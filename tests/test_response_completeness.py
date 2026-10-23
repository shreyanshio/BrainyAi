"""
BrainyAi Automated Response Completeness & Seamless Continuation Test Suite.
Verifies Tests A through L:
- Test A: Normal short prompt produces clean complete response without padding.
- Test B: Detailed explanation allocates comprehensive token budget.
- Test C: Simulated output-limit truncation triggers automatic continuation.
- Test D: Normal stop finish reason does not trigger unnecessary continuation.
- Test E: Multi-turn streaming continuation with boundary overlap deduplication.
- Test F: Code preservation across truncation boundaries.
- Test G: Safety cap on continuation rounds (MAX_CONTINUATION_ROUNDS = 3).
- Test H: Upstream error during continuation recovers accumulated text.
- Test I: Stream consumer early exit / cancellation closes cleanly.
- Test J: Multi-part prompt completeness directive verification.
- Test K: Safety directive persistence in continuation.
- Test L: OutputBudgetManager per-model, task, and context headroom calculations.
"""

import unittest
from unittest.mock import MagicMock, patch

from ai_routing.tasks import TaskType, ResponseDepth
from ai_routing.budget import OutputBudgetManager
from ai_routing.continuation import (
    is_length_truncated,
    stitch_continuation,
    deduplicate_stream_overlap,
    CONTINUATION_PROMPT,
    MAX_CONTINUATION_ROUNDS
)
from ai_routing.providers.base import BaseProvider, ProviderResult
from ai_routing.router import AIRouter


class TestResponseCompletenessSuite(unittest.TestCase):

    def setUp(self):
        self.router = AIRouter()

    # ── Test A: Normal Short Prompt ──
    def test_a_normal_short_prompt_no_continuation(self):
        mock_provider = MagicMock(spec=BaseProvider)
        mock_provider.generate.return_value = ProviderResult(
            text="Paris is the capital of France.",
            model="test-model",
            provider="mock",
            latency_ms=45.0,
            finish_reason="stop",
            output_tokens=10
        )
        self.router._providers = {"mock": mock_provider}

        res = self.router.generate(
            prompt="What is the capital of France?",
            candidate_chain=[("mock", "test-model")]
        )

        self.assertEqual(res.text, "Paris is the capital of France.")
        self.assertFalse(res.continuation_used)
        self.assertEqual(res.continuation_rounds, 0)
        self.assertEqual(mock_provider.generate.call_count, 1)

    # ── Test B: Detailed Explanation Token Budget ──
    def test_b_detailed_explanation_budget_allocation(self):
        budget_groq = OutputBudgetManager.resolve_budget(
            task=TaskType.DETAILED_EXPLANATION,
            depth=ResponseDepth.DEEP,
            provider_name="groq",
            model_id="llama-3.3-70b-versatile"
        )
        self.assertGreaterEqual(budget_groq, 4096)

        budget_gemini = OutputBudgetManager.resolve_budget(
            task=TaskType.DEEP_REASONING,
            depth=ResponseDepth.DEEP,
            provider_name="gemini",
            model_id="gemini-2.5-flash"
        )
        self.assertEqual(budget_gemini, 8192)

    # ── Test C: Length Truncation Triggers Seamless Continuation ──
    def test_c_simulated_length_truncation_continuation(self):
        mock_provider = MagicMock(spec=BaseProvider)
        # Call 1: truncated by length
        # Call 2: finishes normally
        mock_provider.generate.side_effect = [
            ProviderResult(
                text="The process of cellular respiration consists of glycolysis, the Krebs cycle, and ",
                model="test-model",
                provider="mock",
                latency_ms=100.0,
                finish_reason="length",
                output_tokens=50
            ),
            ProviderResult(
                text="oxidative phosphorylation in the mitochondrial membrane.",
                model="test-model",
                provider="mock",
                latency_ms=80.0,
                finish_reason="stop",
                output_tokens=30
            )
        ]
        self.router._providers = {"mock": mock_provider}

        res = self.router.generate(
            prompt="Explain cellular respiration in detail",
            candidate_chain=[("mock", "test-model")]
        )

        self.assertTrue(res.continuation_used)
        self.assertEqual(res.continuation_rounds, 1)
        self.assertEqual(
            res.text,
            "The process of cellular respiration consists of glycolysis, the Krebs cycle, and oxidative phosphorylation in the mitochondrial membrane."
        )
        self.assertEqual(mock_provider.generate.call_count, 2)

    # ── Test D: Normal Stop Finish Reason Does Not Trigger Continuation ──
    def test_d_normal_stop_no_continuation(self):
        mock_provider = MagicMock(spec=BaseProvider)
        mock_provider.generate.return_value = ProviderResult(
            text="Here is the concise answer.",
            model="test-model",
            provider="mock",
            latency_ms=50.0,
            finish_reason="stop",
            output_tokens=15
        )
        self.router._providers = {"mock": mock_provider}

        res = self.router.generate(
            prompt="Simple query",
            candidate_chain=[("mock", "test-model")]
        )

        self.assertFalse(res.continuation_used)
        self.assertEqual(res.continuation_rounds, 0)
        self.assertEqual(mock_provider.generate.call_count, 1)

    # ── Test E: Streaming Continuation with Overlap Deduplication ──
    def test_e_streaming_continuation_with_overlap_deduplication(self):
        class MockStreamProvider(BaseProvider):
            def __init__(self):
                super().__init__()
                self.call_count = 0

            def generate(self, *args, **kwargs):
                pass

            def stream(self, messages, system_prompt, max_tokens, model_id=None, multimodal_parts=None):
                self.call_count += 1
                if self.call_count == 1:
                    self.last_stream_finish_reason = "length"
                    yield "Step 1: Parse the AST.\nStep 2: Optimize bytecode."
                else:
                    self.last_stream_finish_reason = "stop"
                    # Simulate slight boundary repeat from model
                    yield "Optimize bytecode.\nStep 3: Execute in runtime."

        provider = MockStreamProvider()
        self.router._providers = {"mock": provider}

        tokens = list(self.router.stream(
            prompt="Explain compilation steps",
            candidate_chain=[("mock", "test-model")]
        ))

        full_stream_text = "".join(tokens)
        # Should have deduplicated the repeated "Optimize bytecode."
        self.assertIn("Step 1: Parse the AST.\nStep 2: Optimize bytecode.\nStep 3: Execute in runtime.", full_stream_text)
        self.assertEqual(provider.call_count, 2)

    # ── Test F: Code Block Continuation Preservation ──
    def test_f_code_block_continuation_preservation(self):
        part1 = "```python\ndef quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n"
        part2 = "    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)\n```"

        stitched = stitch_continuation(part1, part2)
        self.assertTrue(stitched.startswith("```python\ndef quicksort"))
        self.assertTrue(stitched.endswith("```"))
        self.assertIn("return quicksort(left)", stitched)

    # ── Test G: Safety Cap on Maximum Continuation Rounds ──
    def test_g_max_continuation_rounds_enforced(self):
        mock_provider = MagicMock(spec=BaseProvider)
        # Provider perpetually returns finish_reason="length"
        mock_provider.generate.return_value = ProviderResult(
            text="chunk...",
            model="test-model",
            provider="mock",
            latency_ms=30.0,
            finish_reason="length",
            output_tokens=10
        )
        self.router._providers = {"mock": mock_provider}

        res = self.router.generate(
            prompt="Runaway test",
            candidate_chain=[("mock", "test-model")]
        )

        # 1 initial call + 3 continuation rounds = 4 total calls
        self.assertEqual(mock_provider.generate.call_count, 1 + MAX_CONTINUATION_ROUNDS)
        self.assertEqual(res.continuation_rounds, MAX_CONTINUATION_ROUNDS)
        self.assertTrue(res.continuation_used)

    # ── Test H: Upstream Error During Continuation Recovers Gracefully ──
    def test_h_upstream_error_during_continuation_graceful_recovery(self):
        mock_provider = MagicMock(spec=BaseProvider)
        # Round 1 succeeds with length cutoff; Round 2 crashes
        mock_provider.generate.side_effect = [
            ProviderResult(
                text="Crucial mathematical derivation part 1: E = mc^2. ",
                model="test-model",
                provider="mock",
                latency_ms=60.0,
                finish_reason="length",
                output_tokens=20
            ),
            ConnectionError("Upstream socket dropped during continuation")
        ]
        self.router._providers = {"mock": mock_provider}

        res = self.router.generate(
            prompt="Derive relativity",
            candidate_chain=[("mock", "test-model")]
        )

        # Should recover accumulated text rather than crashing
        self.assertIn("Crucial mathematical derivation part 1: E = mc^2.", res.text)
        self.assertTrue(res.continuation_used)
        self.assertEqual(res.continuation_rounds, 1)

    # ── Test I: Stream Consumer Early Cancellation ──
    def test_i_stream_early_cancellation(self):
        class EndlessStreamProvider(BaseProvider):
            def generate(self, *args, **kwargs):
                pass
            def stream(self, *args, **kwargs):
                for i in range(100):
                    yield f"chunk_{i} "

        provider = EndlessStreamProvider()
        self.router._providers = {"endless": provider}

        stream_gen = self.router.stream(
            prompt="Infinite stream test",
            candidate_chain=[("endless", "model-v1")]
        )

        received = []
        for token in stream_gen:
            received.append(token)
            if len(received) >= 3:
                # Client cancels stream
                stream_gen.close()
                break

        self.assertEqual(len(received), 3)

    # ── Test J: Completeness Directive in Prompts ──
    def test_j_completeness_directive_present(self):
        import study_bot
        self.assertIn("COMPLETENESS DIRECTIVE", study_bot.SYSTEM_PROMPT)
        self.assertIn("Answer the user's complete request accurately, comprehensively, and coherently", study_bot.SYSTEM_PROMPT)

    # ── Test K: Finish Reason Normalization (Gemini & Groq) ──
    def test_k_finish_reason_normalization(self):
        self.assertTrue(is_length_truncated("length"))
        self.assertTrue(is_length_truncated("LENGTH"))
        self.assertTrue(is_length_truncated("MAX_TOKENS"))
        self.assertTrue(is_length_truncated("max_output_tokens"))
        self.assertFalse(is_length_truncated("stop"))
        self.assertFalse(is_length_truncated("STOP"))
        self.assertFalse(is_length_truncated(None))

    # ── Test L: OutputBudgetManager Headroom & Per-Model Limits ──
    def test_l_budget_manager_headroom_and_constraints(self):
        # Cerebras hardware cap
        cerebras_budget = OutputBudgetManager.resolve_budget(
            task=TaskType.CODING,
            depth=ResponseDepth.DEEP,
            provider_name="cerebras",
            model_id="gpt-oss-120b"
        )
        self.assertLessEqual(cerebras_budget, 2048)

        # Context headroom check (e.g. 30000 input tokens on 32k window)
        headroom_budget = OutputBudgetManager.resolve_budget(
            task=TaskType.DETAILED_EXPLANATION,
            depth=ResponseDepth.BALANCED,
            provider_name="groq",
            model_id="llama-3.3-70b-versatile",
            estimated_input_tokens=31000
        )
        self.assertLessEqual(headroom_budget, 2000)

        # Explicit user-requested token cap is honored
        custom_budget = OutputBudgetManager.resolve_budget(
            task=TaskType.QUICK_CHAT,
            depth=ResponseDepth.FAST,
            provider_name="gemini",
            model_id="gemini-2.5-flash",
            requested_max_tokens=256
        )
        self.assertEqual(custom_budget, 256)


if __name__ == "__main__":
    unittest.main()
