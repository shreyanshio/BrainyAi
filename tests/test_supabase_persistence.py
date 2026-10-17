"""Regression tests for durable chat reads and writes (mocked PostgREST)."""
import unittest
from unittest.mock import patch

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
        self.assertEqual(app.sb_get_recent_messages("session"), [])

    @patch("app.requests.request")
    def test_message_write_failure_is_not_reported_as_success(self, request):
        from requests import HTTPError
        request.return_value = FakeResponse(status_error=HTTPError("schema failure"))
        with self.assertRaises(app.SupabaseOperationError):
            app.sb_insert_message("session", "user", "private test text")
        self.assertEqual(app.MEM_MESSAGES.get("session", []), [])

    @patch("app.requests.request")
    def test_session_creation_requires_a_returned_row(self, request):
        request.return_value = FakeResponse([])
        with self.assertRaises(app.SupabaseOperationError):
            app.sb_create_session(123, "test")
        self.assertEqual(app.MEM_SESSIONS.get(123, []), [])


if __name__ == "__main__":
    unittest.main()
