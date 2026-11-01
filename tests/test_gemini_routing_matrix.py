"""
BrainyAi Gemini-First & Normal-Use Provider Routing Matrix Tests
Validates the 20 canonical real-world scenarios from Section 10 of the
Intelligent Provider Routing specification.
"""

import unittest
from unittest.mock import MagicMock, patch

from ai_routing.tasks import (
    classify_task_with_complexity,
    ResponseDepth,
    TaskType,
    TaskComplexity,
)
from ai_routing.policy import get_routing_candidates
from ai_routing.router import AIRouter
from ai_routing.providers.base import BaseProvider, ProviderResult
from ai_routing.prompts import prompt_registry, Platform


class GeminiRoutingMatrixTests(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_20_routing_scenarios_matrix(self):
        """
        Validates the 20 benchmark user requests defined in Section 10:
        1. Hello -> Lightweight path (Groq)
        2. Thanks -> Lightweight response (Groq)
        3. What is HTTP? -> Groq + normal-use
        4. What is an operating system? (fast vs balanced) -> Depth-aware Groq/Gemini
        5. Explain operating systems with examples -> Gemini
        6. Explain gradient descent simply -> Gemini
        7. Teach me SQL joins -> Gemini
        8. Translate this short sentence -> Groq + normal-use
        9. Rewrite this paragraph professionally -> Gemini
        10. Fix this small grammar mistake -> Lightweight path (Groq)
        11. Debug this React component -> Gemini
        12. Explain this Python error -> Gemini
        13. Give me a detailed project roadmap -> Gemini
        14. Compare two universities -> Gemini (+ search when needed)
        15. What is the weather today? -> Search tool + Gemini synthesis
        16. Summarize this PDF -> PDF extraction + Gemini
        17. Generate notes from my PDF -> PDF pipeline + Gemini
        18. Analyze this uploaded image -> Gemini multimodal
        19. Give me a one-line answer -> Lightweight path (Groq)
        20. Explain this in detailed Hinglish -> Gemini
        """
        scenarios = [
            # 1. Hello (Lightweight path)
            ("Hello", {"depth": ResponseDepth.BALANCED}, "groq"),
            # 2. Thanks (Lightweight response)
            ("Thanks", {"depth": ResponseDepth.BALANCED}, "groq"),
            # 3. What is HTTP? (Groq + normal-use)
            ("What is HTTP?", {"depth": ResponseDepth.BALANCED}, "groq"),
            # 4a. What is an operating system? (Depth-aware: FAST -> Groq)
            ("What is an operating system? [Fast]", {"depth": ResponseDepth.FAST, "query": "What is an operating system?"}, "groq"),
            # 4b. What is an operating system? (Depth-aware: BALANCED -> Gemini)
            ("What is an operating system? [Balanced]", {"depth": ResponseDepth.BALANCED, "query": "What is an operating system?"}, "gemini"),
            # 5. Explain operating systems with examples (Gemini)
            ("Explain operating systems with examples", {"depth": ResponseDepth.BALANCED}, "gemini"),
            # 6. Explain gradient descent simply (Gemini)
            ("Explain gradient descent simply", {"depth": ResponseDepth.BALANCED}, "gemini"),
            # 7. Teach me SQL joins (Gemini)
            ("Teach me SQL joins", {"depth": ResponseDepth.BALANCED}, "gemini"),
            # 8. Translate this short sentence (Groq + normal-use)
            ("Translate this short sentence: The library closes at 8 PM", {"depth": ResponseDepth.BALANCED}, "groq"),
            # 9. Rewrite this paragraph professionally (Gemini)
            ("Rewrite this paragraph professionally: We need this done as soon as possible because the clients are getting upset.", {"depth": ResponseDepth.BALANCED}, "gemini"),
            # 10. Fix this small grammar mistake (Lightweight path)
            ("Fix this small grammar mistake: She do not like apples", {"depth": ResponseDepth.BALANCED}, "groq"),
            # 11. Debug this React component (Gemini)
            ("Debug this React component: function App() { return <div/>; }", {"depth": ResponseDepth.BALANCED}, "gemini"),
            # 12. Explain this Python error (Gemini)
            ("Explain this Python error: TypeError: unsupported operand", {"depth": ResponseDepth.BALANCED}, "gemini"),
            # 13. Give me a detailed project roadmap (Gemini)
            ("Give me a detailed project roadmap for a SaaS platform", {"depth": ResponseDepth.BALANCED}, "gemini"),
            # 14. Compare two universities (Gemini)
            ("Compare two universities: Stanford vs MIT", {"depth": ResponseDepth.BALANCED}, "gemini"),
            # 15. What is the weather today? (Search tool + Gemini)
            ("What is the weather today in New Delhi?", {"depth": ResponseDepth.BALANCED}, "gemini"),
            # 16. Summarize this PDF (PDF extraction + Gemini)
            ("Summarize this PDF", {"depth": ResponseDepth.BALANCED, "context": {"pdf_text": "sample PDF text"}}, "gemini"),
            # 17. Generate notes from my PDF (PDF pipeline + Gemini)
            ("Generate notes from my PDF", {"depth": ResponseDepth.BALANCED, "context": {"pdf_text": "sample PDF text"}}, "gemini"),
            # 18. Analyze this uploaded image (Gemini multimodal)
            ("Analyze this uploaded image", {"depth": ResponseDepth.BALANCED, "context": {"has_image": True}}, "gemini"),
            # 19. Give me a one-line answer (Lightweight path)
            ("Give me a one-line answer: What is the capital of France?", {"depth": ResponseDepth.BALANCED}, "groq"),
            # 20. Explain this in detailed Hinglish (Gemini)
            ("Explain this in detailed Hinglish: What is quantum computing?", {"depth": ResponseDepth.BALANCED}, "gemini"),
        ]

        for label, opts, exp_prov in scenarios:
            query = opts.get("query", label)
            depth = opts.get("depth", ResponseDepth.BALANCED)
            context = opts.get("context", None)
            with self.subTest(label=label):
                task, comp = classify_task_with_complexity(query, depth=depth, context=context)
                cands = get_routing_candidates(task, depth=depth, complexity=comp)
                self.assertTrue(len(cands) > 0, f"No candidates returned for {label}")
                top_prov = cands[0][0]
                self.assertEqual(
                    top_prov, exp_prov,
                    f"Scenario '{label}' routed to {top_prov}, expected {exp_prov} (task={task}, comp={comp})"
                )

    def test_normal_use_prompt_loading_and_token_efficiency(self):
        """Verifies normal_use prompt has ~4.1k tokens vs ~9.5k tokens for advanced prompt."""
        normal_prompt = prompt_registry.compose_prompt(normal_use=True)
        adv_prompt = prompt_registry.compose_prompt(task=TaskType.CODING, normal_use=False)

        normal_tokens = len(normal_prompt) // 4
        adv_tokens = len(adv_prompt) // 4

        self.assertLess(normal_tokens, 5000)
        self.assertGreater(adv_tokens, 8000)
        # Verifies > 50% token reduction
        self.assertLess(normal_tokens, adv_tokens * 0.6)

    def test_mocked_gemini_routing_telemetry(self):
        """Validates that Gemini execution records accurate telemetry and mode."""
        gemini_mock = MagicMock(spec=BaseProvider)
        gemini_mock.generate.return_value = ProviderResult(
            text="Here is a professional rewrite of your paragraph...",
            model="gemini-3.8-flash",
            provider="gemini",
            latency_ms=180.0,
            tokens_in=120,
            tokens_out=45
        )
        self.router._providers["gemini"] = gemini_mock

        with patch("ai_routing.router.global_telemetry") as telemetry:
            res = self.router.generate(
                prompt="Rewrite this paragraph professionally: We need this done as soon as possible because the clients are getting upset."
            )

        self.assertEqual(res.provider, "gemini")
        self.assertEqual(res.model, "gemini-3.8-flash")
        record = telemetry.record.call_args.args[0]
        self.assertEqual(record.provider, "gemini")
        self.assertEqual(record.input_tokens, 120)
        self.assertEqual(record.output_tokens, 45)
        self.assertFalse(record.is_estimated)


if __name__ == "__main__":
    unittest.main()
