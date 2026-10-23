"""
BrainyAi Structured AI Telemetry & Observability Layer
Records structured metrics per AI request, computes rolling provider health,
and guarantees complete privacy (never logs API keys, prompt contents, or uploaded document bytes).
"""

import time
import logging
import threading
from collections import deque
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List

logger = logging.getLogger("ai_telemetry")

@dataclass
class TelemetryRecord:
    request_id: str
    task: str
    depth: str
    provider: str
    model: str
    latency_ms: float
    ttft_ms: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    fallback_used: bool = False
    fallback_from: Optional[str] = None
    error_category: Optional[str] = None
    status: str = "success"  # success, error, fallback_recovered
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if not d["timestamp"]:
            d["timestamp"] = time.time()
        return d

class AITelemetry:
    def __init__(self, max_records: int = 1000, max_events: Optional[int] = None):
        if max_events is not None:
            max_records = max_events
        self._max_records = max_records
        self._records = deque(maxlen=max_records)
        self._lock = threading.Lock()
        self._provider_stats: Dict[str, Dict[str, Any]] = {}

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
        request_id: str = "test-req"
    ):
        rec = TelemetryRecord(
            request_id=request_id,
            task=task,
            depth="BALANCED",
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            error_category=error_category,
            status="success" if success else "error"
        )
        self.record(rec)

    def get_provider_summary(self) -> Dict[str, Any]:
        return self.get_provider_health_summary()

    def record(self, rec: TelemetryRecord):
        if not rec.timestamp:
            rec.timestamp = time.time()

        with self._lock:
            self._records.append(rec)
            stats = self._provider_stats.setdefault(rec.provider, {
                "success": 0,
                "failure": 0,
                "latencies": deque(maxlen=100)
            })
            if rec.status == "error":
                stats["failure"] += 1
            else:
                stats["success"] += 1
                if rec.latency_ms > 0:
                    stats["latencies"].append(rec.latency_ms)

        # Log clean structured line without private content or keys
        logger.info(
            "ai_call task=%s depth=%s provider=%s model=%s latency_ms=%.1f fallback=%s status=%s req_id=%s",
            rec.task, rec.depth, rec.provider, rec.model, rec.latency_ms,
            rec.fallback_used, rec.status, rec.request_id
        )

    def get_provider_health_summary(self) -> Dict[str, Any]:
        """Returns health overview for administrative diagnostics."""
        with self._lock:
            summary = {}
            for prov, stats in self._provider_stats.items():
                succ = stats["success"]
                fail = stats["failure"]
                total = succ + fail
                err_rate = (fail / total * 100.0) if total > 0 else 0.0
                lats = list(stats["latencies"])
                avg_lat = (sum(lats) / len(lats)) if lats else 0.0
                summary[prov] = {
                    "total_requests": total,
                    "total_calls": total,
                    "success": succ,
                    "success_count": succ,
                    "failure": fail,
                    "error_count": fail,
                    "error_rate_pct": round(err_rate, 1),
                    "avg_latency_ms": round(avg_lat, 1),
                    "healthy": err_rate < 50.0 or total < 5
                }
            return summary

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            recs = list(self._records)
            return [r.to_dict() for r in recs[-limit:]]

# Singleton instance
global_telemetry = AITelemetry()
