"""Deterministic regression tests for shared rate limits and DDG fallback behavior."""
import os
import json
import threading
import unittest
from unittest.mock import Mock, patch

import security
import study_bot
import app


class ReliabilityContractTests(unittest.TestCase):
    def test_database_history_error_does_not_fall_back_to_new_chat_context(self):
        with app.app.test_request_context("/api/chat/stream"):
            with patch("app.is_user_suspended", return_value=False), \
                 patch("app.sb_get_session", return_value={"id": "00000000-0000-0000-0000-000000000123", "title": "Existing"}), \
                 patch("app.sanitize_input", side_effect=lambda value: value), \
                 patch("study_bot.detect_intent", return_value=("joke", None)), \
                 patch("app.check_rate_limit", return_value=True), \
                 patch("app.consume_user_quota", return_value=(True, {"used": 1, "remaining": 29, "reset_at": "later"})), \
                 patch("app.sb_insert_message"), \
                 patch("app.sb_get_recent_messages", side_effect=app.SupabaseOperationError("offline")), \
                 patch("app.refund_user_quota") as refund:
                prepared, response, status = app._prepare_chat_request({
                    "session_id": "00000000-0000-0000-0000-000000000123",
                    "message": "And what about the second feature?",
                }, 77, "Student", "student", "127.0.0.1")

        self.assertIsNone(prepared)
        self.assertEqual(status, 503)
        self.assertEqual(response.get_json()["code"], "CHAT_HISTORY_UNAVAILABLE")
        refund.assert_called_once_with(77)

    def test_persisted_current_question_is_not_duplicated_if_retry_write_fails(self):
        message = "What about the second feature?"
        history = [
            {"role": "user", "content": "We discussed three features."},
            {"role": "assistant", "content": "The second one was chat memory."},
            {"role": "user", "content": message},
        ]
        with app.app.test_request_context("/api/chat/stream"):
            with patch("app.is_user_suspended", return_value=False), \
                 patch("app.sb_get_session", return_value={"id": "00000000-0000-0000-0000-000000000123", "title": "Existing"}), \
                 patch("app.sanitize_input", side_effect=lambda value: value), \
                 patch("study_bot.detect_intent", return_value=("joke", None)), \
                 patch("app.check_rate_limit", return_value=True), \
                 patch("app.consume_user_quota", return_value=(True, {"used": 1, "remaining": 29, "reset_at": "later"})), \
                 patch("app.sb_insert_message", side_effect=app.SupabaseOperationError("write failed")), \
                 patch("app.sb_get_recent_messages", return_value=history), \
                 patch("study_bot.load_user_into_memory"), \
                 patch("study_bot.get_user_data", return_value={}), \
                 patch("study_bot.get_liked_context", return_value=""), \
                 patch("study_bot.is_offtopic_chat", return_value=False):
                prepared, response, status = app._prepare_chat_request({
                    "session_id": "00000000-0000-0000-0000-000000000123",
                    "message": message,
                }, 77, "Student", "student", "127.0.0.1")

        self.assertIsNone(response)
        self.assertEqual(status, 200)
        self.assertEqual(prepared["messages_context"], history)
        self.assertEqual(sum(1 for item in prepared["messages_context"] if item["role"] == "user" and item["content"] == message), 1)

    def test_rolling_summary_advances_only_through_summarized_messages(self):
        old_schema_state = app._CHAT_SUMMARY_SCHEMA_AVAILABLE
        app._CHAT_SUMMARY_SCHEMA_AVAILABLE = True
        pending = [
            {"id": index + 1, "role": "user" if index % 2 == 0 else "assistant", "content": f"turn {index + 1}"}
            for index in range(41)
        ]
        worker_lock = threading.Lock()
        worker_lock.acquire()
        try:
            with patch("app.sb_get_session", side_effect=[
                    {"id": "session", "context_summary": None, "summary_through_message_id": None},
                    {"id": "session", "context_summary": "Updated summary", "summary_through_message_id": 17},
                 ]), \
                 patch("app.sb_get_messages_after", side_effect=[pending, pending[17:]]), \
                 patch("study_bot.ai_call", return_value="Updated summary") as summarize, \
                 patch("study_bot.clean_response", side_effect=lambda value: value), \
                 patch("app.sb_update_session_summary", return_value=True) as save_summary:
                app._refresh_chat_summary("session", 77, worker_lock)
        finally:
            app._CHAT_SUMMARY_SCHEMA_AVAILABLE = old_schema_state

        summarize.assert_called_once()
        save_summary.assert_called_once_with(
            "session", 77, "Updated summary", 17, expected_previous_id=None
        )
        self.assertFalse(worker_lock.locked())

    def test_prepared_context_combines_owned_summary_and_newer_turns(self):
        session_id = "00000000-0000-0000-0000-000000000123"
        current = "What about the second feature?"
        recent = [
            {"role": "assistant", "content": "We chose persistent chat memory."},
            {"role": "user", "content": current},
        ]
        with app.app.test_request_context("/api/chat/stream"):
            with patch("app.is_user_suspended", return_value=False), \
                 patch("app.sb_get_session", return_value={
                    "id": session_id,
                    "title": "Study project",
                    "context_summary": "The user is building a study app with Python and Supabase.",
                    "summary_through_message_id": 80,
                 }), \
                 patch("app.sanitize_input", side_effect=lambda value: value), \
                 patch("study_bot.detect_intent", return_value=("joke", None)), \
                 patch("app.check_rate_limit", return_value=True), \
                 patch("app.consume_user_quota", return_value=(True, {"used": 1, "remaining": 29, "reset_at": "later"})), \
                 patch("app.sb_insert_message"), \
                 patch("app.sb_get_recent_messages", return_value=recent) as read_history, \
                 patch("study_bot.load_user_into_memory"), \
                 patch("study_bot.get_user_data", return_value={}), \
                 patch("study_bot.get_liked_context", return_value=""), \
                 patch("study_bot.is_offtopic_chat", return_value=False):
                prepared, response, status = app._prepare_chat_request({
                    "session_id": session_id,
                    "message": current,
                }, 77, "Student", "student", "127.0.0.1")

        self.assertIsNone(response)
        self.assertEqual(status, 200)
        self.assertIn("Python and Supabase", prepared["system_prompt"])
        self.assertEqual(prepared["messages_context"], recent)
        self.assertEqual(sum(1 for item in prepared["messages_context"] if item.get("content") == current), 1)
        read_history.assert_called_once_with(session_id, 41, user_id=77, after_id=80)

    def test_code_debug_prompt_tile_streams_without_punctuation_rejection(self):
        old_url, old_key = app.SUPABASE_URL, app.SUPABASE_KEY
        old_env = os.environ.get("RAILWAY_SERVICE_ID")
        app.SUPABASE_URL, app.SUPABASE_KEY = "", ""
        os.environ.pop("RAILWAY_SERVICE_ID", None)
        client = app.app.test_client()
        app.MEM_MESSAGES.clear()
        app.MEM_SESSIONS.clear()
        app._dev_user_quotas.clear()
        prompt = (
            "Analyze this code snippet, point out bugs or inefficiencies, and provide the optimal "
            "implementation with time & space complexity: if (a && b) { return x & 1; }"
        )
        try:
            client.post("/api/auth/web", json={"name": "Code Student", "username": "code_student"})
            with patch("security.check_rate_limit", return_value=True), \
                 patch("app.check_rate_limit", return_value=True), \
                 patch("study_bot.ai_stream", return_value=iter(["Code analysis ready."])), \
                 patch("study_bot.is_offtopic_chat", return_value=False):
                response = client.post("/api/chat/stream", json={"message": prompt}, buffered=True)

            self.assertEqual(response.status_code, 200)
            events = [json.loads(line) for line in response.get_data(as_text=True).splitlines()]
            self.assertFalse(any(event.get("type") == "error" for event in events))
            self.assertTrue(any(event.get("type") == "delta" for event in events))
            session_id = next(event["session_id"] for event in events if event.get("type") == "start")
            self.assertEqual(app.MEM_MESSAGES[session_id][0]["content"], prompt)
        finally:
            app.SUPABASE_URL, app.SUPABASE_KEY = old_url, old_key
            if old_env is not None:
                os.environ["RAILWAY_SERVICE_ID"] = old_env
            else:
                os.environ.pop("RAILWAY_SERVICE_ID", None)
            app.MEM_MESSAGES.clear()
            app.MEM_SESSIONS.clear()
            app._dev_user_quotas.clear()

    def test_full_chat_context_returns_every_turn_in_order(self):
        old_url, old_key = app.SUPABASE_URL, app.SUPABASE_KEY
        session_id = "context-history-contract"
        old_messages = app.MEM_MESSAGES.get(session_id)
        app.SUPABASE_URL, app.SUPABASE_KEY = "", ""
        app.MEM_MESSAGES[session_id] = [
            {"role": "user" if index % 2 == 0 else "assistant", "content": f"turn-{index}"}
            for index in range(40)
        ]
        try:
            messages = app.sb_get_recent_messages(session_id, limit=None)
            self.assertEqual(len(messages), 40)
            self.assertEqual(messages[0]["content"], "turn-0")
            self.assertEqual(messages[-1]["content"], "turn-39")
        finally:
            app.SUPABASE_URL, app.SUPABASE_KEY = old_url, old_key
            if old_messages is None:
                app.MEM_MESSAGES.pop(session_id, None)
            else:
                app.MEM_MESSAGES[session_id] = old_messages

    @patch("app.is_user_suspended", return_value=False)
    @patch("app.sb_get_session", return_value={"id": "00000000-0000-0000-0000-000000000123", "title": "Existing chat"})
    @patch("app.sanitize_input", side_effect=lambda value: value)
    @patch("app.is_blacklisted", return_value=False)
    @patch("app.check_rate_limit", return_value=True)
    @patch("app.consume_user_quota", return_value=(True, {"used": 1, "remaining": 29, "reset_at": "later"}))
    @patch("app.sb_insert_message")
    @patch("app.sb_get_recent_messages")
    @patch("study_bot.load_user_into_memory")
    @patch("study_bot.get_user_data", return_value={})
    @patch("study_bot.get_liked_context", return_value="")
    @patch("study_bot.detect_intent", return_value=("joke", None))
    @patch("study_bot.is_offtopic_chat", return_value=False)
    def test_special_intents_keep_existing_chat_context(
        self, _offtopic, _intent, _liked, _user_data, _load_memory,
        recent_messages, _insert, _quota, _limit, _blacklist, _sanitize, _session, _suspended
    ):
        history = [
            {"role": "user", "content": "We are studying photosynthesis"},
            {"role": "assistant", "content": "Plants convert light into chemical energy."},
            {"role": "user", "content": "Tell me a joke about that"},
        ]
        recent_messages.return_value = history
        prepared, error, status = app._prepare_chat_request({
            "session_id": "00000000-0000-0000-0000-000000000123",
            "message": "Tell me a joke about that",
        }, 99, "Student", "student", "127.0.0.1")

        self.assertIsNone(error)
        self.assertEqual(status, 200)
        self.assertEqual(prepared["messages_context"], history)

    @patch.dict(os.environ, {"ENVIRONMENT": "production", "SUPABASE_URL": "https://db.example", "SUPABASE_SERVICE_KEY": "test"})
    @patch("security.requests.post", side_effect=TimeoutError("offline"))
    def test_production_shared_limiter_uses_local_protection_when_rpc_fails(self, post):
        identifier = "test-ip-rpc-failure"
        security.rate_limits.pop(identifier, None)
        security._shared_limiter_retry_at = 0
        self.assertTrue(security.check_rate_limit(identifier))
        self.assertEqual(post.call_count, 1)
        self.assertEqual(len(security.rate_limits[identifier]), 1)

    @patch.dict(os.environ, {"ENVIRONMENT": "production", "SUPABASE_URL": "", "SUPABASE_SERVICE_KEY": ""})
    def test_production_limiter_uses_local_protection_without_shared_store(self):
        identifier = "test-ip-no-shared-store"
        security.rate_limits.pop(identifier, None)
        self.assertTrue(security.check_rate_limit(identifier))
        self.assertEqual(len(security.rate_limits[identifier]), 1)

    @patch("app.get_user_quota")
    @patch("app._quota_rpc", side_effect=app.SupabaseOperationError("RPC unavailable"))
    def test_product_quota_never_uses_non_atomic_read_modify_write(self, _rpc, get_quota):
        old_url, old_key = app.SUPABASE_URL, app.SUPABASE_KEY
        app.SUPABASE_URL, app.SUPABASE_KEY = "https://db.example", "private-test-key"
        try:
            with self.assertRaises(app.SupabaseOperationError):
                app.consume_user_quota(123)
            get_quota.assert_not_called()
        finally:
            app.SUPABASE_URL, app.SUPABASE_KEY = old_url, old_key

    @patch("app.sb_create_session", side_effect=app.SupabaseOperationError("database unavailable"))
    @patch("study_bot.ai_stream", return_value=iter(["A real answer."]))
    def test_stream_delivers_answer_when_new_session_cannot_be_saved(self, _stream, _create_session):
        client = app.app.test_client()
        client.post("/api/auth/web", json={"name": "Reliability", "username": "reliability"})
        response = client.post("/api/chat/stream", json={"message": "Explain a concept"})

        events = [__import__("json").loads(line) for line in response.data.decode().splitlines() if line]
        self.assertEqual(response.status_code, 200)
        self.assertIn("delta", [event["type"] for event in events])
        done = next(event for event in events if event["type"] == "done")
        self.assertTrue(done["persistence_warning"])
        self.assertIsNone(done["session_id"])

    @patch.object(study_bot, "TAVILY_API_KEYS", [])
    @patch("study_bot.requests.get")
    def test_duckduckgo_instant_answer_normalizes_real_source(self, get):
        response = Mock()
        response.json.return_value = {
            "AbstractText": "A factual abstract.",
            "AbstractURL": "https://example.org/article",
            "RelatedTopics": [{"Text": "Related fact", "FirstURL": "javascript:alert(1)"}],
        }
        get.return_value = response

        result = study_bot.web_search("sample query")

        self.assertIn("A factual abstract.", result)
        self.assertIn("https://example.org/article", result)
        self.assertNotIn("javascript:", result)
        self.assertEqual(get.call_count, 1)

    @patch.object(study_bot, "TAVILY_API_KEYS", [])
    @patch("study_bot.requests.get")
    def test_empty_instant_answer_is_truthful_and_does_not_scrape(self, get):
        response = Mock()
        response.json.return_value = {"RelatedTopics": []}
        get.return_value = response

        result = study_bot.web_search("query with no instant answer")

        self.assertIn("did not return a useful result", result)
        self.assertIn("No full web search was performed", result)
        self.assertEqual(get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
