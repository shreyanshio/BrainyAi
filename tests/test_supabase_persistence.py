"""Regression tests for durable chat reads and writes (mocked PostgREST)."""
import unittest
from unittest.mock import patch
from requests import HTTPError

import app


class FakeResponse:
    def __init__(self, rows=None, status_error=None):
        self.rows = rows if rows is not None else []
        self.status_error = status_error
        self.headers = {}

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        return self.rows


class SupabasePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.url, self.key = app.SUPABASE_URL, app.SUPABASE_KEY
        app.SUPABASE_URL, app.SUPABASE_KEY = "https://example.supabase.co", "test-key"
        app.MEM_MESSAGES.clear()
        app.MEM_SESSIONS.clear()

    def tearDown(self):
        app.SUPABASE_URL, app.SUPABASE_KEY = self.url, self.key
        app.MEM_MESSAGES.clear()
        app.MEM_SESSIONS.clear()

    @patch("app.requests.request")
    def test_successful_empty_database_read_does_not_merge_cache(self, request):
        app.MEM_MESSAGES["session"] = [{"role": "user", "content": "stale"}]
        request.return_value = FakeResponse([])
        self.assertEqual(app.sb_get_recent_messages("session", user_id=123), [])
        self.assertIn("user_id=eq.123", request.call_args.args[1])

    @patch("app.requests.request")
    def test_message_write_failure_is_not_reported_as_success(self, request):
        request.return_value = FakeResponse(status_error=HTTPError("schema failure"))
        with self.assertRaises(app.SupabaseOperationError):
            app.sb_insert_message("session", "user", "private test text", user_id=123)
        self.assertEqual(app.MEM_MESSAGES.get("session", []), [])

    @patch("app.requests.request")
    def test_message_is_saved_with_owner_and_reloaded(self, request):
        request.side_effect = [FakeResponse([])]
        app.sb_insert_message("session", "assistant", "Saved answer", user_id=123)
        payload = request.call_args.kwargs["json"]
        self.assertEqual(payload["user_id"], 123)
        self.assertEqual(payload["session_id"], "session")

        request.side_effect = None
        request.return_value = FakeResponse([{
            "role": "assistant", "content": "Saved answer", "created_at": "2026-10-18T00:00:00Z"
        }])
        rows = app.sb_get_messages("session", 123)
        self.assertEqual(rows[0]["content"], "Saved answer")
        self.assertIn("user_id=eq.123", request.call_args.args[1])

    @patch("app.requests.request")
    def test_public_health_reports_database_connectivity_without_secrets(self, request):
        request.return_value = FakeResponse([])
        result = app.app.test_client().get("/api/health")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json()["database"]["status"], "connected")
        self.assertNotIn("test-key", result.get_data(as_text=True))

    @patch("app.requests.request")
    def test_public_health_reports_database_outage(self, request):
        request.return_value = FakeResponse(status_error=HTTPError("connection failed"))
        result = app.app.test_client().get("/api/health")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json()["database"]["status"], "unavailable")

    @patch("app.requests.request")
    def test_session_creation_requires_a_returned_row(self, request):
        request.return_value = FakeResponse([])
        with self.assertRaises(app.SupabaseOperationError):
            app.sb_create_session(123, "test")
        self.assertEqual(app.MEM_SESSIONS.get(123, []), [])

    def test_supabase_secret_and_legacy_keys_use_compatible_headers(self):
        app.SUPABASE_KEY = "sb_secret_test-key"
        self.assertEqual(app._sb_headers()["apikey"], "sb_secret_test-key")
        self.assertNotIn("Authorization", app._sb_headers())
        app.SUPABASE_KEY = "eyJlegacy-service-role"
        self.assertEqual(app._sb_headers()["Authorization"], "Bearer eyJlegacy-service-role")

    def test_users_cannot_read_rename_or_delete_another_users_session(self):
        app.SUPABASE_URL, app.SUPABASE_KEY = "", ""
        first = app.app.test_client()
        second = app.app.test_client()
        first.post("/api/auth/web", json={"name": "Owner One", "username": "owner_one"})
        created = first.post("/api/sessions", json={"title": "Private conversation"})
        session_id = created.get_json()["id"]
        second.post("/api/auth/web", json={"name": "Owner Two", "username": "owner_two"})

        self.assertEqual(second.get(f"/api/chat/{session_id}").status_code, 404)
        self.assertEqual(second.patch(f"/api/sessions/{session_id}", json={"title": "Stolen"}).status_code, 404)
        self.assertEqual(second.delete(f"/api/sessions/{session_id}").status_code, 404)
        listed = second.get("/api/sessions").get_json()
        self.assertFalse(any(row["id"] == session_id for row in listed))


if __name__ == "__main__":
    unittest.main()
