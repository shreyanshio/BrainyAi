"""Deterministic regression tests for shared rate limits and DDG fallback behavior."""
import os
import unittest
from unittest.mock import Mock, patch

import security
import study_bot
import app


class ReliabilityContractTests(unittest.TestCase):
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
