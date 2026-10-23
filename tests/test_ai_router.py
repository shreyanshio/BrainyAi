"""
Unit tests for Phase 1: Intelligent Multi-Provider AI Router.
Verifies task classification, response-depth token policies, telemetry buffer,
model registry key rotation, and pre-output fallback behavior.
"""

import unittest
from unittest.mock import patch, MagicMock

from ai_routing.tasks import TaskType, ResponseDepth, classify_task
from ai_routing.telemetry import AITelemetry
from ai_routing.registry import ProviderRegistry, ProviderKeyRotator, ModelSpec
from ai_routing.providers.base import ProviderResult, BaseProvider
from ai_routing.router import AIRouter


class TestTaskClassification(unittest.TestCase):
    def test_classify_simple_greeting(self):
        task = classify_task([{"role": "user", "content": "Hi there!"}])
        self.assertEqual(task, TaskType.QUICK_CHAT)

    def test_classify_coding(self):
        task = classify_task([{"role": "user", "content": "Write a python function to reverse a linked list using def reverse_list:"}])
        self.assertEqual(task, TaskType.CODING)

    def test_classify_math_and_logic(self):
        task = classify_task([{"role": "user", "content": "Calculate the integral dx / (x^2 + 1) with step by step proof"}])
        self.assertEqual(task, TaskType.MATH_AND_LOGIC)

    def test_classify_quiz_generation(self):
        task = classify_task([{"role": "user", "content": "Create a 5-question multiple choice quiz on photosynthesis"}])
        self.assertEqual(task, TaskType.QUIZ_GENERATION)

    def test_classify_flashcard_generation(self):
        task = classify_task([{"role": "user", "content": "Generate 10 flashcards for organic chemistry reactions"}])
        self.assertEqual(task, TaskType.FLASHCARD_GENERATION)

    def test_classify_web_research(self):
        task = classify_task([{"role": "user", "content": "What are the latest breakthrough news in room temperature superconductors?"}])
        self.assertEqual(task, TaskType.WEB_RESEARCH)

    def test_classify_pdf_summary(self):
        task = classify_task([{"role": "user", "content": "Please summarize this attached PDF chapter"}])
        self.assertEqual(task, TaskType.PDF_SUMMARY)


class TestKeyRotator(unittest.TestCase):
    def test_rotator_round_robin(self):
        rotator = ProviderKeyRotator("test", ["key_1", "key_2", "key_3"])
        self.assertEqual(rotator.key_count, 3)
        self.assertEqual(rotator.get_next_key(), "key_1")
        self.assertEqual(rotator.get_next_key(), "key_2")
        self.assertEqual(rotator.get_next_key(), "key_3")
        self.assertEqual(rotator.get_next_key(), "key_1")

    def test_rotator_quarantine_on_rate_limit(self):
        rotator = ProviderKeyRotator("test", ["key_1", "key_2"])
        rotator.quarantine_key("key_1", cooldown_seconds=60)
        # Should now only return key_2
        self.assertEqual(rotator.get_next_key(), "key_2")
        self.assertEqual(rotator.get_next_key(), "key_2")

    def test_rotator_empty_keys(self):
        rotator = ProviderKeyRotator("test", [])
        self.assertIsNone(rotator.get_next_key())


class TestAITelemetry(unittest.TestCase):
    def setUp(self):
        self.telemetry = AITelemetry(max_events=20)

    def test_record_and_summary(self):
        self.telemetry.record_call(
            provider="groq",
            model="llama-3.3-70b-versatile",
            task="CODING",
            latency_ms=120.5,
            success=True,
            tokens_in=100,
            tokens_out=250
        )
        self.telemetry.record_call(
            provider="groq",
            model="llama-3.3-70b-versatile",
            task="CODING",
            latency_ms=180.0,
            success=False,
            error_category="RateLimitError"
        )

        summary = self.telemetry.get_provider_summary()
        self.assertIn("groq", summary)
        groq_stats = summary["groq"]
        self.assertEqual(groq_stats["total_calls"], 2)
        self.assertEqual(groq_stats["success_count"], 1)
        self.assertEqual(groq_stats["error_count"], 1)
        self.assertEqual(groq_stats["error_rate_pct"], 50.0)

    def test_ring_buffer_eviction(self):
        for i in range(25):
            self.telemetry.record_call(
                provider="mock",
                model="mock-v1",
                task="QUICK_CHAT",
                latency_ms=10.0 + i,
                success=True
            )
        events = self.telemetry.get_recent_events(limit=50)
        self.assertEqual(len(events), 20)  # Capped at max_events


class TestAIRouterFallback(unittest.TestCase):
    def test_router_generates_with_fallback(self):
        router = AIRouter()

        # Mock first provider failing and second succeeding
        failing_provider = MagicMock(spec=BaseProvider)
        failing_provider.is_available.return_value = True
        failing_provider.generate.side_effect = RuntimeError("Rate limit hit 429")

        successful_provider = MagicMock(spec=BaseProvider)
        successful_provider.is_available.return_value = True
        successful_provider.generate.return_value = ProviderResult(
            text="Hello from fallback provider!",
            model="fallback-model",
            provider="fallback-provider",
            latency_ms=85.0,
            tokens_out=15
        )

        router._providers = {
            "primary": failing_provider,
            "fallback": successful_provider
        }

        chain = [
            ("primary", "primary-model"),
            ("fallback", "fallback-model")
        ]

        result = router.generate(
            messages=[{"role": "user", "content": "Hello"}],
            task=TaskType.QUICK_CHAT,
            candidate_chain=chain
        )

        self.assertEqual(result.text, "Hello from fallback provider!")
        self.assertEqual(result.provider, "fallback")

    def test_router_stream_pre_output_fallback(self):
        router = AIRouter()

        # Provider 1 fails immediately before yielding any tokens
        failing_provider = MagicMock(spec=BaseProvider)
        failing_provider.is_available.return_value = True
        def fail_stream(*args, **kwargs):
            raise ConnectionError("Upstream timeout before first token")
            yield  # make it a generator
        failing_provider.stream.side_effect = fail_stream

        # Provider 2 yields tokens smoothly
        successful_provider = MagicMock(spec=BaseProvider)
        successful_provider.is_available.return_value = True
        def succeed_stream(*args, **kwargs):
            yield "Token 1 "
            yield "Token 2"
        successful_provider.stream.side_effect = succeed_stream

        router._providers = {
            "primary": failing_provider,
            "fallback": successful_provider
        }

        chain = [
            ("primary", "primary-model"),
            ("fallback", "fallback-model")
        ]

        chunks = list(router.stream(
            messages=[{"role": "user", "content": "Stream test"}],
            candidate_chain=chain
        ))

        self.assertEqual("".join(chunks), "Token 1 Token 2")


if __name__ == "__main__":
    unittest.main()
