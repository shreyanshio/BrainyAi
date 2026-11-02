import unittest
from unittest.mock import MagicMock, patch
import requests

from ai_routing.gemini_selection import select_gemini_model
from ai_routing.policy import get_routing_candidates
from ai_routing.providers.gemini_provider import GeminiProvider
from ai_routing.registry import registry
from ai_routing.tasks import ResponseDepth, TaskComplexity, TaskType


class GeminiIntelligentRoutingTests(unittest.TestCase):
    def setUp(self):
        self.paid = registry.allow_paid_models
        self.strict = registry.strict_zero_budget
        registry.set_strict_zero_budget(True)
        registry.set_allow_paid_models(False)

    def tearDown(self):
        registry.set_strict_zero_budget(self.strict)
        registry.set_allow_paid_models(self.paid)

    def test_task_based_model_selection_picks_one_model_before_provider_failover(self):
        with patch.object(registry, "is_model_eligible", return_value=True):
            normal = get_routing_candidates(TaskType.SIMPLE_EXPLANATION, complexity=TaskComplexity.STANDARD)
            code = get_routing_candidates(TaskType.CODING, complexity=TaskComplexity.COMPLEX)
            light = get_routing_candidates(TaskType.SIMPLE_EXPLANATION, complexity=TaskComplexity.LIGHT)
        self.assertEqual(normal[0], ("gemini", "gemini-3.8-flash"))
        self.assertEqual(code[0], ("gemini", "gemini-3.8-flash"))
        self.assertEqual(light[0], ("gemini", "gemini-3.5-flash-lite"))
        for candidates in (normal, code, light):
            self.assertEqual([provider for provider, _ in candidates], ["gemini", "groq", "openrouter"])

    def test_deep_selection_uses_paid_flagship_only_when_explicitly_allowed(self):
        deep = select_gemini_model(TaskType.DEEP_REASONING, depth=ResponseDepth.DEEP, complexity=TaskComplexity.DEEP)
        self.assertEqual(deep.model_id, "gemini-3.8-flash")
        registry.set_strict_zero_budget(False)
        registry.set_allow_paid_models(True)
        deep_paid = select_gemini_model(TaskType.DEEP_REASONING, depth=ResponseDepth.DEEP, complexity=TaskComplexity.DEEP)
        self.assertEqual(deep_paid.model_id, "gemini-4-argon")

    def test_image_selection_requires_registered_multimodal_capability(self):
        selected = select_gemini_model(TaskType.IMAGE_QUESTION, document_context={"has_image": True})
        self.assertEqual(selected.model_id, "gemini-3.8-flash")
        spec = registry.get_model_spec(selected.model_id)
        self.assertIn("image", spec.supported_input_modalities)
        with patch.object(registry, "is_model_eligible", return_value=True):
            candidates = get_routing_candidates(TaskType.IMAGE_QUESTION, document_context={"has_image": True})
        self.assertEqual(candidates[0], ("gemini", "gemini-3.8-flash"))
        self.assertNotIn("groq", [provider for provider, _ in candidates])
        self.assertEqual(candidates[1], ("openrouter", "nvidia/nemotron-3.5-super-vl:free"))

    @patch("ai_routing.providers.gemini_provider.requests.post")
    def test_model_specific_missing_model_tries_one_gemini_alternate(self, post):
        original_status = registry.get_model_spec("gemini-3.8-flash").availability_status
        original_time = registry.get_model_spec("gemini-3.8-flash").last_verified_ts
        first = MagicMock(status_code=404)
        first.raise_for_status.side_effect = requests.HTTPError("404 model not found")
        second = MagicMock(status_code=200)
        second.json.return_value = {"candidates": [{"content": {"parts": [{"text": "ok"}]}, "finishReason": "stop"}]}
        post.side_effect = [first, second]
        rotator = MagicMock(key_count=1)
        rotator.get_key.return_value = "test-key"
        with patch.object(registry, "get_rotator", return_value=rotator):
            try:
                result = GeminiProvider().generate(
                    messages=[{"role": "user", "content": "hello"}],
                    system_prompt="",
                    max_tokens=64,
                    model_id="gemini-3.8-flash",
                )
            finally:
                spec = registry.get_model_spec("gemini-3.8-flash")
                spec.availability_status = original_status
                spec.last_verified_ts = original_time
        self.assertEqual(result.model, "gemini-3.6-flash")
        self.assertEqual(post.call_count, 2)

    @patch("ai_routing.providers.gemini_provider.requests.post")
    def test_quota_error_does_not_try_another_gemini_model(self, post):
        response = MagicMock(status_code=429)
        post.return_value = response
        rotator = MagicMock(key_count=1)
        rotator.get_key.return_value = "test-key"
        with patch.object(registry, "get_rotator", return_value=rotator):
            with self.assertRaisesRegex(RuntimeError, "429"):
                GeminiProvider().generate(
                    messages=[{"role": "user", "content": "hello"}],
                    system_prompt="",
                    max_tokens=64,
                    model_id="gemini-3.8-flash",
                )
        self.assertEqual(post.call_count, 1)
        rotator.quarantine_all.assert_called_once()
        rotator.quarantine_key.assert_not_called()


if __name__ == "__main__":
    unittest.main()
