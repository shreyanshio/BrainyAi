"""Regression tests for lightweight Normal Use selection and safe fallback."""

import unittest
from unittest.mock import MagicMock, patch

from ai_routing.policy import get_routing_candidates
from ai_routing.prompts import prompt_registry
from ai_routing.providers.base import BaseProvider, ProviderResult
from ai_routing.router import AIRouter
from ai_routing.tasks import (
    ResponseDepth,
    TaskComplexity,
    TaskType,
    classify_task,
    classify_task_complexity,
    classify_task_with_complexity,
)


class NormalUseRoutingTests(unittest.TestCase):
    def test_everyday_examples_select_light_complexity(self):
        examples = [
            ("Hello!", TaskType.QUICK_CHAT),
            ("Rewrite this sentence more clearly: I need this fixed soon.", TaskType.WRITING),
            ("Translate hello into Hindi", TaskType.TRANSLATION),
            ("What is gravity?", TaskType.SIMPLE_EXPLANATION),
            ("Summarize this short paragraph: Birds migrate south in winter.", TaskType.SIMPLE_EXPLANATION),
            ("Brainstorm a few names for my book club", TaskType.WRITING),
        ]
        for text, expected_task in examples:
            with self.subTest(text=text):
                task, complexity = classify_task_with_complexity(text)
                self.assertEqual(task, expected_task)
                self.assertIn(complexity, (TaskComplexity.FAST, TaskComplexity.LIGHT))
                self.assertEqual(get_routing_candidates(task, ResponseDepth.BALANCED, complexity)[0][0], "gemini")

    def test_local_arithmetic_fast_path_is_preserved(self):
        router = AIRouter()
        result = router.generate("Calculate 45 * 12 + 180")
        self.assertEqual(result.provider, "local_math_engine")

    def test_complex_reasoning_and_coding_stay_advanced(self):
        for text, expected in (
            ("Prove this theorem step by step in detail", (TaskType.DEEP_REASONING,)),
            ("Design a robust distributed Python service with retries and observability", (TaskType.CODING,)),
            ("Rewrite this Python function to use recursion", (TaskType.CODING, TaskType.DSA)),
        ):
            with self.subTest(text=text):
                task, complexity = classify_task_with_complexity(text)
                self.assertIn(task, expected)
                self.assertNotIn(complexity, (TaskComplexity.FAST, TaskComplexity.LIGHT))

    def test_large_document_request_keeps_pdf_route_and_specialist_prompt(self):
        task = classify_task("Summarize this document", context={"pdf_text": "page " * 10000})
        self.assertEqual(task, TaskType.PDF_SUMMARY)
        self.assertIn("gemini", [provider for provider, _ in get_routing_candidates(task)])
        prompt = prompt_registry.compose_prompt(task=task)
        self.assertIn("ACTIVE TASK SPECIALIST PROTOCOL", prompt)

    def test_router_uses_normal_prompt_and_preserves_history_with_mocked_provider(self):
        router = AIRouter()
        provider = MagicMock(spec=BaseProvider)
        provider.generate.return_value = ProviderResult(
            text="Hello!", model="openai/gpt-oss-20b", provider="groq", latency_ms=10, tokens_in=10, tokens_out=2
        )
        router._providers = {"groq": provider}
        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "How are you?"},
        ]
        with patch("ai_routing.router.global_telemetry") as telemetry:
            result = router.generate(messages=history, candidate_chain=[("groq", "openai/gpt-oss-20b")])
        self.assertEqual(result.text, "Hello!")
        kwargs = provider.generate.call_args.kwargs
        self.assertEqual(kwargs["messages"], history)
        self.assertIn("NORMAL USE — BRAINY", kwargs["system_prompt"])
        self.assertIn("Security and safety", kwargs["system_prompt"])
        self.assertNotIn("Brainy Core Persona Configuration", kwargs["system_prompt"])
        record = telemetry.record.call_args.args[0]
        self.assertEqual(record.mode, "normal_use")
        self.assertTrue(record.prompt_tokens_estimated)
        self.assertGreater(record.prompt_tokens, 0)
        self.assertIn("quick_chat classified", record.selection_reason)

    def test_explicit_specialist_instruction_is_not_replaced(self):
        router = AIRouter()
        provider = MagicMock(spec=BaseProvider)
        provider.generate.return_value = ProviderResult(text="x", model="test", provider="groq", latency_ms=1)
        router._providers = {"groq": provider}
        specialist = "ACTIVE TASK SPECIALIST PROTOCOL\nPreserve this explicit instruction."
        router.generate("Translate hello into Hindi", system_prompt=specialist, candidate_chain=[("groq", "test")])
        self.assertIn("ACTIVE TASK SPECIALIST PROTOCOL", provider.generate.call_args.kwargs["system_prompt"])
        self.assertIn("Preserve this explicit instruction.", provider.generate.call_args.kwargs["system_prompt"])

    def test_fallback_uses_existing_chain_without_repeating_request(self):
        router = AIRouter()
        fast = MagicMock(spec=BaseProvider)
        fast.generate.side_effect = RuntimeError("temporarily unavailable")
        advanced = MagicMock(spec=BaseProvider)
        advanced.generate.return_value = ProviderResult(text="Hello", model="gemini-fast", provider="gemini", latency_ms=3)
        router._providers = {"groq": fast, "gemini": advanced}
        messages = [{"role": "user", "content": "Hi"}]
        with patch("ai_routing.router.global_telemetry") as telemetry:
            result = router.generate(messages=messages, candidate_chain=[("groq", "fast"), ("gemini", "fallback")])
        self.assertTrue(result.fallback_used)
        self.assertEqual(advanced.generate.call_count, 1)
        self.assertEqual(advanced.generate.call_args.kwargs["messages"], messages)
        record = telemetry.record.call_args.args[0]
        self.assertIsNotNone(record.escalation_reason)


if __name__ == "__main__":
    unittest.main()
