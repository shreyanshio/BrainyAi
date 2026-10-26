"""
Comprehensive Test Suite for BrainyAi Enterprise Admin Control Center
Validates:
1. Admin identity & RBAC authorization (designated admin shreyansh101008@gmail.com, 401 unauth, 403 non-admin).
2. Token accounting and pricing registry calculations (exact vs estimated).
3. Telemetry recording, KPI aggregation, and time-series bucketing.
4. Provider rate-limit header parsing and health probe execution.
5. CSV formula injection sanitization (=, +, -, @).
6. Security audit logging and active system alert lifecycle.
7. Admin REST API endpoints via Flask test client.
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import time

from app import app
from admin_service import (
    admin_service,
    AdminAccessManager,
    AdminAuditLogger,
    SafeCSVExporter,
    SystemAlertsManager,
    SystemConfigManager,
    parse_admin_emails
)
from ai_routing.pricing import calculate_token_cost, MODEL_PRICING_REGISTRY
from ai_routing.telemetry import AITelemetry, TelemetryRecord
from security import create_auth_token


class TestAdminControlCenter(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

        # Generate tokens
        self.admin_token = create_auth_token(1001, "admin_user", "AdminShrey", email="shreyansh101008@gmail.com", role="admin")
        self.student_token = create_auth_token(2002, "student_user", "StudentUser", email="student@college.edu", role="student")

    def tearDown(self):
        self.app_context.pop()

    # ── 1. IDENTITY & RBAC AUTHORIZATION ──
    def test_designated_admin_allowlist(self):
        """Verifies default designated admin shreyansh101008@gmail.com is authorized."""
        mgr = AdminAccessManager()
        # Case variation and whitespace trimming
        self.assertTrue(mgr.is_admin(email="shreyansh101008@gmail.com"))
        self.assertTrue(mgr.is_admin(email="SHREYANSH101008@GMAIL.COM"))
        self.assertTrue(mgr.is_admin(email="  shreyansh101008@gmail.com  "))

        # Non-admin user rejected
        self.assertFalse(mgr.is_admin(email="random.student@example.com"))
        self.assertFalse(mgr.is_admin(email=""))
        self.assertFalse(mgr.is_admin(user_id=999999))

    def test_admin_api_authorization_status_codes(self):
        """Strict verification: 401 for unauthenticated, 403 for non-admin, 200 for designated admin."""
        # Unauthenticated request -> 401
        res_unauth = self.client.get("/api/admin/kpis")
        self.assertEqual(res_unauth.status_code, 401)
        self.assertIn("error", res_unauth.get_json())

        # Authenticated non-admin -> 403
        res_non_admin = self.client.get(
            "/api/admin/kpis",
            headers={"Authorization": f"Bearer {self.student_token}"}
        )
        self.assertEqual(res_non_admin.status_code, 403)
        self.assertIn("Forbidden", res_non_admin.get_json()["error"])

        # Authenticated designated admin -> 200
        res_admin = self.client.get(
            "/api/admin/kpis",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(res_admin.status_code, 200)

    # ── 2. PRICING ENGINE & COST ACCOUNTING ──
    def test_pricing_registry_calculations(self):
        """Verifies exact rates for documented models and fallback rates for unknown models."""
        # Groq Llama 3.3 70B: $0.59 in, $0.79 out per 1M
        cost, is_est = calculate_token_cost("groq", "llama-3.3-70b-versatile", 1_000_000, 1_000_000)
        self.assertEqual(cost, round(0.59 + 0.79, 6))
        self.assertFalse(is_est)

        # Gemini 2.5 Flash: $0.15 in, $0.60 out per 1M
        cost_gem, is_est_gem = calculate_token_cost("gemini", "gemini-2.5-flash", 500_000, 500_000)
        self.assertEqual(cost_gem, round(0.15 * 0.5 + 0.60 * 0.5, 6))
        self.assertFalse(is_est_gem)

        # OpenRouter free tier models calculate to $0.00
        cost_free, is_est_free = calculate_token_cost("openrouter", "google/gemma-4-31b-it:free", 10_000, 10_000)
        self.assertEqual(cost_free, 0.0)
        self.assertFalse(is_est_free)

        # Fallback rate for unlisted model
        cost_fallback, is_est_fallback = calculate_token_cost("unknown_prov", "mystery-model-v9", 1_000_000, 1_000_000)
        self.assertTrue(is_est_fallback)
        self.assertEqual(cost_fallback, round(0.40 + 0.80, 6))

    # ── 3. TELEMETRY & TIME-SERIES BUCKETING ──
    def test_telemetry_kpis_and_time_series(self):
        """Verifies metrics aggregation, windowing, and time-series buckets."""
        test_telem = AITelemetry(max_records=100)
        t_now = time.time()

        # Record calls
        test_telem.record(TelemetryRecord(
            request_id="req-1",
            user_id=101,
            task="CONCEPT_EXPLANATION",
            depth="BALANCED",
            provider="groq",
            model="llama-3.3-70b-versatile",
            latency_ms=250.0,
            input_tokens=500,
            output_tokens=300,
            status="success",
            timestamp=t_now - 60
        ))
        test_telem.record(TelemetryRecord(
            request_id="req-2",
            user_id=102,
            task="PDF_SUMMARIZATION",
            depth="DEEP",
            provider="gemini",
            model="gemini-2.5-flash",
            latency_ms=450.0,
            input_tokens=1000,
            output_tokens=500,
            fallback_used=True,
            fallback_from="groq",
            status="fallback_recovered",
            timestamp=t_now - 30
        ))
        test_telem.record(TelemetryRecord(
            request_id="req-3",
            user_id=101,
            task="QUICK_ANSWER",
            depth="FAST",
            provider="sambanova",
            model="Meta-Llama-3.1-8B-Instruct",
            latency_ms=100.0,
            status="error",
            error_category="RateLimitExceeded",
            timestamp=t_now - 10
        ))

        # Check KPIs
        kpis = test_telem.get_kpis(window_sec=3600.0)
        self.assertEqual(kpis["total_requests"], 3)
        self.assertEqual(kpis["successful_requests"], 2)
        self.assertEqual(kpis["failed_requests"], 1)
        self.assertEqual(kpis["fallback_requests"], 1)
        self.assertEqual(kpis["input_tokens"], 1500)
        self.assertEqual(kpis["output_tokens"], 800)
        self.assertEqual(kpis["total_tokens"], 2300)
        self.assertEqual(kpis["active_users_in_window"], 2)

        # Check Time-Series buckets
        buckets = test_telem.get_time_series(window_sec=3600.0, num_buckets=6)
        self.assertEqual(len(buckets), 6)
        total_bucket_reqs = sum(b["requests"] for b in buckets)
        self.assertEqual(total_bucket_reqs, 3)

    # ── 4. PROVIDER RATE-LIMIT HEADER PARSING ──
    def test_observe_provider_quota_headers(self):
        """Verifies parsing of x-ratelimit-* headers."""
        test_telem = AITelemetry()
        headers = {
            "x-ratelimit-limit-requests": "1000",
            "x-ratelimit-remaining-requests": "980",
            "x-ratelimit-limit-tokens": "500000",
            "x-ratelimit-remaining-tokens": "495000"
        }
        test_telem.observe_provider_quota("groq", headers, model="llama-3.3-70b-versatile")
        observations = test_telem.get_quota_observations()

        self.assertIn("groq", observations)
        obs = observations["groq"]
        self.assertEqual(obs["remaining_requests"], 980)
        self.assertEqual(obs["limit_requests"], 1000)
        self.assertEqual(obs["remaining_tokens"], 495000)

    # ── 5. CSV FORMULA INJECTION DEFENSE ──
    def test_csv_formula_injection_defense(self):
        """Verifies formulas starting with =, +, -, @, \t, \r are prepended with single quote."""
        unsafe_payloads = [
            "=SUM(A1:A10)",
            "+123456",
            "-cmd|'/C calc'!A0",
            "@import",
            "\tTAB_TEST",
            "\rCR_TEST"
        ]
        for payload in unsafe_payloads:
            sanitized = SafeCSVExporter.sanitize_cell(payload)
            self.assertTrue(
                sanitized.startswith("'"),
                f"Payload {payload} was not escaped: {sanitized}"
            )

        # Normal text and numbers should not be mangled
        self.assertEqual(SafeCSVExporter.sanitize_cell("Normal Text"), "Normal Text")
        self.assertEqual(SafeCSVExporter.sanitize_cell(1234), "1234")
        self.assertEqual(SafeCSVExporter.sanitize_cell(""), "")

    def test_csv_export_generators(self):
        """Verifies generation of CSV reports."""
        # Requests CSV
        sample_logs = [{
            "request_id": "test-req-1",
            "user_id": 101,
            "task": "QUICK_ANSWER",
            "depth": "BALANCED",
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
            "latency_ms": 150.0,
            "ttft_ms": 50.0,
            "input_tokens": 100,
            "output_tokens": 200,
            "total_tokens": 300,
            "cost_usd": 0.0002,
            "is_estimated": False,
            "status": "success",
            "fallback_used": False,
            "timestamp": time.time()
        }]
        csv_req = SafeCSVExporter.export_requests_csv(sample_logs)
        self.assertIn("Request ID", csv_req)
        self.assertIn("test-req-1", csv_req)

        # Users CSV
        sample_users = [{
            "id": 101,
            "username": "shrey",
            "first_name": "Shrey",
            "email": "shrey@test.com",
            "role": "admin",
            "login_count": 5,
            "last_login_at": "2026-10-26T00:00:00Z",
            "is_suspended": False,
            "created_at": "2026-10-01T00:00:00Z"
        }]
        csv_users = SafeCSVExporter.export_users_csv(sample_users)
        self.assertIn("User ID", csv_users)
        self.assertIn("shrey", csv_users)

    # ── 6. AUDIT LOGGING & SYSTEM ALERTS ──
    def test_audit_logger(self):
        """Verifies administrative audit entries are stored and retrieved."""
        logger = AdminAuditLogger(maxlen=10)
        logger.log(
            actor_id=1001,
            actor_email="shreyansh101008@gmail.com",
            action="toggle_user_suspend",
            target_type="user",
            target_id="505",
            details={"is_suspended": True}
        )
        logs = logger.get_logs()
        self.assertEqual(logs["total"], 1)
        self.assertEqual(logs["logs"][0]["action"], "toggle_user_suspend")
        self.assertEqual(logs["logs"][0]["actor_email"], "shreyansh101008@gmail.com")

    def test_system_alerts_lifecycle(self):
        """Verifies creation and resolution of system alerts."""
        alerts_mgr = SystemAlertsManager()
        alert = alerts_mgr.create_alert(
            severity="warning",
            title="High Latency Warning",
            message="Provider latency exceeded 3000ms",
            component="router"
        )
        self.assertEqual(len(alerts_mgr.get_active_alerts()), 1)

        # Resolve alert
        alerts_mgr.resolve_alert(alert["id"], actor_email="shreyansh101008@gmail.com")
        self.assertEqual(len(alerts_mgr.get_active_alerts()), 0)

    # ── 7. ADMIN REST API ENDPOINTS VIA CLIENT ──
    def test_admin_rest_api_suite(self):
        """End-to-end test of admin endpoints with verified admin token."""
        headers = {"Authorization": f"Bearer {self.admin_token}"}

        # 1. /api/admin/check
        res = self.client.get("/api/admin/check", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["is_admin"])

        # 2. /api/admin/timeseries
        res = self.client.get("/api/admin/timeseries?window=3600&buckets=12", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.get_json()), 12)

        # 3. /api/admin/requests
        res = self.client.get("/api/admin/requests?limit=10", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("logs", res.get_json())

        # 4. /api/admin/providers
        res = self.client.get("/api/admin/providers", headers=headers)
        self.assertEqual(res.status_code, 200)
        provs = res.get_json()
        self.assertIn("groq", provs)
        self.assertIn("gemini", provs)
        self.assertIn("sambanova", provs)

        # 5. /api/admin/costs
        res = self.client.get("/api/admin/costs", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("pricing_registry", res.get_json())

        # 6. /api/admin/pdf-analytics
        res = self.client.get("/api/admin/pdf-analytics", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("total_documents", res.get_json())

        # 7. /api/admin/audit-logs
        res = self.client.get("/api/admin/audit-logs", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("logs", res.get_json())

        # 8. /api/admin/config (GET & POST)
        res = self.client.get("/api/admin/config", headers=headers)
        self.assertEqual(res.status_code, 200)
        res_post = self.client.post(
            "/api/admin/config",
            headers=headers,
            json={"key": "test_flag", "value": True}
        )
        self.assertEqual(res_post.status_code, 200)

        # 9. /api/admin/export/requests (CSV)
        res_export = self.client.get("/api/admin/export/requests", headers=headers)
        self.assertEqual(res_export.status_code, 200)
        self.assertEqual(res_export.mimetype, "text/csv")
        self.assertIn("attachment", res_export.headers.get("Content-Disposition", ""))

        # 10. Invalid export type
        res_bad_export = self.client.get("/api/admin/export/invalid_type", headers=headers)
        self.assertEqual(res_bad_export.status_code, 400)


if __name__ == "__main__":
    unittest.main()
