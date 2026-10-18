"""Regression tests for durable chat reads and writes (mocked PostgREST)."""
import unittest
import os
import re
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
            "id": 42, "role": "assistant", "content": "Saved answer", "created_at": "2026-10-18T00:00:00Z"
        }])
        rows = app.sb_get_messages("session", 123)
        self.assertEqual(rows[0]["content"], "Saved answer")
        self.assertEqual(rows[0]["id"], 42)
        self.assertIn("user_id=eq.123", request.call_args.args[1])
        self.assertIn("select=id,role,content,created_at", request.call_args.args[1])

    @patch("app.requests.request")
    def test_history_read_pages_past_the_supabase_row_limit(self, request):
        first_page = [
            {"id": index, "role": "assistant", "content": f"answer-{index}", "created_at": "2026-10-18T00:00:00Z"}
            for index in range(1, 501)
        ]
        last_page = [{"id": 501, "role": "assistant", "content": "answer-501", "created_at": "2026-10-18T00:00:00Z"}]
        request.side_effect = [FakeResponse(first_page), FakeResponse(last_page)]

        history = app.sb_get_messages("session", 123)

        self.assertEqual(len(history), 501)
        self.assertEqual(history[0]["id"], 1)
        self.assertEqual(history[-1]["id"], 501)
        self.assertIn("offset=500", request.call_args_list[1].args[1])

    def test_conversation_list_pagination_reaches_older_chats(self):
        app.SUPABASE_URL, app.SUPABASE_KEY = "", ""
        client = app.app.test_client()
        client.post("/api/auth/web", json={"name": "Paged Owner", "username": "paged_owner"})
        for title in ("Chat A", "Chat B", "Chat C", "Chat D", "Chat E"):
            self.assertEqual(client.post("/api/sessions", json={"title": title}).status_code, 200)

        first = client.get("/api/sessions?limit=2&offset=0").get_json()
        second = client.get("/api/sessions?limit=2&offset=2").get_json()
        third = client.get("/api/sessions?limit=2&offset=4").get_json()
        self.assertEqual(len(first["sessions"]), 2)
        self.assertTrue(first["has_more"])
        self.assertTrue(second["has_more"])
        self.assertFalse(third["has_more"])
        ids = [row["id"] for page in (first, second, third) for row in page["sessions"]]
        self.assertEqual(len(ids), 5)
        self.assertEqual(len(set(ids)), 5)
        self.assertEqual(third["next_offset"], 5)

    def test_previous_chat_encryption_key_can_read_existing_content(self):
        with patch("app._get_auth_secret_key", return_value="old-chat-key"):
            stored = app.mask_secure_hash("A saved earlier question")
        with patch("app._get_auth_secret_key", return_value="new-chat-key"), \
             patch.dict(os.environ, {"CHAT_ENCRYPTION_PREVIOUS_KEY": "old-chat-key"}):
            self.assertEqual(app.unmask_secure_hash(stored), "A saved earlier question")

    def test_unreadable_encrypted_chat_text_fails_closed_without_returning_payload(self):
        with patch("app._get_auth_secret_key", return_value="original-key"):
            stored = app.mask_secure_hash("Private historical message")
        with patch("app._get_auth_secret_key", return_value="different-key"), \
             patch.dict(os.environ, {"CHAT_ENCRYPTION_PREVIOUS_KEY": ""}):
            with self.assertRaises(app.StoredChatContentUnavailable) as raised:
                app.unmask_secure_hash(stored)
        self.assertNotIn(stored, str(raised.exception))
        self.assertNotRegex(str(raised.exception), re.compile(r"hsh_v1_"))

    @patch("app._sb_request")
    def test_chat_session_read_falls_back_cleanly_before_optional_summary_migration(self, request):
        old_schema_state = app._CHAT_SUMMARY_SCHEMA_AVAILABLE
        app._CHAT_SUMMARY_SCHEMA_AVAILABLE = None
        request.side_effect = [
            app.SupabaseSchemaUnavailable("optional migration missing"),
            FakeResponse([{"id": "session", "title": "Existing title", "user_id": 123}]),
        ]
        try:
            row = app.sb_get_session("session", 123)
            schema_after = app._CHAT_SUMMARY_SCHEMA_AVAILABLE
        finally:
            app._CHAT_SUMMARY_SCHEMA_AVAILABLE = old_schema_state
        self.assertEqual(row["title"], "Existing title")
        self.assertFalse(schema_after)
        self.assertIn("context_summary", request.call_args_list[0].kwargs["params"])
        self.assertNotIn("context_summary", request.call_args_list[1].kwargs["params"])

    @patch("app._sb_request")
    def test_rolling_summary_write_is_owner_scoped_and_encrypted(self, request):
        old_schema_state = app._CHAT_SUMMARY_SCHEMA_AVAILABLE
        app._CHAT_SUMMARY_SCHEMA_AVAILABLE = True
        request.return_value = FakeResponse([{"id": "session"}])
        try:
            saved = app.sb_update_session_summary("session", 123, "The user is building a study app.", 81)
        finally:
            app._CHAT_SUMMARY_SCHEMA_AVAILABLE = old_schema_state
        self.assertTrue(saved)
        self.assertIn("id=eq.session&user_id=eq.123", request.call_args.kwargs["params"])
        self.assertIn("summary_through_message_id=is.null", request.call_args.kwargs["params"])
        payload = request.call_args.kwargs["json_body"]
        self.assertTrue(payload["context_summary"].startswith("hsh_v1_"))
        self.assertNotIn("study app", payload["context_summary"])
        self.assertEqual(payload["summary_through_message_id"], 81)

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

    def test_workspace_metadata_is_owner_scoped_and_filterable(self):
        app.SUPABASE_URL, app.SUPABASE_KEY = "", ""
        owner = app.app.test_client()
        other = app.app.test_client()
        owner.post("/api/auth/web", json={"name": "Workspace Owner", "username": "workspace_owner"})
        created = owner.post("/api/sessions", json={"title": "Saved study"})
        session_id = created.get_json()["id"]

        self.assertEqual(owner.patch(f"/api/sessions/{session_id}", json={"is_saved": True, "is_pinned": True}).status_code, 200)
        listed = owner.get("/api/sessions?view=saved").get_json()
        self.assertTrue(any(row["id"] == session_id for row in listed))
        other.post("/api/auth/web", json={"name": "Other User", "username": "other_workspace_user"})
        self.assertEqual(other.patch(f"/api/sessions/{session_id}", json={"is_archived": True}).status_code, 404)

    def test_workspace_metadata_rejects_non_boolean_values(self):
        with self.assertRaises(ValueError):
            app.sb_update_session_metadata("session", 123, {"is_saved": "yes"})

    @patch("app._sb_request")
    def test_session_list_gracefully_falls_back_on_schema_error(self, mock_sb):
        mock_sb.side_effect = [
            app.SupabaseSchemaUnavailable("column chat_sessions.last_message_at does not exist"),
            FakeResponse([{"id": "session-1", "title": "Legacy chat", "created_at": "2026-10-18T10:00:00Z"}]),
        ]
        sessions = app.sb_list_sessions(123)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["id"], "session-1")
        self.assertEqual(sessions[0]["title"], "Legacy chat")
        self.assertFalse(sessions[0]["is_pinned"])

    @patch("app._sb_request")
    def test_messages_read_gracefully_falls_back_on_schema_error(self, mock_sb):
        mock_sb.side_effect = [
            app.SupabaseSchemaUnavailable("column chat_messages.user_id does not exist"),
            FakeResponse([{"id": 1, "role": "user", "content": "Hello", "created_at": "2026-10-18T10:00:00Z"}]),
        ]
        messages = app.sb_get_messages("session-1", 123)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["content"], "Hello")

    @patch("app._sb_request")
    @patch("app.unmask_secure_hash", side_effect=app.StoredChatContentUnavailable("rotated secret"))
    def test_session_list_and_messages_gracefully_handle_unmask_failure(self, _unmask, mock_sb):
        mock_sb.return_value = FakeResponse([
            {"id": "session-rot", "title": "hsh_v1_rot", "created_at": "2026-10-18T10:00:00Z",
             "is_pinned": False, "is_saved": False, "is_archived": False, "last_message_at": None, "updated_at": None}
        ])
        sessions = app.sb_list_sessions(123)
        self.assertEqual(sessions[0]["title"], "Study Session")

        mock_sb.return_value = FakeResponse([
            {"id": 10, "role": "user", "content": "hsh_v1_secret", "created_at": "2026-10-18T10:00:00Z"}
        ])
        messages = app.sb_get_messages("session-rot", 123)
        self.assertEqual(messages[0]["content"], "[Encrypted message from previous session]")


if __name__ == "__main__":
    unittest.main()
