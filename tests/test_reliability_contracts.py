"""Deterministic regression tests for shared rate limits and DDG fallback behavior."""
import os
import unittest
from unittest.mock import Mock, patch

import security
import study_bot
import app


class ReliabilityContractTests(unittest.TestCase):
    @patch.dict(os.environ, {"ENVIRONMENT": "production", "SUPABASE_URL": "https://db.example", "SUPABASE_SERVICE_KEY": "test"})
    @patch("security.requests.post", side_effect=TimeoutError("offline"))
    def test_production_shared_limiter_fails_closed(self, _post):
        with self.assertRaises(security.RateLimitStoreUnavailable):
            security.check_rate_limit("test-ip")

    @patch.dict(os.environ, {"ENVIRONMENT": "production", "SUPABASE_URL": "", "SUPABASE_SERVICE_KEY": ""})
    def test_production_limiter_requires_shared_store(self):
        with self.assertRaises(security.RateLimitStoreUnavailable):
            security.check_rate_limit("test-ip")

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
