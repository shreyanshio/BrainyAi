"""Comprehensive test suite covering production reliability, memory isolation, context, quotas, and API contracts."""
import json
import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

import app
import study_bot
import security


class FullSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.app.config["TESTING"] = True
        cls.client = app.app.test_client()

    def setUp(self):
        # Reset local test state
        self.client = app.app.test_client()
        app.MEM_MESSAGES.clear()
        app.MEM_SESSIONS.clear()
        app._dev_user_quotas.clear()
        security.rate_limits.clear()
        # Save original Supabase configuration
        self.orig_url = app.SUPABASE_URL
        self.orig_key = app.SUPABASE_KEY
        # Set to empty so dev fallback is used unless test explicitly mocks Supabase
        app.SUPABASE_URL = ""
        app.SUPABASE_KEY = ""

    def tearDown(self):
        app.SUPABASE_URL = self.orig_url
        app.SUPABASE_KEY = self.orig_key
        app.MEM_MESSAGES.clear()
        app.MEM_SESSIONS.clear()
        app._dev_user_quotas.clear()
        security.rate_limits.clear()

    # ── 1. SUPABASE PERSISTENCE & ERROR DETECTION ─────────────────────
    def test_unconfigured_uses_safe_dev_fallback(self):
        """When Supabase credentials are not configured, dev fallback works safely without crashing."""
        user_id = 888101
        session = app.sb_create_session(user_id, "Test Dev Session")
        self.assertIn("id", session)
        self.assertEqual(session["title"], "Test Dev Session")

        app.sb_insert_message(session["id"], "user", "Hello world")
        msgs = app.sb_get_recent_messages(session["id"], 5)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["content"], "Hello world")

        quota = app.get_user_quota(user_id)
        self.assertEqual(quota["used"], 0)
        self.assertEqual(quota["limit"], app.GLOBAL_MESSAGE_LIMIT)

    @patch("app.requests.request")
    def test_configured_supabase_failure_raises_visibly(self, mock_req):
        """When Supabase is configured and fails, SupabaseOperationError is raised and not masked."""
        from requests import HTTPError
        app.SUPABASE_URL = "https://example.supabase.co"
        app.SUPABASE_KEY = "test-key"

        fake_resp = MagicMock()
        fake_resp.raise_for_status.side_effect = HTTPError("PostgREST connection failure")
        mock_req.return_value = fake_resp

        with self.assertRaises(app.SupabaseOperationError):
            app.sb_insert_message("test-sess", "user", "Secret content")

        with self.assertRaises(app.SupabaseOperationError):
            app.sb_create_session(12345, "Test Session")

    # ── 2. CONVERSATION CONTEXT PRESERVATION ACROSS TURNS ──────────────
    def test_chronological_conversation_context_preservation(self):
        """Follow-up questions maintain chronological context in order without duplicates."""
        user_id = 999201
        sess = app.sb_create_session(user_id, "Photosynthesis Discussion")
        sess_id = sess["id"]

        # Turn 1: User asks question
        app.sb_insert_message(sess_id, "user", "What is photosynthesis?")
        # Turn 1: Assistant replies
        app.sb_insert_message(sess_id, "assistant", "Photosynthesis is the process by which plants use sunlight to synthesize nutrients.")
        # Turn 2: User asks follow-up
        app.sb_insert_message(sess_id, "user", "What about the dark reaction?")

        messages = app.sb_get_recent_messages(sess_id, limit=15)
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "What is photosynthesis?")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertIn("Photosynthesis is", messages[1]["content"])
        self.assertEqual(messages[2]["role"], "user")
        self.assertEqual(messages[2]["content"], "What about the dark reaction?")

    # ── 3. STRICT PERSONAL MEMORY ISOLATION ACROSS USERS ───────────────
    def test_personal_memory_isolation_across_users(self):
        """User A's preferences, notes, and study facts never leak to User B."""
        user_a = 700101
        user_b = 700202

        study_bot.save_user_memory(user_a, {"level": "Advanced", "preferences": {"focus": "Organic Chemistry"}, "liked_notes": ["Benzene aromaticity rules"]})
        study_bot.save_user_memory(user_b, {"level": "Beginner", "preferences": {"focus": "Calculus I"}, "liked_notes": ["L'Hopital rule derivative ratios"]})

        data_a = study_bot.get_user_data(user_a)
        data_b = study_bot.get_user_data(user_b)

        self.assertEqual(data_a.get("preferences", {}).get("focus"), "Organic Chemistry")
        self.assertEqual(data_b.get("preferences", {}).get("focus"), "Calculus I")

        liked_a = study_bot.get_liked_context(user_a)
        liked_b = study_bot.get_liked_context(user_b)

        self.assertIn("Benzene aromaticity", liked_a)
        self.assertNotIn("Calculus", liked_a)
        self.assertIn("L'Hopital rule", liked_b)
        self.assertNotIn("Benzene", liked_b)

    # ── 4. RATE LIMIT (BURST) VS QUOTA (5-HOUR WINDOW) SEPARATION ─────
    def test_rate_limit_burst_versus_quota_window(self):
        """Burst rate limit (10 req/min) returns CHAT_RATE_LIMITED; 5h quota returns QUOTA_EXCEEDED."""
        user_id = 555301
        # Fill user quota up to 30
        for _ in range(30):
            allowed, st = app.consume_user_quota(user_id)
            self.assertTrue(allowed)

        # 31st request triggers quota exhaustion
        allowed, st = app.consume_user_quota(user_id)
        self.assertFalse(allowed)
        self.assertEqual(st["used"], 30)
        self.assertEqual(st["remaining"], 0)

        # Burst rate limiter test independently
        key = f"user_{user_id}_burst"
        for _ in range(10):
            self.assertTrue(security.check_rate_limit(key, limit=10, window=60))
        # 11th request triggers rate limit
        self.assertFalse(security.check_rate_limit(key, limit=10, window=60))

    # ── 5. API CONTRACT TESTS ACROSS REGISTERED ROUTES ────────────────
    def test_api_config_contract(self):
        """GET /api/config returns 200 with public environment keys."""
        resp = self.client.get("/api/config")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("google_client_id", data)
        self.assertIn("telegram_bot_username", data)

    def test_api_models_contract(self):
        """GET /api/models returns 200 with list of available study models."""
        resp = self.client.get("/api/models")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data, list)
        self.assertTrue(any(m["id"] == "brainy-balanced" for m in data))

    def test_api_auth_me_unauthorized(self):
        """GET /api/auth/me returns 401 when no session exists."""
        resp = self.client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 401)

    def test_api_auth_web_and_me(self):
        """POST /api/auth/web logs in user and GET /api/auth/me returns user details."""
        resp = self.client.post("/api/auth/web", json={"name": "Alice Study", "username": "alicestudy"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("authenticated"))
        self.assertEqual(data["user"]["first_name"], "Alice Study")

        # Now test /api/auth/me
        me_resp = self.client.get("/api/auth/me")
        self.assertEqual(me_resp.status_code, 200)
        me_data = me_resp.get_json()
        self.assertEqual(me_data["user"]["first_name"], "Alice Study")

    @patch("app._is_production", return_value=True)
    def test_unverified_name_login_is_disabled_in_production(self, _production):
        response = self.client.post("/api/auth/web", json={"name": "Impersonated User"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["code"], "UNVERIFIED_LOGIN_DISABLED")

    def test_api_usage_contract(self):
        """GET /api/usage returns 200 with quota fields for logged-in user."""
        # Log in
        self.client.post("/api/auth/web", json={"name": "Bob Student", "username": "bobstudent"})
        resp = self.client.get("/api/usage")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("used", data)
        self.assertIn("limit", data)
        self.assertIn("remaining", data)
        self.assertIn("reset_at", data)
        self.assertEqual(data["window_hours"], 5)

    def test_api_sessions_lifecycle_contract(self):
        """POST, GET, PATCH, DELETE /api/sessions lifecycle contract."""
        self.client.post("/api/auth/web", json={"name": "Charlie", "username": "charlie"})

        # Create session
        create_resp = self.client.post("/api/sessions", json={"title": "Thermodynamics"})
        self.assertEqual(create_resp.status_code, 200)
        sess = create_resp.get_json()
        sess_id = sess["id"]
        self.assertEqual(sess["title"], "Thermodynamics")

        # List sessions
        list_resp = self.client.get("/api/sessions")
        self.assertEqual(list_resp.status_code, 200)
        sessions = list_resp.get_json()
        self.assertTrue(any(s["id"] == sess_id for s in sessions))

        # Rename session
        patch_resp = self.client.patch(f"/api/sessions/{sess_id}", json={"title": "Thermodynamics Rev 1"})
        self.assertEqual(patch_resp.status_code, 200)

        # Get chat history
        history_resp = self.client.get(f"/api/chat/{sess_id}")
        self.assertEqual(history_resp.status_code, 200)
        history = history_resp.get_json()
        self.assertEqual(history["title"], "Thermodynamics Rev 1")

        # Delete session
        del_resp = self.client.delete(f"/api/sessions/{sess_id}")
        self.assertEqual(del_resp.status_code, 200)

    @patch("study_bot.ai_call")
    def test_api_chat_send_contract(self, mock_ai_call):
        """POST /api/chat/send returns formatted assistant reply and advances quota."""
        mock_ai_call.return_value = "Newton's second law is F = ma."
        self.client.post("/api/auth/web", json={"name": "Diana", "username": "diana"})

        resp = self.client.post("/api/chat/send", json={
            "message": "Explain Newton's second law",
            "model": "brainy-balanced",
            "answer_length": "short"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["role"], "assistant")
        self.assertIn("F = ma", data["content"])
        self.assertIn("session_id", data)
        self.assertEqual(data["usage"]["used"], 1)

    @patch("study_bot.ai_stream")
    def test_api_chat_stream_contract(self, mock_ai_stream):
        """POST /api/chat/stream returns NDJSON stream with start, delta, and done events."""
        def fake_stream(*args, **kwargs):
            yield "Kinetic energy "
            yield "is 0.5 * m * v^2."
        mock_ai_stream.side_effect = fake_stream

        self.client.post("/api/auth/web", json={"name": "Evan", "username": "evan"})
        resp = self.client.post("/api/chat/stream", json={
            "message": "Formula for kinetic energy",
            "model": "brainy-fast",
            "answer_length": "short"
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/x-ndjson", resp.content_type)

        lines = [json.loads(line) for line in resp.data.decode("utf-8").strip().split("\n") if line.strip()]
        types = [l.get("type") for l in lines]
        self.assertIn("start", types)
        self.assertIn("delta", types)
        self.assertIn("done", types)

    def test_api_admin_health_contract(self):
        """GET /api/admin/health enforces admin auth: 401 when unauthenticated, 200 with admin session."""
        resp = self.client.get("/api/admin/health")
        self.assertEqual(resp.status_code, 401)

        # Authenticate as admin
        admin_id = next(iter(app.ADMIN_USER_IDS)) if app.ADMIN_USER_IDS else 999999
        with self.client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["first_name"] = "Admin"
            sess["username"] = "admin"
            sess["role"] = "admin"

        orig_ids = set(app.ADMIN_USER_IDS)
        app.ADMIN_USER_IDS.add(admin_id)
        try:
            admin_resp = self.client.get("/api/admin/health")
            self.assertEqual(admin_resp.status_code, 200)
            data = admin_resp.get_json()
            self.assertIn("status", data)
            self.assertIn("timestamp", data)
        finally:
            app.ADMIN_USER_IDS = orig_ids

    def test_google_auth_missing_credential(self):
        """POST /api/auth/google returns 400 when credential token is missing."""
        resp = self.client.post("/api/auth/google", json={})
        self.assertEqual(resp.status_code, 400)

    @patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "brainyai-test.apps.googleusercontent.com"})
    @patch("requests.get")
    def test_google_auth_success_with_tokeninfo(self, mock_get):
        """POST /api/auth/google verifies id_token via Google tokeninfo fallback."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "sub": "10987654321",
            "email": "scholar@example.com",
            "email_verified": "true",
            "name": "Jane Scholar",
            "picture": "https://example.com/avatar.jpg",
            "aud": "brainyai-test.apps.googleusercontent.com",
            "iss": "https://accounts.google.com",
            "exp": str(int(datetime.now(timezone.utc).timestamp()) + 600),
        }
        mock_get.return_value = mock_resp

        resp = self.client.post("/api/auth/google", json={"credential": "mock_valid_id_token"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("authenticated"))
        self.assertEqual(data["user"]["first_name"], "Jane Scholar")
        self.assertEqual(data["user"]["email"], "scholar@example.com")
        self.assertIn("token", data)
        authenticated = app.app.test_client().get("/api/auth/me", headers={"Authorization": f"Bearer {data['token']}"})
        self.assertEqual(authenticated.status_code, 200)
        self.assertEqual(authenticated.get_json()["user"]["id"], data["user"]["id"])

    @patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "brainyai-test.apps.googleusercontent.com"})
    @patch("requests.get")
    def test_google_auth_rejects_token_for_another_client(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "sub": "subject-123", "email": "student@example.com", "email_verified": True,
            "aud": "other-client.apps.googleusercontent.com", "iss": "https://accounts.google.com",
            "exp": str(int(datetime.now(timezone.utc).timestamp()) + 600),
        }
        mock_get.return_value = mock_resp
        response = self.client.post("/api/auth/google", json={"credential": "wrong-audience-token"})
        self.assertEqual(response.status_code, 401)

    @patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "brainyai-test.apps.googleusercontent.com"})
    @patch("requests.get")
    def test_legacy_google_access_token_flow_checks_client_and_profile(self, mock_get):
        rejected_id_token = MagicMock(status_code=400)
        access_info = MagicMock(status_code=200)
        access_info.json.return_value = {
            "issued_to": "brainyai-test.apps.googleusercontent.com",
            "user_id": "google-sub-456",
            "expires_in": "300",
        }
        user_info = MagicMock(status_code=200)
        user_info.json.return_value = {
            "sub": "google-sub-456", "email": "fallback@example.com",
            "email_verified": True, "name": "Fallback Scholar",
        }
        mock_get.side_effect = [rejected_id_token, access_info, user_info]
        response = self.client.post("/api/auth/google", json={"credential": "legacy-access-token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["user"]["email"], "fallback@example.com")

    @patch("app.sb_record_login")
    @patch("study_bot.load_user_into_memory")
    @patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "brainyai-test.apps.googleusercontent.com"})
    @patch("requests.get")
    def test_google_auth_resilient_to_background_failures(self, mock_get, mock_mem, mock_rec):
        """POST /api/auth/google succeeds even if background audit/memory raises an error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "sub": "999888777",
            "email": "resilient@example.com",
            "email_verified": True,
            "name": "Resilient Scholar",
            "aud": "brainyai-test.apps.googleusercontent.com",
            "iss": "accounts.google.com",
            "exp": str(int(datetime.now(timezone.utc).timestamp()) + 600),
        }
        mock_get.return_value = mock_resp
        mock_mem.side_effect = RuntimeError("Supabase connection timeout")
        mock_rec.side_effect = RuntimeError("Supabase RLS violation")

        resp = self.client.post("/api/auth/google", json={"credential": "token_with_sb_down"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("authenticated"))
        self.assertEqual(data["user"]["first_name"], "Resilient Scholar")

    @patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "brainyai-test.apps.googleusercontent.com"})
    @patch("requests.get")
    def test_google_auth_invalid_token(self, mock_get):
        """POST /api/auth/google returns 401 when token verification fails."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Invalid Value"
        mock_get.return_value = mock_resp

        resp = self.client.post("/api/auth/google", json={"credential": "invalid_junk_token"})
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()

