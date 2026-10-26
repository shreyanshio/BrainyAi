"""
BrainyAi Enterprise Admin Control Center Service
Centralizes administrator authorization, observability, metrics aggregation,
provider health probes, quota monitoring, PDF analytics, audit trails, and secure data exports.
"""

import csv
import io
import os
import time
import uuid
import logging
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set

from ai_routing.router import router
from ai_routing.telemetry import telemetry, global_telemetry
from ai_routing.pricing import MODEL_PRICING_REGISTRY, DEFAULT_FALLBACK_RATES

logger = logging.getLogger("admin_service")

# ── 1. ADMIN AUTHORIZATION & IDENTITY ──
DEFAULT_ADMIN_EMAILS = {"shreyansh101008@gmail.com"}


def parse_admin_emails() -> Set[str]:
    """Parses admin email allowlists from environment and defaults."""
    emails = set(DEFAULT_ADMIN_EMAILS)
    for env_var in ("BRAINYAI_ADMIN_EMAILS", "ADMIN_EMAILS"):
        val = os.environ.get(env_var, "")
        if val:
            for part in val.split(","):
                part = part.strip().lower()
                if part and "@" in part:
                    emails.add(part)
    return emails


def parse_admin_user_ids() -> Set[int]:
    ids = set()
    val = os.environ.get("ADMIN_USER_IDS", "")
    if val:
        for part in val.split(","):
            part = part.strip()
            if part.isdigit():
                ids.add(int(part))
    return ids


def parse_admin_usernames() -> Set[str]:
    names = set()
    val = os.environ.get("ADMIN_USERNAMES", "")
    if val:
        for part in val.split(","):
            part = part.strip().lstrip("@").lower()
            if part:
                names.add(part)
    return names


class AdminAccessManager:
    """Authoritative server-side role check."""

    def __init__(self, sb_req_fn=None):
        self._sb_req = sb_req_fn

    def set_supabase_requester(self, sb_req_fn):
        self._sb_req = sb_req_fn

    def is_admin(
        self,
        user_id: Optional[int | str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None
    ) -> bool:
        norm_email = (email or "").strip().lower()
        if norm_email:
            allowed_emails = parse_admin_emails()
            if norm_email in allowed_emails:
                return True

        if user_id is not None:
            try:
                uid_int = int(user_id)
                if uid_int in parse_admin_user_ids():
                    return True
            except (ValueError, TypeError):
                pass

        norm_user = (username or "").strip().lstrip("@").lower()
        if norm_user and norm_user in parse_admin_usernames():
            return True

        # Check Supabase admin_roles table if configured
        if norm_email and self._sb_req:
            try:
                res = self._sb_req(
                    "GET",
                    "admin_roles",
                    params=f"?email=eq.{norm_email}&is_active=eq.true&select=role,is_active"
                )
                if res and res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list) and len(data) > 0:
                        return True
            except Exception as e:
                logger.debug("admin_roles lookup non-fatal error: %s", e)

        return False


# ── 2. AUDIT LOGGING & COMPLIANCE ──
class AdminAuditLogger:
    def __init__(self, maxlen: int = 1000, sb_req_fn=None):
        self._logs = deque(maxlen=maxlen)
        self._sb_req = sb_req_fn

    def set_supabase_requester(self, sb_req_fn):
        self._sb_req = sb_req_fn

    def log(
        self,
        actor_id: Optional[int | str],
        actor_email: Optional[str],
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ):
        now_ts = time.time()
        now_iso = datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat()
        entry = {
            "id": str(uuid.uuid4()),
            "actor_id": str(actor_id) if actor_id is not None else None,
            "actor_email": actor_email or "system",
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id) if target_id is not None else None,
            "details": details or {},
            "ip_address": ip_address,
            "created_at": now_iso,
            "timestamp": now_ts
        }
        self._logs.appendleft(entry)
        logger.info(
            "admin_audit actor=%s action=%s target=%s/%s details=%s",
            actor_email, action, target_type, target_id, details
        )

        if self._sb_req:
            try:
                self._sb_req(
                    "POST",
                    "admin_audit_logs",
                    json_body={
                        "actor_id": int(actor_id) if actor_id and str(actor_id).isdigit() else None,
                        "actor_email": actor_email or "system",
                        "action": action,
                        "target_type": target_type,
                        "target_id": str(target_id) if target_id is not None else None,
                        "details": details or {},
                        "ip_address": ip_address,
                        "created_at": now_iso
                    }
                )
            except Exception as e:
                logger.debug("Failed to persist audit log to Supabase: %s", e)

    def get_logs(self, limit: int = 50, offset: int = 0, action: Optional[str] = None) -> Dict[str, Any]:
        logs_list = list(self._logs)
        if action:
            logs_list = [l for l in logs_list if l["action"].lower() == action.lower()]
        total = len(logs_list)
        sliced = logs_list[offset: offset + limit]
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "logs": sliced
        }


# ── 3. CSV FORMULA INJECTION DEFENSE & EXPORT ENGINE ──
class SafeCSVExporter:
    @staticmethod
    def sanitize_cell(value: Any) -> str:
        """
        Escapes cells against formula injection (CSV/DDE Injection).
        Cells starting with =, +, -, @, tab, or carriage return are prepended with a single quote.
        """
        if value is None:
            return ""
        s = str(value)
        if not s:
            return ""
        first_char = s[0]
        if first_char in ("=", "+", "-", "@", "\t", "\r"):
            return f"'{s}"
        return s

    @classmethod
    def export_requests_csv(cls, logs: List[Dict[str, Any]]) -> str:
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        headers = [
            "Request ID", "Timestamp (UTC)", "User ID", "Task", "Depth",
            "Provider", "Model", "Latency (ms)", "TTFT (ms)",
            "Input Tokens", "Output Tokens", "Total Tokens",
            "Cost USD", "Is Estimated", "Status", "Fallback Used", "Fallback From"
        ]
        writer.writerow([cls.sanitize_cell(h) for h in headers])

        for r in logs:
            ts_iso = ""
            if r.get("timestamp"):
                ts_iso = datetime.fromtimestamp(r["timestamp"], tz=timezone.utc).isoformat()
            row = [
                cls.sanitize_cell(r.get("request_id")),
                cls.sanitize_cell(ts_iso),
                cls.sanitize_cell(r.get("user_id")),
                cls.sanitize_cell(r.get("task")),
                cls.sanitize_cell(r.get("depth")),
                cls.sanitize_cell(r.get("provider")),
                cls.sanitize_cell(r.get("model")),
                cls.sanitize_cell(round(r.get("latency_ms", 0), 2)),
                cls.sanitize_cell(round(r.get("ttft_ms", 0), 2) if r.get("ttft_ms") is not None else ""),
                cls.sanitize_cell(r.get("input_tokens", 0)),
                cls.sanitize_cell(r.get("output_tokens", 0)),
                cls.sanitize_cell(r.get("total_tokens", 0)),
                cls.sanitize_cell(r.get("cost_usd", 0.0)),
                cls.sanitize_cell(r.get("is_estimated", False)),
                cls.sanitize_cell(r.get("status")),
                cls.sanitize_cell(r.get("fallback_used", False)),
                cls.sanitize_cell(r.get("fallback_from", ""))
            ]
            writer.writerow(row)
        return output.getvalue()

    @classmethod
    def export_users_csv(cls, users: List[Dict[str, Any]]) -> str:
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        headers = [
            "User ID", "Username", "First Name", "Email", "Role",
            "Login Count", "Last Login (UTC)", "Suspended", "Created At"
        ]
        writer.writerow([cls.sanitize_cell(h) for h in headers])

        for u in users:
            row = [
                cls.sanitize_cell(u.get("id")),
                cls.sanitize_cell(u.get("username")),
                cls.sanitize_cell(u.get("first_name")),
                cls.sanitize_cell(u.get("email")),
                cls.sanitize_cell(u.get("role")),
                cls.sanitize_cell(u.get("login_count", 0)),
                cls.sanitize_cell(u.get("last_login_at")),
                cls.sanitize_cell(u.get("is_suspended", False)),
                cls.sanitize_cell(u.get("created_at"))
            ]
            writer.writerow(row)
        return output.getvalue()

    @classmethod
    def export_audit_logs_csv(cls, logs: List[Dict[str, Any]]) -> str:
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        headers = [
            "ID", "Timestamp (UTC)", "Actor ID", "Actor Email",
            "Action", "Target Type", "Target ID", "IP Address", "Details"
        ]
        writer.writerow([cls.sanitize_cell(h) for h in headers])

        for l in logs:
            row = [
                cls.sanitize_cell(l.get("id")),
                cls.sanitize_cell(l.get("created_at")),
                cls.sanitize_cell(l.get("actor_id")),
                cls.sanitize_cell(l.get("actor_email")),
                cls.sanitize_cell(l.get("action")),
                cls.sanitize_cell(l.get("target_type")),
                cls.sanitize_cell(l.get("target_id")),
                cls.sanitize_cell(l.get("ip_address")),
                cls.sanitize_cell(str(l.get("details", {})))
            ]
            writer.writerow(row)
        return output.getvalue()

    @classmethod
    def export_costs_csv(cls, summary: Dict[str, Any]) -> str:
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([cls.sanitize_cell(h) for h in ["Provider", "Model", "Input Rate / 1M ($)", "Output Rate / 1M ($)", "Estimated Cost USD"]])
        for m, rates in MODEL_PRICING_REGISTRY.items():
            cost = summary.get("by_model", {}).get(m, 0.0)
            writer.writerow([
                cls.sanitize_cell("registry"),
                cls.sanitize_cell(m),
                cls.sanitize_cell(rates["input"]),
                cls.sanitize_cell(rates["output"]),
                cls.sanitize_cell(cost)
            ])
        return output.getvalue()


# ── 4. SYSTEM ALERTS & CONFIGURATION ──
class SystemAlertsManager:
    def __init__(self, sb_req_fn=None):
        self._alerts: Dict[str, Dict[str, Any]] = {}
        self._sb_req = sb_req_fn

    def set_supabase_requester(self, sb_req_fn):
        self._sb_req = sb_req_fn

    def create_alert(
        self,
        severity: str,  # info, warning, error, critical
        title: str,
        message: str,
        component: str,
        alert_id: Optional[str] = None
    ) -> Dict[str, Any]:
        aid = alert_id or str(uuid.uuid4())
        now_ts = time.time()
        now_iso = datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat()
        alert = {
            "id": aid,
            "severity": severity,
            "title": title,
            "message": message,
            "component": component,
            "created_at": now_iso,
            "is_resolved": False,
            "resolved_at": None,
            "resolved_by": None
        }
        self._alerts[aid] = alert

        if self._sb_req:
            try:
                self._sb_req("POST", "admin_system_alerts", json_body=alert)
            except Exception as e:
                logger.debug("Failed to persist alert: %s", e)
        return alert

    def resolve_alert(self, alert_id: str, actor_email: str) -> bool:
        if alert_id in self._alerts:
            self._alerts[alert_id]["is_resolved"] = True
            self._alerts[alert_id]["resolved_at"] = datetime.now(timezone.utc).isoformat()
            self._alerts[alert_id]["resolved_by"] = actor_email

        if self._sb_req:
            try:
                self._sb_req(
                    "PATCH",
                    "admin_system_alerts",
                    params=f"?id=eq.{alert_id}",
                    json_body={
                        "is_resolved": True,
                        "resolved_at": datetime.now(timezone.utc).isoformat(),
                        "resolved_by": actor_email
                    }
                )
            except Exception as e:
                logger.debug("Failed to resolve alert in Supabase: %s", e)
        return True

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        # Evaluate dynamic alert rules
        prov_health = telemetry.get_provider_health_summary()
        for prov_name, stats in prov_health.items():
            if stats.get("total_requests", 0) >= 5 and stats.get("error_rate_pct", 0) >= 50.0:
                aid = f"prov-err-{prov_name}"
                if aid not in self._alerts or self._alerts[aid]["is_resolved"]:
                    self.create_alert(
                        severity="error",
                        title=f"High Error Rate on {prov_name}",
                        message=f"Provider {prov_name} has an error rate of {stats['error_rate_pct']}% across {stats['total_requests']} requests.",
                        component="ai_routing",
                        alert_id=aid
                    )

        return [a for a in self._alerts.values() if not a.get("is_resolved")]


class SystemConfigManager:
    def __init__(self, sb_req_fn=None):
        self._config: Dict[str, Any] = {
            "maintenance_mode": False,
            "default_response_depth": "BALANCED",
            "global_rate_limit_per_min": 60,
            "pdf_max_file_size_mb": 25,
            "enable_web_grounding": True,
            "enable_ocr_fallback": True
        }
        self._sb_req = sb_req_fn

    def set_supabase_requester(self, sb_req_fn):
        self._sb_req = sb_req_fn

    def get_config(self) -> Dict[str, Any]:
        return dict(self._config)

    def update_config(self, key: str, value: Any, actor: str) -> Dict[str, Any]:
        self._config[key] = value
        now_iso = datetime.now(timezone.utc).isoformat()
        if self._sb_req:
            try:
                self._sb_req(
                    "POST",
                    "admin_system_config",
                    json_body={
                        "key": key,
                        "value": str(value),
                        "updated_by": actor,
                        "updated_at": now_iso
                    }
                )
            except Exception as e:
                logger.debug("Non-fatal config persist error: %s", e)
        return self._config


# ── 5. ADMIN CONTROL CENTER SERVICE FACADE ──
class AdminControlService:
    def __init__(self):
        self.access = AdminAccessManager()
        self.audit = AdminAuditLogger()
        self.alerts = SystemAlertsManager()
        self.config = SystemConfigManager()
        self.telemetry = telemetry
        self._sb_req = None

    def set_supabase_requester(self, sb_req_fn):
        self._sb_req = sb_req_fn
        self.access.set_supabase_requester(sb_req_fn)
        self.audit.set_supabase_requester(sb_req_fn)
        self.alerts.set_supabase_requester(sb_req_fn)
        self.config.set_supabase_requester(sb_req_fn)
        telemetry.set_supabase_requester(sb_req_fn)

    def get_kpis(self, window_sec: float = 86400.0, user_report: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Returns consolidated KPIs across AI, users, and documents."""
        telemetry_kpis = telemetry.get_kpis(window_sec=window_sec)

        # PDF metrics
        pdf_analytics = self.get_pdf_analytics()

        # User metrics
        total_users = 0
        active_today = 0
        active_week = 0
        suspended_users = 0
        if user_report:
            total_users = user_report.get("total_users", 0)
            active_today = user_report.get("active_today", 0)
            active_week = user_report.get("active_week", 0)
            suspended_users = user_report.get("suspended_users_count", 0)

        active_alerts = len(self.alerts.get_active_alerts())

        return {
            **telemetry_kpis,
            "total_users": total_users,
            "active_users_today": active_today,
            "active_users_week": active_week,
            "suspended_users": suspended_users,
            "total_pdf_documents": pdf_analytics.get("total_documents", 0),
            "total_pdf_pages": pdf_analytics.get("total_pages", 0),
            "active_alerts_count": active_alerts,
            "server_timestamp": time.time(),
            "server_time_iso": datetime.now(timezone.utc).isoformat()
        }

    def get_providers_status(self) -> Dict[str, Any]:
        """Provides status, health, and key configuration across AI and Search providers."""
        prov_health = telemetry.get_provider_health_summary()
        providers = {}

        provider_keys = {
            "groq": ("GROQ_API_KEY", ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3.8-27b", "openai/gpt-oss-120b"]),
            "gemini": ("GEMINI_API_KEY", ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite"]),
            "sambanova": ("SAMBANOVA_API_KEY", ["Meta-Llama-3.3-70B-Instruct", "Meta-Llama-3.1-8B-Instruct", "Qwen2.5-72B-Instruct"]),
            "cerebras": ("CEREBRAS_API_KEY", ["llama3.1-8b", "qwen-3.8-27b", "gpt-oss-120b"]),
            "openrouter": ("OPENROUTER_API_KEY", ["google/gemma-4-31b-it:free", "nvidia/nemotron-3.5-lightning:free"]),
            "tavily": ("TAVILY_API_KEY", ["search"]),
            "duckduckgo": (None, ["instant_answer"])
        }

        for prov_id, (key_env, models) in provider_keys.items():
            key_val = os.environ.get(key_env, "") if key_env else "built-in"
            has_key = bool(key_val and key_val.strip())
            masked_key = f"{key_val[:4]}...{key_val[-4:]}" if has_key and len(key_val) > 8 else ("configured" if has_key else "missing")
            if prov_id == "duckduckgo":
                masked_key = "free-no-key-required"

            health = prov_health.get(prov_id, {
                "total_requests": 0,
                "success_count": 0,
                "error_count": 0,
                "error_rate_pct": 0.0,
                "avg_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "healthy": has_key
            })

            providers[prov_id] = {
                "id": prov_id,
                "name": prov_id.capitalize(),
                "configured": has_key,
                "masked_key": masked_key,
                "models": models,
                "health": health
            }

        return providers

    def probe_provider(self, provider_name: str) -> Dict[str, Any]:
        """Executes a live health probe against a provider and records latency & headers."""
        prov_name = provider_name.lower().strip()
        start_t = time.perf_counter()
        prov_inst = router.get_provider(prov_name)

        if not prov_inst:
            return {
                "provider": prov_name,
                "success": False,
                "latency_ms": 0.0,
                "error": f"Provider '{prov_name}' is not recognized or not registered."
            }

        try:
            # Dispatch minimal lightweight probe
            res = prov_inst.generate(
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5
            )
            lat = (time.perf_counter() - start_t) * 1000.0

            # Record in telemetry
            telemetry.record_call(
                provider=prov_name,
                model=getattr(res, "model", "probe"),
                task="HEALTH_PROBE",
                latency_ms=lat,
                success=True,
                tokens_in=1,
                tokens_out=1,
                request_id=f"probe-{int(time.time())}"
            )

            return {
                "provider": prov_name,
                "success": True,
                "latency_ms": round(lat, 2),
                "model": getattr(res, "model", "default"),
                "status": "healthy"
            }
        except Exception as e:
            lat = (time.perf_counter() - start_t) * 1000.0
            telemetry.record_call(
                provider=prov_name,
                model="probe",
                task="HEALTH_PROBE",
                latency_ms=lat,
                success=False,
                error_category=type(e).__name__,
                request_id=f"probe-fail-{int(time.time())}"
            )
            return {
                "provider": prov_name,
                "success": False,
                "latency_ms": round(lat, 2),
                "error": str(e)
            }

    def get_pdf_analytics(self) -> Dict[str, Any]:
        """Gathers document statistics from local storage and in-memory caches."""
        try:
            from pdf_studio.service import _DOCUMENTS_STORE, _PAGES_STORE
            docs = list(_DOCUMENTS_STORE.values())
            pages_all = [p for page_list in _PAGES_STORE.values() for p in page_list]

            total_docs = len(docs)
            total_pages = sum(d.get("page_count", 0) for d in docs)
            total_size_bytes = sum(d.get("file_size_bytes", 0) for d in docs)

            native_pages = sum(1 for p in pages_all if not p.get("is_ocr"))
            ocr_pages = sum(1 for p in pages_all if p.get("is_ocr"))

            lats = [d.get("extraction_time_ms", 0) for d in docs if d.get("extraction_time_ms", 0) > 0]
            avg_time = (sum(lats) / len(lats)) if lats else 0.0

            failed_docs = sum(1 for d in docs if d.get("status") == "error")

            return {
                "total_documents": total_docs,
                "total_pages": total_pages,
                "total_size_bytes": total_size_bytes,
                "native_pages": native_pages,
                "ocr_pages": ocr_pages,
                "avg_extraction_time_ms": round(avg_time, 1),
                "failed_documents": failed_docs,
                "recent_documents": docs[-10:] if docs else []
            }
        except Exception as e:
            logger.debug("PDF analytics retrieval non-fatal error: %s", e)
            return {
                "total_documents": 0,
                "total_pages": 0,
                "total_size_bytes": 0,
                "native_pages": 0,
                "ocr_pages": 0,
                "avg_extraction_time_ms": 0.0,
                "failed_documents": 0,
                "recent_documents": []
            }

    def get_costs_summary(self) -> Dict[str, Any]:
        """Provides total estimated cost and model breakdown."""
        kpis = telemetry.get_kpis(window_sec=2592000.0)  # 30-day window
        prov_health = telemetry.get_provider_health_summary()

        by_provider = {}
        for prov, data in prov_health.items():
            by_provider[prov] = {
                "tokens_in": data.get("tokens_in", 0),
                "tokens_out": data.get("tokens_out", 0),
                "cost_usd": data.get("total_cost_usd", 0.0)
            }

        return {
            "total_estimated_cost_usd": kpis.get("estimated_cost_usd", 0.0),
            "pricing_registry": MODEL_PRICING_REGISTRY,
            "fallback_rates": DEFAULT_FALLBACK_RATES,
            "cost_by_provider": by_provider
        }


# Singleton instance
admin_service = AdminControlService()
