"""
Tests for BrainyAi Mathematics Routing Optimization, SymPy Engine, and LLM Grounding.
Verifies zero Gemini/LLM calls for pure/symbolic calculations, verified grounding injection
for explanation-based requests, conceptual LLM routing, and robust fallback handling.
"""

import unittest
from unittest.mock import patch, MagicMock
import sympy as sp

from ai_routing.maths import (
    MathematicsEngine,
    can_solve_locally,
    solve_locally,
    try_solve_locally,
    needs_explanation,
    normalize_math_characters,
    strip_explanation_request,
    safe_parse_expression
)
from ai_routing.router import router, RouterResponse
from ai_routing.tasks import TaskType
from ai_routing.policy import ResponseDepth
from ai_routing.telemetry import global_telemetry


class TestMathematicsEngineUnit(unittest.TestCase):
    """Unit tests for the deterministic SymPy-backed MathematicsEngine."""

    def setUp(self):
        self.engine = MathematicsEngine()

    def test_unicode_superscripts_normalization(self):
        """Tests that unicode superscripts are properly converted to ^ powers."""
        self.assertEqual(normalize_math_characters("x² - 5x + 6"), "x^2 - 5x + 6")
        self.assertEqual(normalize_math_characters("x³ + 2x²"), "x^3 + 2x^2")
        self.assertEqual(normalize_math_characters("3x²"), "3x^2")
        self.assertEqual(normalize_math_characters("(x² - 4)/(x - 2)"), "(x^2 - 4)/(x - 2)")
        self.assertEqual(normalize_math_characters("2⁺¹"), "2^+1")
        self.assertEqual(normalize_math_characters("y⁻²"), "y^-2")

    def test_unicode_operators_normalization(self):
        """Tests that Unicode minus, multiplication, division, and roots are normalized."""
        self.assertEqual(normalize_math_characters("5 − 3"), "5 - 3")
        self.assertEqual(normalize_math_characters("4 × 5"), "4 * 5")
        self.assertEqual(normalize_math_characters("10 ÷ 2"), "10 / 2")
        self.assertEqual(normalize_math_characters("√16"), "sqrt16")
        self.assertEqual(normalize_math_characters("π"), "pi")
        self.assertEqual(normalize_math_characters("∞"), "oo")

    def test_pure_arithmetic(self):
        """Tests pure arithmetic calculation with large and small numbers."""
        res1 = self.engine.solve("2 + 2")
        self.assertTrue(res1.is_solved)
        self.assertEqual(res1.solution, "4")
        self.assertEqual(res1.problem_type, "arithmetic")

        res2 = self.engine.solve("what is 345 * 789")
        self.assertTrue(res2.is_solved)
        self.assertEqual(res2.solution, "272205")

        res3 = self.engine.solve("calculate 10^3 + 25 * 4")
        self.assertTrue(res3.is_solved)
        self.assertEqual(res3.solution, "1100")

    def test_symbolic_equation_solving_with_unicode(self):
        """Tests solving quadratic equations containing Unicode superscripts."""
        res = self.engine.solve("Solve x² - 5x + 6 = 0")
        self.assertTrue(res.is_solved)
        self.assertEqual(res.problem_type, "algebra_equation")
        self.assertEqual(res.solution, ["2", "3"])
        self.assertEqual(res.verification_status, "verified_symbolically")
        self.assertIn("Verified", res.formatted_markdown)

    def test_symbolic_differentiation_with_unicode(self):
        """Tests differentiating expressions with Unicode superscripts."""
        res = self.engine.solve("Differentiate x³ + 2x²")
        self.assertTrue(res.is_solved)
        self.assertEqual(res.problem_type, "calculus_differentiation")
        self.assertEqual(res.solution, "3*x**2 + 4*x")
        self.assertEqual(res.latex_solution, "3 x^{2} + 4 x")

    def test_symbolic_integration_with_unicode(self):
        """Tests integrating expressions with Unicode superscripts."""
        res = self.engine.solve("Integrate 3x²")
        self.assertTrue(res.is_solved)
        self.assertEqual(res.problem_type, "calculus_integration")
        self.assertEqual(res.solution, "x**3 + C")
        self.assertEqual(res.latex_solution, "x^{3} + C")

    def test_algebraic_simplification_with_unicode(self):
        """Tests simplifying rational expressions with Unicode superscripts."""
        res = self.engine.solve("Simplify (x² - 4)/(x - 2)")
        self.assertTrue(res.is_solved)
        self.assertEqual(res.problem_type, "algebra_simplify")
        self.assertEqual(res.solution, "x + 2")
        self.assertEqual(res.latex_solution, "x + 2")

    def test_calculus_limits_natural_language(self):
        """Tests limit evaluation with natural language approaches phrases."""
        res = self.engine.solve("Find the limit of sin(x)/x as x approaches 0")
        self.assertTrue(res.is_solved)
        self.assertEqual(res.problem_type, "calculus_limit")
        self.assertEqual(str(res.solution), "1")
        self.assertEqual(res.latex_solution, "1")

    def test_coin_toss_probability(self):
        """Tests exact binomial coin toss probability calculation."""
        res = self.engine.solve("Calculate the probability of getting two heads in three coin tosses")
        self.assertTrue(res.is_solved)
        self.assertEqual(res.problem_type, "probability_combinatorics")
        self.assertEqual(res.solution, "3/8")
        self.assertEqual(res.latex_solution, "\\frac{3}{8}")
        self.assertEqual(res.verification_status, "verified_numerically")
        self.assertIn("37.5", res.formatted_markdown)

    def test_explanation_detection(self):
        """Tests explanation and pedagogical walkthrough intent detection."""
        self.assertFalse(needs_explanation("2 + 2"))
        self.assertFalse(needs_explanation("Solve x^2 - 5x + 6 = 0"))
        self.assertFalse(needs_explanation("Differentiate x^3 + 2x^2"))
        self.assertFalse(needs_explanation("Integrate 3x^2"))
        self.assertTrue(needs_explanation("Solve x^2 - 5x + 6 = 0 and explain every step"))
        self.assertTrue(needs_explanation("Differentiate x^3 + 2x^2 step by step"))
        self.assertTrue(needs_explanation("Explain the quadratic formula"))
        self.assertTrue(needs_explanation("Solve this problem with explanation in detail"))
        self.assertTrue(needs_explanation("Solve x^2 - 4 = 0 samjhao"))


    def test_natural_language_arithmetic_phrases(self):
        """Tests natural-language arithmetic phrases: divided by, multiplied by, minus, squared, cubed, square root."""
        test_queries = [
            ("What is 25 × 48?", "1200"),
            ("Find the value of 250 divided by 5.", "50"),
            ("125 multiplied by 8.", "1000"),
            ("1000 minus 275.", "725"),
            ("15% of 800.", "120"),
            ("What will be 12.5% of 640?", "80"),
            ("3² + 4².", "25"),
            ("square root of 144", "12"),
            ("5 squared + 2 cubed", "33"),
            ("2 raised to the power 8", "256")
        ]
        for query, expected_sol in test_queries:
            with self.subTest(query=query):
                self.assertTrue(self.engine.can_solve(query), f"can_solve returned False for: {query}")
                res = self.engine.solve(query)
                self.assertTrue(res.is_solved, f"Engine failed to solve: {query}")
                self.assertIn(expected_sol, str(res.solution), f"Expected {expected_sol} in {res.solution} for {query}")

    def test_limit_variations_and_unicode_arrows(self):
        """Tests limit evaluation with arrows (->, →), infix, and prefix forms."""
        limit_queries = [
            ("Calculate lim x→0 (sin x)/x", "1"),
            ("Limit of sin(x)/x, x → 0", "1"),
            ("limit of (1 + 1/x)^x as x approaches infinity", "E")
        ]
        for query, expected_sol in limit_queries:
            with self.subTest(query=query):
                self.assertTrue(self.engine.can_solve(query), f"can_solve returned False for: {query}")
                res = self.engine.solve(query)
                self.assertTrue(res.is_solved, f"Engine failed to solve limit: {query}")
                self.assertEqual(str(res.solution), expected_sol)

    def test_try_solve_locally_single_pass(self):
        """Tests try_solve_locally returns MathResult on valid math and None on non-math."""
        res_math = try_solve_locally("Find the value of 250 divided by 5.")
        self.assertIsNotNone(res_math)
        self.assertTrue(res_math.is_solved)
        self.assertEqual(res_math.solution, "50")

        res_word = try_solve_locally("A train travels 120 km in 2 hours. What is its average speed?")
        self.assertIsNone(res_word)

        res_concept = try_solve_locally("Explain the fundamental theorem of calculus")
        self.assertIsNone(res_concept)

    def test_division_by_zero_handling(self):
        """Tests that division by zero returns a safe, uncrashable error message."""
        res = self.engine.solve("10 / 0")
        self.assertFalse(res.is_solved)
        self.assertIn("mathematically undefined", res.error_message)

    def test_conceptual_math_not_solved_locally(self):
        """Tests that purely conceptual math queries are flagged for LLM routing."""
        self.assertFalse(self.engine.can_solve("Explain the quadratic formula"))
        self.assertFalse(self.engine.can_solve("Find the determinant of a 3×3 matrix"))
        self.assertFalse(self.engine.can_solve("Solve this word problem step by step"))


class TestMathematicsAIRouting(unittest.TestCase):
    """Integration tests verifying central router execution paths and zero Gemini calls for pure math."""

    @patch("ai_routing.providers.gemini_provider.GeminiProvider.generate")
    def test_pure_arithmetic_zero_gemini_calls(self, mock_gemini_generate):
        """Pure calculation (2 + 2) must execute via SymPy and make strictly 0 Gemini calls."""
        res = router.generate("2 + 2")
        self.assertEqual(mock_gemini_generate.call_count, 0)
        self.assertEqual(res.provider, "local_math_engine")
        self.assertEqual(res.model, "math_engine_v1")
        self.assertEqual(res.workflow, "sympy_only")
        self.assertTrue(res.math_verified)
        self.assertIn("4", res.text)

    @patch("ai_routing.providers.gemini_provider.GeminiProvider.generate")
    def test_symbolic_solving_zero_gemini_calls(self, mock_gemini_generate):
        """Symbolic equation (Solve x² - 5x + 6 = 0) must execute via SymPy and make strictly 0 Gemini calls."""
        res = router.generate("Solve x² - 5x + 6 = 0")
        self.assertEqual(mock_gemini_generate.call_count, 0)
        self.assertEqual(res.provider, "local_math_engine")
        self.assertEqual(res.workflow, "sympy_only")
        self.assertTrue(res.math_verified)
        self.assertIn("2", res.text)
        self.assertIn("3", res.text)

    @patch("ai_routing.providers.gemini_provider.GeminiProvider.generate")
    def test_symbolic_differentiation_zero_gemini_calls(self, mock_gemini_generate):
        """Symbolic differentiation (Differentiate x³ + 2x²) must make strictly 0 Gemini calls."""
        res = router.generate("Differentiate x³ + 2x²")
        self.assertEqual(mock_gemini_generate.call_count, 0)
        self.assertEqual(res.provider, "local_math_engine")
        self.assertEqual(res.workflow, "sympy_only")
        self.assertTrue(res.math_verified)

    @patch("ai_routing.providers.gemini_provider.GeminiProvider.generate")
    def test_symbolic_integration_zero_gemini_calls(self, mock_gemini_generate):
        """Symbolic integration (Integrate 3x²) must make strictly 0 Gemini calls."""
        res = router.generate("Integrate 3x²")
        self.assertEqual(mock_gemini_generate.call_count, 0)
        self.assertEqual(res.provider, "local_math_engine")
        self.assertEqual(res.workflow, "sympy_only")
        self.assertTrue(res.math_verified)

    @patch("ai_routing.providers.gemini_provider.GeminiProvider.generate")
    def test_symbolic_simplification_zero_gemini_calls(self, mock_gemini_generate):
        """Algebraic simplification (Simplify (x² - 4)/(x - 2)) must make strictly 0 Gemini calls."""
        res = router.generate("Simplify (x² - 4)/(x - 2)")
        self.assertEqual(mock_gemini_generate.call_count, 0)
        self.assertEqual(res.provider, "local_math_engine")
        self.assertEqual(res.workflow, "sympy_only")
        self.assertTrue(res.math_verified)

    @patch("ai_routing.providers.gemini_provider.GeminiProvider.generate")
    def test_coin_toss_probability_zero_gemini_calls(self, mock_gemini_generate):
        """Coin toss probability calculation must execute via SymPy and make strictly 0 Gemini calls."""
        res = router.generate("Calculate the probability of getting two heads in three coin tosses")
        self.assertEqual(mock_gemini_generate.call_count, 0)
        self.assertEqual(res.provider, "local_math_engine")
        self.assertEqual(res.workflow, "sympy_only")
        self.assertTrue(res.math_verified)
        self.assertIn(r"\frac{3}{8}", res.text)
        self.assertIn("37.5", res.text)

    @patch("ai_routing.providers.gemini_provider.GeminiProvider.generate")
    def test_calculation_with_explanation_hybrid_flow(self, mock_gemini_generate):
        """Calculation with explanation request triggers sympy_then_llm with verified grounding."""
        mock_provider_resp = MagicMock()
        mock_provider_resp.text = "Here is the step-by-step conceptual explanation based on the roots x = 2 and x = 3."
        mock_provider_resp.model = "gemini-3.8-flash"
        mock_provider_resp.finish_reason = "STOP"
        mock_provider_resp.input_tokens = 150
        mock_provider_resp.output_tokens = 80
        mock_gemini_generate.return_value = mock_provider_resp

        res = router.generate("Solve x² - 5x + 6 = 0 and explain every step")
        self.assertEqual(mock_gemini_generate.call_count, 1)
        self.assertEqual(res.workflow, "sympy_then_llm")
        self.assertTrue(res.math_verified)
        self.assertEqual(res.provider, "gemini")

        # Verify that verified mathematical grounding was injected into prompt/messages
        call_kwargs = mock_gemini_generate.call_args[1]
        messages = call_kwargs["messages"]
        last_msg = messages[-1]["content"]
        self.assertIn("[VERIFIED MATHEMATICAL GROUNDING FROM SYMPY ENGINE]", last_msg)
        self.assertIn("algebra_equation", last_msg)
        self.assertIn("Do NOT recalculate", last_msg)

    @patch("ai_routing.providers.gemini_provider.GeminiProvider.generate")
    def test_conceptual_math_llm_only(self, mock_gemini_generate):
        """Conceptual math (Explain quadratic formula) routes directly to LLM (llm_only)."""
        mock_provider_resp = MagicMock()
        mock_provider_resp.text = "The quadratic formula x = (-b +/- sqrt(b^2 - 4ac))/(2a) is derived by completing the square."
        mock_provider_resp.model = "gemini-3.8-flash"
        mock_provider_resp.finish_reason = "STOP"
        mock_provider_resp.input_tokens = 50
        mock_provider_resp.output_tokens = 60
        mock_gemini_generate.return_value = mock_provider_resp

        res = router.generate("Explain the quadratic formula")
        self.assertEqual(mock_gemini_generate.call_count, 1)
        self.assertEqual(res.workflow, "llm_only")
        self.assertFalse(res.math_verified)

    @patch("ai_routing.providers.gemini_provider.GeminiProvider.generate")
    def test_hybrid_flow_fallback_if_llm_fails(self, mock_gemini_generate):
        """If LLM explanation fails, hybrid flow returns verified SymPy calculation safely."""
        mock_gemini_generate.side_effect = RuntimeError("Gemini quota 429")
        with patch("ai_routing.providers.groq_provider.GroqProvider.generate", side_effect=RuntimeError("Groq 429")), \
             patch("ai_routing.providers.cerebras_provider.CerebrasProvider.generate", side_effect=RuntimeError("Cerebras 429")), \
             patch("ai_routing.providers.openrouter_provider.OpenRouterProvider.generate", side_effect=RuntimeError("OpenRouter 429")), \
             patch("ai_routing.providers.sambanova_provider.SambaNovaProvider.generate", side_effect=RuntimeError("SambaNova 429")):
            res = router.generate("Solve x² - 5x + 6 = 0 and explain every step")
            self.assertEqual(res.provider, "local_math_engine")
            self.assertTrue(res.math_verified)
            self.assertEqual(res.workflow, "sympy_fallback")
            self.assertIn("The roots are", res.text)



    @patch("ai_routing.providers.gemini_provider.GeminiProvider.generate")
    @patch("ai_routing.providers.groq_provider.GroqProvider.generate")
    @patch("ai_routing.providers.cerebras_provider.CerebrasProvider.generate")
    @patch("ai_routing.providers.sambanova_provider.SambaNovaProvider.generate")
    @patch("ai_routing.providers.openrouter_provider.OpenRouterProvider.generate")
    def test_natural_language_arithmetic_zero_remote_calls(
        self, mock_openrouter, mock_sambanova, mock_cerebras, mock_groq, mock_gemini
    ):
        """Natural-language arithmetic queries must make 0 calls to any remote LLM provider."""
        queries = [
            "What is 25 × 48?",
            "Find the value of 250 divided by 5.",
            "125 multiplied by 8.",
            "1000 minus 275.",
            "15% of 800.",
            "What will be 12.5% of 640?",
            "3² + 4².",
            "Calculate lim x→0 (sin x)/x"
        ]
        for q in queries:
            with self.subTest(query=q):
                res = router.generate(q)
                self.assertEqual(res.provider, "local_math_engine")
                self.assertEqual(res.workflow, "sympy_only")
                self.assertEqual(mock_gemini.call_count, 0)
                self.assertEqual(mock_groq.call_count, 0)
                self.assertEqual(mock_cerebras.call_count, 0)
                self.assertEqual(mock_sambanova.call_count, 0)
                self.assertEqual(mock_openrouter.call_count, 0)


class TestMathematicsStreaming(unittest.TestCase):
    """Tests streaming fast-path for pure math and verified grounding."""

    def test_streaming_pure_math_zero_llm(self):
        """Streaming pure math returns immediate SymPy markdown chunk with zero LLM calls."""
        chunks = list(router.stream("what is 345 * 789"))
        self.assertEqual(len(chunks), 1)
        self.assertIn("272205", chunks[0])


if __name__ == "__main__":
    unittest.main()
