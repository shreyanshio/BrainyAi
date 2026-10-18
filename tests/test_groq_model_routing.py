"""Mocked contract tests for the Groq fast and balanced stream routes."""
import unittest
from unittest.mock import Mock, patch

import study_bot


class GroqModelRoutingTests(unittest.TestCase):
    def test_fast_stream_uses_configurable_active_model_and_completion_token_field(self):
        delta = Mock(content="fast")
        chunk = Mock(choices=[Mock(delta=delta)])
        client = Mock()
        client.chat.completions.create.return_value = [chunk]
        with patch.object(study_bot, "GROQ_API_KEYS", ["fake-key"]), \
             patch.object(study_bot, "GROQ_FAST_MODEL", "openai/gpt-oss-20b"), \
             patch.object(study_bot, "_get_groq_client", return_value=client):
            self.assertEqual(list(study_bot._stream_groq([], "system", 256, "brainy-fast")), ["fast"])

        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "openai/gpt-oss-20b")
        self.assertEqual(kwargs["max_completion_tokens"], 256)
        self.assertEqual(kwargs["reasoning_effort"], "low")
        self.assertNotIn("max_tokens", kwargs)

    def test_balanced_non_stream_uses_configurable_active_model(self):
        completion = Mock(choices=[Mock(finish_reason="stop", message=Mock(content="balanced"))])
        client = Mock()
        client.chat.completions.create.return_value = completion
        with patch.object(study_bot, "GROQ_API_KEYS", ["fake-key"]), \
             patch.object(study_bot, "GROQ_BALANCED_MODEL", "openai/gpt-oss-120b"), \
             patch.object(study_bot, "_get_groq_client", return_value=client):
            text, truncated = study_bot._call_groq([], "system", 512)

        self.assertEqual(text, "balanced")
        self.assertFalse(truncated)
        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "openai/gpt-oss-120b")
        self.assertEqual(kwargs["max_completion_tokens"], 512)
        self.assertNotIn("max_tokens", kwargs)


if __name__ == "__main__":
    unittest.main()
