"""
BrainyAi Intent Matching Test Suite
Tests:
1. Same topic, different user intentions.
2. Different wording/paraphrases, same intention.
3. STEM math derivations vs problem solving.
4. Multi-intent compound requests.
5. Explicit negative constraints and formatting boundaries.
"""

import unittest
from ai_routing.intent import intent_resolver, UserIntentRequest


class TestIntentMatching(unittest.TestCase):

    def test_same_topic_different_intents_python(self):
        """Verifies that the same topic ('Python') correctly resolves to distinct intentions."""
        matrix = [
            ("Explain Python", "explain_concept", "educational"),
            ("Teach me Python from zero", "learn_from_zero", "educational"),
            ("Write Python code", "generate_code", "coding"),
            ("Fix this Python code: def add(a, b) return a + b", "debug_code", "coding"),
            ("Give me notes on Python data structures", "generate_notes", "educational"),
            ("Compare Python and Java", "compare_concepts", "educational"),
            ("Check the latest official Python 3.13 documentation", "find_documentation", "coding_search"),
            ("Why does this Python code raise IndexError?", "understand_error", "coding"),
        ]

        for query, expected_intent, expected_wf in matrix:
            res = intent_resolver.resolve(UserIntentRequest(query=query))
            self.assertEqual(res.primary_intent, expected_intent, f"Failed intent for query: {query}")
            self.assertEqual(res.workflow, expected_wf, f"Failed workflow for query: {query}")
            self.assertEqual(res.topic, "python", f"Topic should be python for: {query}")

    def test_different_wording_same_intent_explain(self):
        """Verifies that different paraphrases all resolve to 'explain_concept'."""
        queries = [
            "Explain transformer architecture",
            "Help me understand attention mechanism",
            "Break down backpropagation for me",
            "How does gradient descent work?",
            "Samjhao binary search tree kya hota hai",
            "Aa concept samjavo: photosynthesis"
        ]

        for q in queries:
            res = intent_resolver.resolve(UserIntentRequest(query=q))
            self.assertEqual(res.primary_intent, "explain_concept", f"Failed for query: {q}")
            self.assertIn(res.workflow, ["educational", "normal_chat"])

    def test_stem_problem_solving_and_working(self):
        """Verifies distinction between raw problem solving and explicit working/derivation requests."""
        # Raw problem solving
        solve_res = intent_resolver.resolve(UserIntentRequest(query="Solve for x: 3x + 12 = 45"))
        self.assertEqual(solve_res.primary_intent, "solve_problem")
        self.assertEqual(solve_res.workflow, "mathematics")

        integral_res = intent_resolver.resolve(UserIntentRequest(query="Evaluate the integral of x^2 * sin(x) dx"))
        self.assertEqual(integral_res.primary_intent, "solve_problem")
        self.assertEqual(integral_res.workflow, "mathematics")

        # Explicit working / proof steps
        steps_res = intent_resolver.resolve(UserIntentRequest(query="Show working for finding eigenvalues of [[2, 1], [1, 2]]"))
        self.assertEqual(steps_res.primary_intent, "show_working")
        self.assertIn("show_steps", steps_res.constraints)
        self.assertEqual(steps_res.workflow, "mathematics")

    def test_multi_intent_compound_requests(self):
        """Verifies that multi-clause queries retain secondary intents in ordered tasks."""
        # 3 intents in one sentence
        q1 = "Explain recursion, show Python code, and give me 5 questions"
        res1 = intent_resolver.resolve(UserIntentRequest(query=q1))
        self.assertEqual(res1.primary_intent, "explain_concept")
        self.assertIn("generate_code", res1.secondary_intents)
        self.assertIn("generate_questions", res1.secondary_intents)
        self.assertEqual(res1.topic, "recursion")
        self.assertIn("language:python", res1.constraints)
        self.assertIn("count:5", res1.constraints)
        self.assertEqual(res1.workflow, "coding")  # Adjusted because code generation is requested

        # 2 intents: concept + quiz
        q2 = "Explain neural networks and make 5 MCQs"
        res2 = intent_resolver.resolve(UserIntentRequest(query=q2))
        self.assertEqual(res2.primary_intent, "explain_concept")
        self.assertIn("generate_quiz", res2.secondary_intents)
        self.assertIn("count:5", res2.constraints)

    def test_negative_instructions_and_constraints(self):
        """Verifies that negative constraints strictly override tool/code behavior."""
        # No search
        q_no_search = "Explain quantum mechanics without using Google"
        res_no_search = intent_resolver.resolve(UserIntentRequest(query=q_no_search))
        self.assertEqual(res_no_search.primary_intent, "explain_concept")
        self.assertIn("no_web_search", res_no_search.constraints)
        self.assertFalse(res_no_search.search_required)

        # No code
        q_no_code = "Don't give me code, just explain the logic of merge sort"
        res_no_code = intent_resolver.resolve(UserIntentRequest(query=q_no_code))
        self.assertEqual(res_no_code.primary_intent, "explain_concept")
        self.assertIn("no_code", res_no_code.constraints)
        self.assertNotEqual(res_no_code.workflow, "coding")

        # Brevity
        q_brevity = "Make notes on mitosis but keep it short"
        res_brevity = intent_resolver.resolve(UserIntentRequest(query=q_brevity))
        self.assertEqual(res_brevity.primary_intent, "generate_notes")
        self.assertIn("concise", res_brevity.constraints)

        # Language constraint with negative exclusion
        q_lang = "Write a script in Python not JavaScript to scrape quotes"
        res_lang = intent_resolver.resolve(UserIntentRequest(query=q_lang))
        self.assertEqual(res_lang.primary_intent, "generate_code")
        self.assertIn("language:python", res_lang.constraints)
        self.assertIn("exclude:javascript", res_lang.constraints)


if __name__ == "__main__":
    unittest.main()
