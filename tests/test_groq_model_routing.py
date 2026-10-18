"""Mocked contract tests for the Groq fast, balanced, and reasoning stream routes."""
import unittest
from unittest.mock import Mock, patch

import study_bot


class GroqModelRoutingTests(unittest.TestCase):
    def test_fast_stream_uses_configurable_active_model_and_omits_unsupported_reasoning_effort(self):
        delta = Mock(content="fast")
        chunk = Mock(choices=[Mock(delta=delta)])
        client = Mock()
        client.chat.completions.create.return_value = [chunk]
        with patch.object(study_bot, "GROQ_API_KEYS", ["fake-key"]), \
             patch.object(study_bot, "GROQ_FAST_MODEL", "llama-3.1-8b-instant"), \
             patch.object(study_bot, "_get_groq_client", return_value=client):
            self.assertEqual(list(study_bot._stream_groq([], "system", 256, "brainy-fast")), ["fast"])

        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "llama-3.1-8b-instant")
        self.assertEqual(kwargs["max_completion_tokens"], 256)
        self.assertNotIn("reasoning_effort", kwargs)
        self.assertNotIn("max_tokens", kwargs)

    def test_balanced_non_stream_uses_configurable_active_model_and_omits_unsupported_reasoning_effort(self):
        completion = Mock(choices=[Mock(finish_reason="stop", message=Mock(content="balanced"))])
        client = Mock()
        client.chat.completions.create.return_value = completion
        with patch.object(study_bot, "GROQ_API_KEYS", ["fake-key"]), \
             patch.object(study_bot, "GROQ_BALANCED_MODEL", "llama-3.3-70b-versatile"), \
             patch.object(study_bot, "_get_groq_client", return_value=client):
            text, truncated = study_bot._call_groq([], "system", 512)

        self.assertEqual(text, "balanced")
        self.assertFalse(truncated)
        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "llama-3.3-70b-versatile")
        self.assertEqual(kwargs["max_completion_tokens"], 512)
        self.assertNotIn("reasoning_effort", kwargs)
        self.assertNotIn("max_tokens", kwargs)

    def test_reasoning_model_includes_reasoning_effort(self):
        delta = Mock(content="reasoning")
        chunk = Mock(choices=[Mock(delta=delta)])
        client = Mock()
        client.chat.completions.create.return_value = [chunk]
        with patch.object(study_bot, "GROQ_API_KEYS", ["fake-key"]), \
             patch.object(study_bot, "GROQ_BALANCED_MODEL", "deepseek-r1-distill-llama-70b"), \
             patch.object(study_bot, "_get_groq_client", return_value=client):
            self.assertEqual(list(study_bot._stream_groq([], "system", 512, "brainy-balanced")), ["reasoning"])

        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "deepseek-r1-distill-llama-70b")
        self.assertEqual(kwargs["reasoning_effort"], "medium")


if __name__ == "__main__":
    unittest.main()
