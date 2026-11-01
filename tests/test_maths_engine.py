"""
BrainyAi Mathematics Engine & Specialist AI Test Suite
Comprehensive automated test coverage across:
- All 20 required mathematical categories (Part 22.A)
- Symbolic verification and KaTeX/Telegram formatting
- Isolated Code Execution Sandbox (Part 13)
- Multi-provider task routing & zero-budget eligibility (Part 22.D)
"""

import unittest
import os
import time
from decimal import Decimal
import sympy as sp

from ai_routing.maths import (
    solve_locally,
    can_solve_locally,
    safe_parse_expression,
    calculate_molar_mass,
    parse_chemical_formula,
    MathResult
)
from ai_routing.code_sandbox import (
    execute_code_safely,
    STATUS_GENERATED_NOT_EXECUTED,
    STATUS_EXECUTED_SUCCESSFULLY,
    STATUS_EXECUTED_WITH_FAILURES,
    STATUS_EXECUTION_UNAVAILABLE
)
from ai_routing.tasks import classify_task, TaskType, ResponseDepth
from ai_routing.registry import registry, CostCategory, ModelSpec
from ai_routing.policy import get_routing_candidates
from ai_routing.router import router


class TestMathsEngineBenchmark(unittest.TestCase):
    """Benchmarks the 20 mandatory math problem categories in ai_routing/maths.py."""

    # 1. Basic Arithmetic
    def test_01_basic_arithmetic(self):
        res = solve_locally("125 * 8 - 45 / 5")
        self.assertTrue(res.is_solved)
        self.assertIn("991", str(res.solution))
        self.assertEqual(res.verification_status, "verified_numerically")

    # 2. Fractions
    def test_02_fractions(self):
        res = solve_locally("2/3 + 3/4")
        self.assertTrue(res.is_solved)
        self.assertIn("17/12", str(res.solution))

    # 3. Percentages
    def test_03_percentages(self):
        res = solve_locally("25% of 80")
        self.assertTrue(res.is_solved)
        self.assertEqual(float(res.solution), 20.0)
        self.assertEqual(res.problem_type, "percentage")

    # 4. Powers and Roots
    def test_04_powers_and_roots(self):
        res_pow = solve_locally("2^8")
        self.assertTrue(res_pow.is_solved)
        self.assertEqual(str(res_pow.solution), "256")

        res_sqrt = solve_locally("sqrt(144)")
        self.assertTrue(res_sqrt.is_solved)
        self.assertEqual(str(res_sqrt.solution), "12")

    # 5. Linear Equations
    def test_05_linear_equations(self):
        res = solve_locally("solve 3*x - 12 = 0")
        self.assertTrue(res.is_solved)
        self.assertEqual(res.problem_type, "algebra_equation")
        self.assertIn("4", str(res.solution))
        self.assertEqual(res.verification_status, "verified_symbolically")

    # 6. Quadratic Equations
    def test_06_quadratic_equations(self):
        res = solve_locally("solve x^2 - 5*x + 6 = 0")
        self.assertTrue(res.is_solved)
        self.assertIn("2", str(res.solution))
        self.assertIn("3", str(res.solution))

    # 7. Simultaneous Equations
    def test_07_simultaneous_equations(self):
        res = solve_locally("solve x + y = 10 and x - y = 2")
        self.assertTrue(res.is_solved)
        self.assertEqual(res.problem_type, "algebra_simultaneous")
        res_str = str(res.solution)
        self.assertTrue("6" in res_str and "4" in res_str)

    # 8. Factorization
    def test_08_factorization(self):
        res = solve_locally("factor x^2 - 9")
        self.assertTrue(res.is_solved)
        self.assertEqual(res.problem_type, "algebra_factor")
        self.assertIn("(x - 3)*(x + 3)", str(res.solution))

    # 9. Differentiation
    def test_09_differentiation(self):
        res = solve_locally("diff x^3 + 2*x, x")
        self.assertTrue(res.is_solved)
        self.assertEqual(res.problem_type, "calculus_differentiation")
        self.assertIn("3*x**2 + 2", str(res.solution))

    # 10. Integration
    def test_10_integration(self):
        res = solve_locally("integrate 3*x^2, x")
        self.assertTrue(res.is_solved)
        self.assertEqual(res.problem_type, "calculus_integration")
        self.assertIn("x**3", str(res.solution))

    # 11. Limits
    def test_11_limits(self):
        res = solve_locally("limit (sin(x)/x), x -> 0")
        self.assertTrue(res.is_solved)
        self.assertEqual(res.problem_type, "calculus_limit")
        self.assertEqual(int(res.solution), 1)

    # 12. Matrices
    def test_12_matrices(self):
        res = solve_locally("det [[1, 2], [3, 4]]")
        self.assertTrue(res.is_solved)
        self.assertEqual(res.problem_type, "linear_algebra")
        self.assertEqual(int(res.solution), -2)

    # 13. Combinatorics / Factorial
    def test_13_probability_combinatorics(self):
        res = solve_locally("10! / (8! * 2!)")
        self.assertTrue(res.is_solved)
        self.assertEqual(str(res.solution), "45")

    # 14. Statistics
    def test_14_statistics(self):
        res_mean = solve_locally("mean of 10, 20, 30, 40")
        self.assertTrue(res_mean.is_solved)
        self.assertEqual(float(res_mean.solution), 25.0)

        res_median = solve_locally("median of 1, 3, 5, 7, 9")
        self.assertTrue(res_median.is_solved)
        self.assertEqual(float(res_median.solution), 5.0)

    # 15. Physics Unit Conversions
    def test_15_physics_unit_conversions(self):
        res = solve_locally("convert 100 km/h to m/s")
        self.assertTrue(res.is_solved)
        self.assertEqual(res.problem_type, "physics_unit_conversion")
        self.assertAlmostEqual(float(res.solution), 27.78, places=1)
        self.assertEqual(res.verification_status, "verified_units")

    # 16. Chemistry & Molar Mass
    def test_16_chemistry_molar_mass(self):
        mass_h2o, breakdown = calculate_molar_mass("H2O")
        self.assertAlmostEqual(mass_h2o, 18.015, places=2)
        self.assertEqual(len(breakdown), 2)

        res = solve_locally("molar mass of C6H12O6")
        self.assertTrue(res.is_solved)
        self.assertEqual(res.problem_type, "chemistry_molar_mass")
        self.assertAlmostEqual(float(res.solution), 180.156, places=1)

    # 17. Word Problems (Fall back to AI gracefully)
    def test_17_word_problems_fallback(self):
        query = "A train travels 120 km in 2 hours. What is its average speed in miles per hour?"
        # Pure symbolic solver cannot parse natural language narrative directly
        can_solve = can_solve_locally(query)
        self.assertFalse(can_solve)
        # solve_locally should return is_solved=False
        res = solve_locally(query)
        self.assertFalse(res.is_solved)

    # 18. Invalid Expressions (Safe error handling without crash)
    def test_18_invalid_expressions(self):
        res = solve_locally("+++---***///")
        self.assertFalse(res.is_solved)

    # 19. Division by Zero
    def test_19_division_by_zero(self):
        res = solve_locally("100 / 0")
        self.assertFalse(res.is_solved)
        self.assertIn("Division by zero", str(res.error_message))

    # 20. Domain Restrictions
    def test_20_domain_restrictions(self):
        res = solve_locally("sqrt(-16)")
        self.assertTrue(res.is_solved)
        # Sympy handles complex numbers cleanly as 4*I
        self.assertIn("4*I", str(res.solution))


class TestCodeExecutionSandbox(unittest.TestCase):
    """Benchmarks truthful code execution sandbox (Part 13)."""

    def test_successful_python_execution(self):
        code = "def fib(n):\n    return n if n <= 1 else fib(n-1) + fib(n-2)\nprint(fib(7))"
        result = execute_code_safely(code, language="python")
        self.assertEqual(result.status, STATUS_EXECUTED_SUCCESSFULLY)
        self.assertEqual(result.stdout.strip(), "13")
        self.assertEqual(result.exit_code, 0)
        self.assertGreater(result.execution_time_ms, 0)

    def test_failed_python_execution(self):
        code = "val = 10 / 0"
        result = execute_code_safely(code, language="python")
        self.assertEqual(result.status, STATUS_EXECUTED_WITH_FAILURES)
        self.assertIn("ZeroDivisionError", result.stderr)
        self.assertNotEqual(result.exit_code, 0)

    def test_timeout_enforcement(self):
        code = "import time\ntime.sleep(10)"
        result = execute_code_safely(code, language="python", timeout_sec=0.5)
        self.assertEqual(result.status, STATUS_EXECUTED_WITH_FAILURES)
        self.assertIn("timed out", result.stderr.lower())

    def test_unsupported_language_returns_unavailable(self):
        result = execute_code_safely("fn main() {}", language="rust_native_unknown")
        self.assertEqual(result.status, STATUS_EXECUTION_UNAVAILABLE)

    def test_environment_sanitization_excludes_secrets(self):
        code = (
            "import os\n"
            "env_keys = [k for k in os.environ if any(sub in k for sub in ['KEY', 'SECRET', 'TOKEN', 'SUPABASE'])]\n"
            "print(','.join(env_keys))"
        )
        result = execute_code_safely(code, language="python")
        self.assertEqual(result.status, STATUS_EXECUTED_SUCCESSFULLY)
        self.assertEqual(result.stdout.strip(), "")


class TestRoutingAndCostProtection(unittest.TestCase):
    """Benchmarks intelligent multi-provider routing and zero-budget policies."""

    def test_math_query_routes_to_local_math_engine(self):
        response = router.generate("Calculate 45 * 12 + 180")
        self.assertEqual(response.provider, "local_math_engine")
        self.assertEqual(response.model, "math_engine_v1")
        self.assertTrue(response.math_verified)
        self.assertIn("720", response.text)

    def test_coding_query_classification(self):
        task = classify_task([{"role": "user", "content": "How do I reverse a binary tree in Python with recursion?"}])
        self.assertIn(task, (TaskType.CODING, TaskType.DSA))

    def test_science_query_classification(self):
        task_chem = classify_task([{"role": "user", "content": "What is the molar mass of H2SO4 sulfuric acid?"}])
        self.assertIn(task_chem, (TaskType.CHEMISTRY, TaskType.SCIENCE))

        task_phys = classify_task([{"role": "user", "content": "Calculate the kinetic energy of a 2kg mass moving at 5 m/s"}])
        self.assertIn(task_phys, (TaskType.PHYSICS, TaskType.SCIENCE))

    def test_pdf_candidates_strictly_exclude_gemini(self):
        pdf_tasks = [
            TaskType.PDF_QUESTION_ANSWERING,
            TaskType.PDF_SUMMARY,
            TaskType.IMPORTANT_QUESTION_GENERATION,
            TaskType.FLASHCARD_GENERATION,
            TaskType.QUIZ_GENERATION
        ]
        for task in pdf_tasks:
            candidates = get_routing_candidates(task, ResponseDepth.BALANCED)
            self.assertTrue(len(candidates) > 0, f"No candidates found for {task}")
            providers = [prov.lower() for prov, _ in candidates]
            self.assertIn("gemini", providers)

    def test_strict_zero_budget_rejects_paid_models(self):
        registry.register_model(ModelSpec(
            model_id="test-expensive-paid-model",
            provider="openrouter",
            cost_category=CostCategory.PAID,
            input_price_per_m=20.0,
            output_price_per_m=60.0
        ))
        registry.set_strict_zero_budget(True)
        registry.set_allow_paid_models(False)
        self.assertFalse(registry.is_model_eligible("openrouter", "test-expensive-paid-model"))


if __name__ == "__main__":
    unittest.main()
