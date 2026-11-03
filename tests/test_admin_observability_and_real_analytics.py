"""
BrainyAi - Comprehensive Test Suite for Real Admin Panel Observability,
Real-Time Analytics, Rate-Limit Controls, User Inspection & Security Compliance
"""

import os
import json
import time
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# Ensure required testing environment
os.environ["FLASK_SECRET_KEY"] = "test-admin-secret-key-0123456789"
os.environ["APP_ENV"] = "testing"
os.environ["BRAINYAI_ADMIN_EMAILS"] = "admin@brainy.ai,shreyansh101008@gmail.com"
os.environ["ADMIN_USER_IDS"] = "1001,1002"
os.environ["ADMIN_USERNAMES"] = "adminuser"

import app
from app import app as flask_app
from admin_service import admin_service, SafeCSVExporter
from ai_routing.telemetry import telemetry, TelemetryRecord


class TestAdminObservabilityAndAnalytics(unittest.TestCase):
    def setUp(self):
        self.client = flask_app.test_client()
        self.app_context = flask_app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def _login_admin(self, user_id=1001, email="shreyansh101008@gmail.com", username="adminuser"):
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["email"] = email
            sess["username"] = username
            sess["first_name"] = "SuperAdmin"

    def _login_student(self, user_id=9999, email="student@school.edu", username="student1"):
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["email"] = email
            sess["username"] = username
            sess["first_name"] = "RegularStudent"

    # ── 1. ADMIN AUTHORIZATION & SECURITY ──

    def test_unauthorized_user_blocked_from_admin_kpis(self):
        self._login_student()
        resp = self.client.get("/api/admin/kpis")
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertIn("Administrator access required", data.get("error", ""))

    def test_unauthenticated_request_blocked_from_admin(self):
        resp = self.client.get("/api/admin/kpis")
        self.assertEqual(resp.status_code, 401)

    def test_admin_authorized_by_allowlist_email(self):
        self._login_admin(user_id=8888, email="shreyansh101008@gmail.com", username="customname")
        resp = self.client.get("/api/admin/kpis")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("total_requests", data)
        self.assertIn("total_users", data)

    def test_admin_authorized_by_admin_user_id(self):
        self._login_admin(user_id=1001, email="other@domain.com", username="random")
        resp = self.client.get("/api/admin/kpis")
        self.assertEqual(resp.status_code, 200)

    # ── 2. REAL KPIS & TIMESERIES AGGREGATIONS ──

    def test_admin_kpis_calculation_and_cohorts(self):
        self._login_admin()
        # Record sample telemetry calls
        telemetry.record_call(
            provider="groq",
            model="llama-3.3-70b-versatile",
            task="CODING",
            latency_ms=150.0,
            success=True,
            tokens_in=120,
            tokens_out=250,
            request_id="test-kpi-1",
            user_id=123
        )
        telemetry.record_call(
            provider="gemini",
            model="gemini-2.5-flash",
            task="QUICK_CHAT",
            latency_ms=95.0,
            success=True,
            tokens_in=50,
            tokens_out=100,
            request_id="test-kpi-2",
            user_id=456
        )

        resp = self.client.get("/api/admin/kpis?window=86400")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertGreaterEqual(data["total_requests"], 2)
        self.assertGreaterEqual(data["input_tokens"], 170)
        self.assertGreaterEqual(data["output_tokens"], 350)
        self.assertGreaterEqual(data["total_tokens"], 520)
        self.assertIn("active_users_today", data)
        self.assertIn("active_users_week", data)
        self.assertIn("total_conversations", data)
        self.assertIn("total_messages", data)

    def test_admin_timeseries_buckets_for_different_windows(self):
        self._login_admin()
        # Test 24-hour window
        resp24 = self.client.get("/api/admin/timeseries?window=86400&buckets=24")
        self.assertEqual(resp24.status_code, 200)
        buckets24 = resp24.get_json()
        self.assertEqual(len(buckets24), 24)

        # Test 7-day window
        resp7d = self.client.get("/api/admin/timeseries?window=604800&buckets=14")
        self.assertEqual(resp7d.status_code, 200)
        buckets7d = resp7d.get_json()
        self.assertEqual(len(buckets7d), 14)

        # Test 90-day window
        resp90d = self.client.get("/api/admin/timeseries?window=7776000&buckets=30")
        self.assertEqual(resp90d.status_code, 200)
        buckets90d = resp90d.get_json()
        self.assertEqual(len(buckets90d), 30)

    # ── 3. USER MANAGEMENT & USER PROFILE INSPECTION ──

    def test_admin_users_list_and_search(self):
        self._login_admin()
        resp = self.client.get("/api/admin/users?limit=25")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("users", data)
        self.assertIn("total", data)
        self.assertIn("page", data)

    def test_admin_get_user_details_inspection(self):
        self._login_admin()
        target_uid = 555
        resp = self.client.get(f"/api/admin/users/{target_uid}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertIn("user", data)
        self.assertIn("quota", data)
        self.assertIn("image_quota", data)
        self.assertIn("telemetry", data)
        self.assertEqual(data["user"]["user_id"], target_uid)
        self.assertEqual(data["quota"]["limit"], 30)
        self.assertEqual(data["quota"]["window_hours"], 5)
        self.assertEqual(data["image_quota"]["limit"], 5)

    def test_admin_prevent_self_suspension(self):
        self._login_admin(user_id=1001)
        resp = self.client.post("/api/admin/users/1001/suspend")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Cannot suspend your own admin account", resp.get_json().get("error", ""))

    def test_admin_toggle_user_suspension(self):
        self._login_admin(user_id=1001)
        target_id = 9988

        # First suspend
        resp1 = self.client.post(f"/api/admin/users/{target_id}/suspend")
        self.assertEqual(resp1.status_code, 200)
        self.assertTrue(resp1.get_json()["is_suspended"])

        # Unsuspend
        resp2 = self.client.post(f"/api/admin/users/{target_id}/suspend")
        self.assertEqual(resp2.status_code, 200)
        self.assertFalse(resp2.get_json()["is_suspended"])

    # ── 4. RATE LIMITS & RESOURCE CONTROLS ──

    def test_admin_rate_limits_endpoint(self):
        self._login_admin()
        resp = self.client.get("/api/admin/rate-limits")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertIn("config", data)
        self.assertIn("active_quotas", data)
        self.assertIn("provider_observations", data)
        self.assertEqual(data["config"]["message_limit"], 30)
        self.assertEqual(data["config"]["window_hours"], 5)
        self.assertEqual(data["config"]["image_limit"], 5)

    def test_admin_reset_user_quota(self):
        self._login_admin()
        target_id = 777
        # First consume quota
        with app._dev_quota_lock:
            app._dev_user_quotas[str(target_id)] = {
                "used": 18,
                "window_start": datetime.now(timezone.utc).isoformat(),
                "reset_at": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

        # Reset via API
        resp = self.client.post("/api/admin/rate-limits/reset", json={"user_id": target_id})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["quota"]["used"], 0)
        self.assertEqual(data["quota"]["remaining"], 30)

        # Verify audit log was recorded
        audit = admin_service.audit.get_logs(limit=10)
        actions = [l["action"] for l in audit.get("logs", [])]
        self.assertIn("reset_user_quota", actions)

    def test_admin_reset_all_quotas(self):
        self._login_admin()
        resp = self.client.post("/api/admin/rate-limits/reset", json={"all": True})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("All user quotas have been reset", data["message"])

    # ── 5. SYSTEM LOGS & ERROR MONITORING ──

    def test_admin_system_logs_aggregation(self):
        self._login_admin()
        # Record an error event
        telemetry.record_call(
            provider="sambanova",
            model="DeepSeek-V3.1",
            task="RESEARCH",
            latency_ms=250.0,
            success=False,
            error_category="RateLimit429",
            request_id="err-log-test-1"
        )

        resp = self.client.get("/api/admin/system-logs?category=all")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("events", data)
        self.assertIn("total", data)
        self.assertGreaterEqual(data["total"], 1)

    # ── 6. PROVIDER STATUS & PROBES ──

    def test_admin_providers_status(self):
        self._login_admin()
        resp = self.client.get("/api/admin/providers")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("groq", data)
        self.assertIn("gemini", data)
        self.assertIn("duckduckgo", data)

    # ── 7. SAFE CSV EXPORT & FORMULA INJECTION DEFENSE ──

    def test_safe_csv_formula_injection_defense(self):
        # Cells starting with =, +, -, @ must be prepended with '
        self.assertEqual(SafeCSVExporter.sanitize_cell("=1+1"), "'=1+1")
        self.assertEqual(SafeCSVExporter.sanitize_cell("+cmd|' /C calc'!A0"), "'+cmd|' /C calc'!A0")
        self.assertEqual(SafeCSVExporter.sanitize_cell("-2+3"), "'-2+3")
        self.assertEqual(SafeCSVExporter.sanitize_cell("@SUM(A1:A10)"), "'@SUM(A1:A10)")
        self.assertEqual(SafeCSVExporter.sanitize_cell("Normal Text"), "Normal Text")
        self.assertEqual(SafeCSVExporter.sanitize_cell(""), "")
        self.assertEqual(SafeCSVExporter.sanitize_cell(None), "")

    def test_admin_export_requests_csv(self):
        self._login_admin()
        resp = self.client.get("/api/admin/export/requests")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp.headers.get("Content-Type", ""))
        self.assertIn("Request ID", resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
