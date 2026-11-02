"""
BrainyAi Context Awareness & Follow-up Resolution Test Suite
Tests:
1. Elliptical pronoun resolution ("it", "that").
2. Code optimization follow-ups preserving previous code reference.
3. Search evidence reuse from prior search results.
4. Sibling task continuation ("now give me more examples", "convert into a table").
5. Topic shift detection (clearing old context on new subjects).
"""

import unittest
from ai_routing.intent import intent_resolver, UserIntentRequest


class TestContextAwareness(unittest.TestCase):

    def test_shorter_answer_followup_preserves_topic(self):
        """Verifies 'Make it shorter' inherits prior topic and resolves target."""
        messages = [
            {"role": "user", "content": "Explain neural networks in detail."},
            {"role": "assistant", "content": "A neural network is a computational model inspired by the human brain..."}
        ]

        req = UserIntentRequest(
            query="Make it shorter",
            messages=messages
        )
        res = intent_resolver.resolve(req)

        self.assertEqual(res.primary_intent, "request_shorter_answer")
        self.assertEqual(res.topic, "neural network")
        self.assertTrue(res.context_required)
        self.assertEqual(res.context_reference_target, "previous_answer")
        self.assertIn("concise", res.constraints)
        self.assertEqual(res.workflow, "normal_chat")

    def test_code_optimization_followup(self):
        """Verifies 'Now optimize it' after code generation resolves to optimize_code."""
        messages = [
            {"role": "user", "content": "Write a Python function for bubble sort."},
            {"role": "assistant", "content": "def bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n-i-1):\n            if arr[j] > arr[j+1]:\n                arr[j], arr[j+1] = arr[j+1], arr[j]\n    return arr"}
        ]

        req = UserIntentRequest(
            query="Now optimize it",
            messages=messages
        )
        res = intent_resolver.resolve(req)

        self.assertEqual(res.primary_intent, "optimize_code")
        self.assertEqual(res.topic, "python")
        self.assertTrue(res.context_required)
        self.assertEqual(res.context_reference_target, "previous_code")
        self.assertEqual(res.workflow, "coding")

    def test_search_evidence_reuse_from_prior_results(self):
        """Verifies 'Explain the second result you found earlier' reuses search without re-querying web."""
        messages = [
            {"role": "user", "content": "What are the latest AI coding benchmarks?"},
            {"role": "assistant", "content": "LIVE WEB RESEARCH FINDINGS:\n[1] Benchmark A (https://a.com)\n[2] Benchmark B (https://b.com)"}
        ]

        req = UserIntentRequest(
            query="Explain the second result you found earlier",
            messages=messages
        )
        res = intent_resolver.resolve(req)

        self.assertEqual(res.primary_intent, "explain_concept")
        self.assertIn("reuse_search", res.constraints)
        self.assertFalse(res.search_required)
        self.assertTrue(res.context_required)
        self.assertEqual(res.context_reference_target, "search_result_item")

    def test_sibling_task_more_examples(self):
        """Verifies 'Give me more examples' inherits topic from prior turn."""
        messages = [
            {"role": "user", "content": "Explain polymorphism in object-oriented programming."},
            {"role": "assistant", "content": "Polymorphism allows objects of different classes to be treated as objects of a common superclass."}
        ]

        req = UserIntentRequest(
            query="Give me more examples",
            messages=messages
        )
        res = intent_resolver.resolve(req)

        self.assertEqual(res.primary_intent, "give_examples")
        self.assertEqual(res.topic, "polymorphism")
        self.assertTrue(res.context_required)

    def test_convert_to_table_format_followup(self):
        """Verifies 'Convert it into a table' applies table format constraint while preserving topic."""
        messages = [
            {"role": "user", "content": "Compare TCP and UDP protocols."},
            {"role": "assistant", "content": "TCP is connection-oriented and reliable. UDP is connectionless and faster."}
        ]

        req = UserIntentRequest(
            query="Convert it into a table",
            messages=messages
        )
        res = intent_resolver.resolve(req)

        self.assertIn("format:table", res.constraints)
        self.assertTrue(res.context_required)

    def test_topic_shift_clears_old_context(self):
        """Verifies that an unrelated query clears old topic and does not force prior context."""
        messages = [
            {"role": "user", "content": "Write a Python script for web scraping."},
            {"role": "assistant", "content": "import requests\nfrom bs4 import BeautifulSoup\n..."}
        ]

        # Brand new topic in natural sciences
        req = UserIntentRequest(
            query="Explain photosynthesis in detail",
            messages=messages
        )
        res = intent_resolver.resolve(req)

        self.assertEqual(res.primary_intent, "explain_concept")
        self.assertEqual(res.topic, "photosynthesis")
        self.assertNotEqual(res.topic, "python")
        self.assertFalse(res.context_required)
        self.assertEqual(res.workflow, "educational")


if __name__ == "__main__":
    unittest.main()
