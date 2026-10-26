"""
BrainyAi Structured AI Telemetry & Observability Layer
Records structured metrics per AI request, computes rolling provider health,
tracks exact/estimated costs, durable Supabase persistence, and rate-limit header observations.
Guarantees complete user privacy: never logs API keys, prompt contents, or uploaded document bytes.
"""

import time
import logging
import threading
from collections import deque
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from ai_routing.pricing import calculate_token_cost

logger = logging.getLogger("ai_telemetry")


@dataclass
class TelemetryRecord:
    request_id: str
    task: str
    depth: str
    provider: str
    model: str
    latency_ms: float
    user_id: Optional[int | str] = None
    ttft_ms: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    fallback_used: bool = False
    fallback_from: Optional[str] = None
    error_category: Optional[str] = None
    status: str = "success"  # success, error, fallback_recovered
    continuation_used: bool = False
    continuation_rounds: int = 0
    cost_usd: float = 0.0
    is_estimated: bool = False
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if not d["timestamp"]:
            d["timestamp"] = time.time()
        if d["total_tokens"] is None:
            in_t = d.get("input_tokens") or 0
            out_t = d.get("output_tokens") or 0
            d["total_tokens"] = in_t + out_t
        return d


class AITelemetry:
    def __init__(self, max_records: int = 2000, max_events: Optional[int] = None):
        if max_events is not None:
            max_records = max_events
        self._max_records = max_records
        self._records = deque(maxlen=max_records)
        self._lock = threading.Lock()
        self._provider_stats: Dict[str, Dict[str, Any]] = {}
        self._quota_observations: Dict[str, Dict[str, Any]] = {}
        self._sb_req = None

    def set_supabase_requester(self, sb_req_fn):
        """Allows injecting Supabase PostgREST client for durable persistence."""
        self._sb_req = sb_req_fn

    def record_call(
        self,
        provider: str,
        model: str,
        task: str,
        latency_ms: float,
        success: bool = True,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
        error_category: Optional[str] = None,
        request_id: str = "test-req",
        user_id: Optional[int | str] = None
    ):
        """Helper for simple call recording with automatic cost calculation."""
        cost, is_est = calculate_token_cost(provider, model, tokens_in, tokens_out)
        tot_tok = (tokens_in or 0) + (tokens_out or 0)

        rec = TelemetryRecord(
            request_id=request_id,
            user_id=user_id,
            task=task,
            depth="BALANCED",
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            total_tokens=tot_tok,
            error_category=error_category,
            status="success" if success else "error",
            cost_usd=cost,
            is_estimated=is_est
        )
        self.record(rec)

    def record(self, rec: TelemetryRecord):
        """Authoritative request recording method."""
        if not rec.timestamp:
            rec.timestamp = time.time()

        if rec.total_tokens is None:
            rec.total_tokens = (rec.input_tokens or 0) + (rec.output_tokens or 0)

        if rec.cost_usd == 0.0 and (rec.input_tokens or rec.output_tokens):
            cost, is_est = calculate_token_cost(rec.provider, rec.model, rec.input_tokens, rec.output_tokens)
            rec.cost_usd = cost
            rec.is_estimated = is_est

        with self._lock:
            self._records.append(rec)
            stats = self._provider_stats.setdefault(rec.provider, {
                "success": 0,
                "failure": 0,
                "latencies": deque(maxlen=100),
                "tokens_in": 0,
                "tokens_out": 0,
                "total_cost": 0.0,
                "last_success_at": None,
                "last_failure_at": None
            })
            if rec.status == "error":
                stats["failure"] += 1
                stats["last_failure_at"] = rec.timestamp
            else:
                stats["success"] += 1
                stats["last_success_at"] = rec.timestamp
                if rec.latency_ms > 0:
                    stats["latencies"].append(rec.latency_ms)

            stats["tokens_in"] += (rec.input_tokens or 0)
            stats["tokens_out"] += (rec.output_tokens or 0)
            stats["total_cost"] += rec.cost_usd

        # Log clean telemetry line without secrets or prompt bodies
        logger.info(
            "ai_call task=%s depth=%s provider=%s model=%s latency_ms=%.1f tokens_in=%s tokens_out=%s cost=$%.6f status=%s req_id=%s user_id=%s",
            rec.task, rec.depth, rec.provider, rec.model, rec.latency_ms,
            rec.input_tokens, rec.output_tokens, rec.cost_usd, rec.status, rec.request_id, rec.user_id
        )

        # Durable async/safe persistence to Supabase if configured
        if self._sb_req:
            try:
                created_iso = datetime.fromtimestamp(rec.timestamp, tz=timezone.utc).isoformat()
                payload = {
                    "request_id": rec.request_id,
                    "user_id": int(rec.user_id) if rec.user_id and str(rec.user_id).isdigit() else None,
                    "task": rec.task,
                    "depth": rec.depth,
                    "provider": rec.provider,
                    "model": rec.model,
                    "latency_ms": round(rec.latency_ms, 2),
                    "ttft_ms": round(rec.ttft_ms, 2) if rec.ttft_ms is not None else None,
                    "input_tokens": rec.input_tokens or 0,
                    "output_tokens": rec.output_tokens or 0,
                    "total_tokens": rec.total_tokens or 0,
                    "status": rec.status,
                    "fallback_used": rec.fallback_used,
                    "fallback_from": rec.fallback_from,
                    "error_category": rec.error_category,
                    "cost_usd": rec.cost_usd,
                    "is_estimated": rec.is_estimated,
                    "created_at": created_iso
                }
                self._sb_req("POST", "ai_request_logs", json_body=payload)
            except Exception as e:
                logger.debug("Non-fatal Supabase telemetry persistence error: %s", e)

    def observe_provider_quota(self, provider: str, headers: Dict[str, str], model: Optional[str] = None):
        """Parses real rate-limit headers returned by providers and stores observations."""
        if not headers or not isinstance(headers, dict):
            return

        norm_headers = {k.lower(): v for k, v in headers.items()}
        now_ts = time.time()

        def _parse_int(key_patterns):
            for pat in key_patterns:
                val = norm_headers.get(pat.lower())
                if val is not None and str(val).isdigit():
                    return int(val)
            return None

        req_limit = _parse_int(["x-ratelimit-limit-requests", "ratelimit-limit-requests"])
        req_rem = _parse_int(["x-ratelimit-remaining-requests", "ratelimit-remaining-requests"])
        tok_limit = _parse_int(["x-ratelimit-limit-tokens", "ratelimit-limit-tokens"])
        tok_rem = _parse_int(["x-ratelimit-remaining-tokens", "ratelimit-remaining-tokens"])

        if req_limit is not None or req_rem is not None or tok_limit is not None or tok_rem is not None:
            observation = {
                "provider": provider,
                "model": model,
                "limit_requests": req_limit,
                "remaining_requests": req_rem,
                "limit_tokens": tok_limit,
                "remaining_tokens": tok_rem,
                "observed_at": now_ts,
                "observed_iso": datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat(),
                "source": "response_headers"
            }
            with self._lock:
                self._quota_observations[provider] = observation

    def get_quota_observations(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._quota_observations)

    def get_provider_health_summary(self) -> Dict[str, Any]:
        """Returns health overview for diagnostics and provider monitoring."""
        with self._lock:
            summary = {}
            for prov, stats in self._provider_stats.items():
                succ = stats["success"]
                fail = stats["failure"]
                total = succ + fail
                err_rate = (fail / total * 100.0) if total > 0 else 0.0
                lats = list(stats["latencies"])
                avg_lat = (sum(lats) / len(lats)) if lats else 0.0
                p95_lat = sorted(lats)[int(len(lats) * 0.95)] if lats else avg_lat

                summary[prov] = {
                    "provider": prov,
                    "total_requests": total,
                    "total_calls": total,
                    "success": succ,
                    "success_count": succ,
                    "failure": fail,
                    "error_count": fail,
                    "error_rate_pct": round(err_rate, 1),
                    "avg_latency_ms": round(avg_lat, 1),
                    "p95_latency_ms": round(p95_lat, 1),
                    "tokens_in": stats.get("tokens_in", 0),
                    "tokens_out": stats.get("tokens_out", 0),
                    "total_cost_usd": round(stats.get("total_cost", 0.0), 4),
                    "last_success_at": stats.get("last_success_at"),
                    "last_failure_at": stats.get("last_failure_at"),
                    "healthy": err_rate < 50.0 or total < 5
                }
            return summary

    def get_kpis(self, window_sec: float = 86400.0) -> Dict[str, Any]:
        """Calculates core KPI cards across the active time window."""
        now = time.time()
        start_ts = now - window_sec

        with self._lock:
            window_recs = [r for r in self._records if r.timestamp >= start_ts]

        total_reqs = len(window_recs)
        succ_reqs = sum(1 for r in window_recs if r.status != "error")
        fail_reqs = sum(1 for r in window_recs if r.status == "error")
        fallback_reqs = sum(1 for r in window_recs if r.fallback_used)

        in_tokens = sum(r.input_tokens or 0 for r in window_recs)
        out_tokens = sum(r.output_tokens or 0 for r in window_recs)
        total_tokens = in_tokens + out_tokens
        total_cost = sum(r.cost_usd for r in window_recs)

        latencies = [r.latency_ms for r in window_recs if r.latency_ms > 0]
        avg_lat = (sum(latencies) / len(latencies)) if latencies else 0.0
        p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0

        unique_users = len(set(r.user_id for r in window_recs if r.user_id is not None))

        return {
            "total_requests": total_reqs,
            "successful_requests": succ_reqs,
            "failed_requests": fail_reqs,
            "fallback_requests": fallback_reqs,
            "success_rate_pct": round((succ_reqs / total_reqs * 100.0) if total_reqs > 0 else 100.0, 1),
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "total_tokens": total_tokens,
            "avg_tokens_per_request": round((total_tokens / total_reqs) if total_reqs > 0 else 0.0, 1),
            "estimated_cost_usd": round(total_cost, 4),
            "avg_latency_ms": round(avg_lat, 1),
            "p95_latency_ms": round(p95_lat, 1),
            "active_users_in_window": unique_users
        }

    def get_time_series(self, window_sec: float = 86400.0, num_buckets: int = 24) -> List[Dict[str, Any]]:
        """Produces aggregated time-series buckets for interactive charts."""
        now = time.time()
        start_ts = now - window_sec
        bucket_size = window_sec / num_buckets

        with self._lock:
            window_recs = [r for r in self._records if r.timestamp >= start_ts]

        buckets = []
        for i in range(num_buckets):
            b_start = start_ts + i * bucket_size
            b_end = b_start + bucket_size
            b_recs = [r for r in window_recs if b_start <= r.timestamp < b_end]

            reqs = len(b_recs)
            succ = sum(1 for r in b_recs if r.status != "error")
            fail = sum(1 for r in b_recs if r.status == "error")
            in_tok = sum(r.input_tokens or 0 for r in b_recs)
            out_tok = sum(r.output_tokens or 0 for r in b_recs)
            cost = sum(r.cost_usd for r in b_recs)
            lats = [r.latency_ms for r in b_recs if r.latency_ms > 0]
            avg_l = (sum(lats) / len(lats)) if lats else 0.0

            b_iso = datetime.fromtimestamp(b_start, tz=timezone.utc).strftime("%H:%M" if window_sec <= 86400 else "%m-%d %H:00")

            buckets.append({
                "time_label": b_iso,
                "timestamp": b_start,
                "requests": reqs,
                "successful": succ,
                "failed": fail,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "total_tokens": in_tok + out_tok,
                "cost_usd": round(cost, 5),
                "avg_latency_ms": round(avg_l, 1)
            })

        return buckets

    def get_request_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        status: Optional[str] = None,
        user_id: Optional[int | str] = None
    ) -> Dict[str, Any]:
        """Retrieves paginated, filtered request logs."""
        with self._lock:
            all_recs = list(self._records)

        # Apply filters
        filtered = all_recs
        if provider:
            filtered = [r for r in filtered if r.provider.lower() == provider.lower()]
        if model:
            filtered = [r for r in filtered if model.lower() in r.model.lower()]
        if status:
            filtered = [r for r in filtered if r.status.lower() == status.lower()]
        if user_id is not None:
            filtered = [r for r in filtered if str(r.user_id) == str(user_id)]

        total_count = len(filtered)
        # Reverse chronological
        sorted_recs = sorted(filtered, key=lambda x: x.timestamp, reverse=True)
        slice_recs = sorted_recs[offset: offset + limit]

        return {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "logs": [r.to_dict() for r in slice_recs]
        }

    def get_user_analytics(self, user_id: int) -> Dict[str, Any]:
        """Aggregates usage statistics for a specific user ID."""
        with self._lock:
            user_recs = [r for r in self._records if str(r.user_id) == str(user_id)]

        total_reqs = len(user_recs)
        in_tok = sum(r.input_tokens or 0 for r in user_recs)
        out_tok = sum(r.output_tokens or 0 for r in user_recs)
        total_cost = sum(r.cost_usd for r in user_recs)

        prov_counts: Dict[str, int] = {}
        for r in user_recs:
            prov_counts[r.provider] = prov_counts.get(r.provider, 0) + 1

        return {
            "user_id": user_id,
            "total_requests": total_reqs,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "total_tokens": in_tok + out_tok,
            "estimated_cost_usd": round(total_cost, 4),
            "provider_distribution": prov_counts,
            "recent_requests": [r.to_dict() for r in user_recs[-10:]]
        }

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            recs = list(self._records)
            return [r.to_dict() for r in recs[-limit:]]


# Global singleton instances
global_telemetry = AITelemetry()
telemetry = global_telemetry
AITelemetry.get_provider_summary = AITelemetry.get_provider_health_summary
