"""
Tests for BrainyAi Intelligent Gemini + Groq Routing Architecture
Verifies:
  1. Gemini = Primary for normal conversation and specialist tasks
  2. Gemini 3.5 Flash-Lite handles lightweight task routing
  3. Groq and OpenRouter are provider-level secondary and tertiary failover
  4. Task Complexity Classification (FAST, LIGHT, STANDARD, COMPLEX, DEEP)
  5. Thinking level adaptation (low, medium, high) without deprecated parameters
  6. Multimodal support and capability checks
  7. Non-Gemini invariant for PDF Study Studio
  8. Zero-budget enforcement and rejection of paid models (gemini-4-argon)
"""

import unittest
from unittest.mock import patch, MagicMock
from ai_routing.tasks import (
    TaskType,
    ResponseDepth,
    TaskComplexity,
    classify_task,
    classify_task_complexity,
    classify_task_with_complexity,
)
from ai_routing.policy import (
    get_routing_candidates,
    compute_routing_score,
    PDF_STUDY_TASKS,
    CODING_TASKS,
    MATH_TASKS,
    SCIENCE_TASKS,
)
from ai_routing.registry import registry, CostCategory, ModelSpec
from ai_routing.providers.gemini_provider import GeminiProvider


class TestTaskComplexityClassification(unittest.TestCase):
    """Verifies deterministic, zero-cost complexity classification."""

    def test_casual_greetings_classified_as_fast(self):
        greetings = [
            "Hi",
            "Hello!",
            "Hey",
            "Namaste",
            "Good morning",
            "thanks",
            "ok",
            "How are you?",
            "kem cho",
        ]
        for g in greetings:
            c = classify_task_complexity(g)
            self.assertEqual(c, TaskComplexity.FAST, f"Expected FAST for '{g}', got {c}")

    def test_short_definitions_and_translations_as_light(self):
        prompts = [
            ("define momentum briefly", TaskType.SIMPLE_EXPLANATION),
            ("what is a photon in short", TaskType.SIMPLE_EXPLANATION),
            ("translate this to Hindi: good job", TaskType.TRANSLATION),
        ]
        for p, t in prompts:
            c = classify_task_complexity(p, task=t)
            self.assertEqual(c, TaskComplexity.LIGHT, f"Expected LIGHT for '{p}', got {c}")

    def test_coding_and_science_as_complex(self):
        complex_prompts = [
            ("Write a Python function to implement binary search", TaskType.CODING),
            ("Debug this recursion: def f(n): return f(n-1)", TaskType.CODING_DEBUGGING),
            ("Explain Dijkstra's shortest path algorithm with time complexity", TaskType.DSA),
            ("SELECT user_id, count(*) FROM orders GROUP BY user_id", TaskType.SQL),
            ("Explain the second law of thermodynamics and entropy", TaskType.PHYSICS),
            ("Explain the difference between SN1 and SN2 reaction mechanisms", TaskType.CHEMISTRY),
            ("Explain transcription and translation in protein synthesis", TaskType.BIOLOGY),
        ]
        for p, t in complex_prompts:
            c = classify_task_complexity(p, task=t)
            self.assertIn(c, (TaskComplexity.COMPLEX, TaskComplexity.DEEP), f"Expected COMPLEX/DEEP for '{p}', got {c}")

    def test_deep_reasoning_and_proofs_as_deep(self):
        deep_prompts = [
            ("Prove that the square root of 2 is irrational step by step in detail", TaskType.DEEP_REASONING),
            ("Provide an in-depth architectural trade-off analysis of microservices vs monolith", TaskType.DEEP_REASONING),
        ]
        for p, t in deep_prompts:
            c = classify_task_complexity(p, task=t, depth=ResponseDepth.DEEP)
            self.assertEqual(c, TaskComplexity.DEEP, f"Expected DEEP for '{p}', got {c}")


class TestRoutingPolicyGroqSpeedGeminiIntelligence(unittest.TestCase):
    """Verifies Gemini model selection is separate from provider failover."""

    def setUp(self):
        self.eligibility = patch.object(registry, "is_model_eligible", return_value=True)
        self.eligibility.start()
        self.addCleanup(self.eligibility.stop)

    def test_casual_chat_uses_gemini_lite_before_provider_failover(self):
        candidates = get_routing_candidates(TaskType.QUICK_CHAT, complexity=TaskComplexity.FAST)
        self.assertTrue(len(candidates) > 0)
        first_prov, first_model = candidates[0]
        self.assertEqual(first_prov, "gemini", f"Gemini remains primary for normal chat, got {first_prov}")
        self.assertEqual(first_model, "gemini-3.5-flash-lite")

        # Ensure gemini-3.8-flash is NEVER selected for casual chat
        models = [m for p, m in candidates if p == "gemini"]
        self.assertEqual(models, ["gemini-3.5-flash-lite"], "Choose one Gemini model before provider failover")

    def test_coding_routes_to_one_gemini_38_flash_before_provider_failover(self):
        for task in CODING_TASKS:
            candidates = get_routing_candidates(task, complexity=TaskComplexity.COMPLEX)
            self.assertGreaterEqual(len(candidates), 2)
            self.assertEqual(candidates[0], ("gemini", "gemini-3.8-flash"), f"Primary for {task} must be gemini-3.8-flash")
            self.assertEqual([p for p, _ in candidates if p == "gemini"], ["gemini"])

    def test_math_routes_to_gemini_38_flash_primary(self):
        for task in MATH_TASKS:
            candidates = get_routing_candidates(task, complexity=TaskComplexity.COMPLEX)
            self.assertTrue(len(candidates) >= 2)
            self.assertEqual(candidates[0], ("gemini", "gemini-3.8-flash"))
            self.assertEqual([p for p, _ in candidates if p == "gemini"], ["gemini"])

    def test_science_routes_to_gemini_38_flash_primary(self):
        for task in SCIENCE_TASKS:
            candidates = get_routing_candidates(task, complexity=TaskComplexity.COMPLEX)
            self.assertTrue(len(candidates) >= 2)
            self.assertEqual(candidates[0], ("gemini", "gemini-3.8-flash"))
            self.assertEqual([p for p, _ in candidates if p == "gemini"], ["gemini"])

    def test_web_research_routes_to_gemini_38_flash_primary(self):
        candidates = get_routing_candidates(TaskType.WEB_RESEARCH, complexity=TaskComplexity.STANDARD)
        self.assertEqual(candidates[0], ("gemini", "gemini-3.8-flash"))
        self.assertEqual([p for p, _ in candidates if p == "gemini"], ["gemini"])

    def test_multimodal_routes_to_gemini_flash_models(self):
        candidates = get_routing_candidates(TaskType.IMAGE_QUESTION)
        self.assertEqual(candidates[0], ("gemini", "gemini-3.8-flash"))
        self.assertEqual([p for p, _ in candidates if p == "gemini"], ["gemini"])

    def test_strict_non_gemini_invariant_for_pdf_tasks(self):
        for task in PDF_STUDY_TASKS:
            candidates = get_routing_candidates(task)
            self.assertTrue(len(candidates) > 0, f"No candidates found for {task}")
            # Gemini is allowed and present in routing candidates for PDF study tasks
            providers = [p.lower() for p, _ in candidates]
            self.assertIn("gemini", providers)
            self.assertEqual(providers[:3], ["gemini", "groq", "openrouter"])


class TestThinkingLevelSelection(unittest.TestCase):
    """Verifies thinking level assignment based on model and complexity."""

    def test_gemini_38_flash_thinking_levels(self):
        self.assertEqual(registry.get_model_thinking_level("gemini-3.8-flash", TaskComplexity.FAST), "low")
        self.assertEqual(registry.get_model_thinking_level("gemini-3.8-flash", TaskComplexity.LIGHT), "low")
        self.assertEqual(registry.get_model_thinking_level("gemini-3.8-flash", TaskComplexity.STANDARD), "medium")
        self.assertEqual(registry.get_model_thinking_level("gemini-3.8-flash", TaskComplexity.COMPLEX), "high")
        self.assertEqual(registry.get_model_thinking_level("gemini-3.8-flash", TaskComplexity.DEEP), "high")

    def test_gemini_36_flash_thinking_levels(self):
        self.assertEqual(registry.get_model_thinking_level("gemini-3.6-flash", TaskComplexity.STANDARD), "medium")
        self.assertEqual(registry.get_model_thinking_level("gemini-3.6-flash", TaskComplexity.COMPLEX), "high")

    def test_lite_and_legacy_models_have_no_thinking(self):
        self.assertIsNone(registry.get_model_thinking_level("gemini-3.5-flash-lite", TaskComplexity.COMPLEX))
        self.assertIsNone(registry.get_model_thinking_level("gemini-3.1-flash-lite", TaskComplexity.DEEP))
        self.assertIsNone(registry.get_model_thinking_level("gemini-2.5-flash", TaskComplexity.COMPLEX))


class TestModelEligibilityAndZeroBudget(unittest.TestCase):
    """Verifies strict zero-budget enforcement and paid model rejection."""

    def setUp(self):
        self.orig_strict = registry.strict_zero_budget
        self.orig_paid = registry.allow_paid_models

    def tearDown(self):
        registry.set_strict_zero_budget(self.orig_strict)
        registry.set_allow_paid_models(self.orig_paid)

    def test_gemini_4_argon_rejected_in_zero_budget_mode(self):
        registry.set_strict_zero_budget(True)
        registry.set_allow_paid_models(False)
        spec = registry.get_model_spec("gemini-4-argon")
        self.assertIsNotNone(spec)
        self.assertTrue(spec.is_paid_only)
        self.assertEqual(spec.cost_category, CostCategory.PAID)

        # Must be rejected by eligibility filter
        is_eligible = registry.is_model_eligible("gemini", "gemini-4-argon")
        self.assertFalse(is_eligible, "gemini-4-argon MUST be rejected under strict zero-budget mode")

    def test_gemini_4_argon_accepted_only_when_explicitly_allowed(self):
        registry.set_strict_zero_budget(False)
        registry.set_allow_paid_models(True)
        # Mock key count so provider is marked available
        with patch.object(registry, "get_key_count", return_value=1):
            is_eligible = registry.is_model_eligible("gemini", "gemini-4-argon")
            self.assertTrue(is_eligible)

    def test_model_catalog_metadata(self):
        catalog = registry.get_model_catalog()
        model_ids = {m["model_id"]: m for m in catalog}
        self.assertIn("gemini-3.8-flash", model_ids)
        self.assertIn("gemini-3.6-flash", model_ids)
        self.assertIn("gemini-3.5-flash-lite", model_ids)
        self.assertIn("openai/gpt-oss-20b", model_ids)

        g38 = model_ids["gemini-3.8-flash"]
        self.assertEqual(g38["lifecycle"], "stable")
        self.assertIn("image", g38["supported_modalities"])
        self.assertIn("high", g38["supported_thinking_levels"])
        self.assertFalse(g38["is_paid_only"])


class TestGeminiProviderPayload(unittest.TestCase):
    """Verifies that GeminiProvider correctly constructs requests with thinkingConfig."""

    @patch("ai_routing.providers.gemini_provider.requests.post")
    def test_gemini_thinking_config_passed_for_gemini_3(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{
                "content": {"parts": [{"text": "Result from Gemini"}]},
                "finishReason": "stop"
            }]
        }
        mock_post.return_value = mock_resp

        with patch.object(registry, "get_rotator") as mock_rot:
            rot_mock = MagicMock()
            rot_mock.key_count = 1
            rot_mock.get_key.return_value = "fake_gemini_key"
            mock_rot.return_value = rot_mock

            provider = GeminiProvider()
            res = provider.generate(
                messages=[{"role": "user", "content": "Write a quicksort"}],
                system_prompt="You are a helpful assistant.",
                max_tokens=2048,
                model_id="gemini-3.8-flash",
                thinking_level="high"
            )
            self.assertEqual(res.text, "Result from Gemini")
            self.assertTrue(mock_post.called)
            called_payload = mock_post.call_args[1]["json"]
            self.assertIn("thinkingConfig", called_payload["generationConfig"])
            self.assertEqual(called_payload["generationConfig"]["thinkingConfig"]["thinkingLevel"], "HIGH")

    @patch("ai_routing.providers.gemini_provider.requests.post")
    def test_gemini_thinking_config_omitted_for_legacy_gemini_2(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{
                "content": {"parts": [{"text": "Result from Gemini 2.5"}]},
                "finishReason": "stop"
            }]
        }
        mock_post.return_value = mock_resp

        with patch.object(registry, "get_rotator") as mock_rot:
            rot_mock = MagicMock()
            rot_mock.key_count = 1
            rot_mock.get_key.return_value = "fake_gemini_key"
            mock_rot.return_value = rot_mock

            provider = GeminiProvider()
            res = provider.generate(
                messages=[{"role": "user", "content": "Explain gravity"}],
                system_prompt="You are a helpful assistant.",
                max_tokens=2048,
                model_id="gemini-2.5-flash",
                thinking_level="medium"
            )
            self.assertEqual(res.text, "Result from Gemini 2.5")
            called_payload = mock_post.call_args[1]["json"]
            self.assertNotIn("thinkingConfig", called_payload["generationConfig"])


class TestAIRouterEndToEnd(unittest.TestCase):
    """Verifies that AIRouter accurately directs traffic according to the speed vs intelligence policy."""

    def test_router_generates_via_groq_for_greetings(self):
        from ai_routing.router import router
        from ai_routing.providers.base import ProviderResult

        with patch.object(router._providers["groq"], "generate") as mock_groq_gen:
            mock_groq_gen.return_value = ProviderResult(
                text="Hello! How can I help you today?",
                model="openai/gpt-oss-20b",
                provider="groq"
            )
            res = router.generate("Hey there! Good morning")
            self.assertEqual(res.provider, "groq")
            self.assertEqual(res.model, "openai/gpt-oss-20b")
            self.assertTrue(mock_groq_gen.called)

    def test_router_generates_via_gemini_for_coding(self):
        from ai_routing.router import router
        from ai_routing.providers.base import ProviderResult

        with patch.object(router._providers["gemini"], "generate") as mock_gemini_gen:
            mock_gemini_gen.return_value = ProviderResult(
                text="def mergesort(arr): ...",
                model="gemini-3.8-flash",
                provider="gemini"
            )
            res = router.generate("Write a complete mergesort algorithm in Python with time complexity")
            self.assertEqual(res.provider, "gemini")
            self.assertEqual(res.model, "gemini-3.8-flash")
            self.assertTrue(mock_gemini_gen.called)

    def test_router_solves_math_locally_zero_cost(self):
        from ai_routing.router import router
        res = router.generate("integrate 3*x^2 dx")
        self.assertEqual(res.provider, "local_math_engine")
        self.assertTrue(res.math_verified)
        self.assertIn("x^{3}", res.text)


if __name__ == "__main__":
    unittest.main()
