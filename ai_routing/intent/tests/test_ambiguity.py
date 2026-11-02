"""
BrainyAi Ambiguity & Confidence Management Test Suite
Tests:
1. High confidence resolution for clear queries.
2. Medium confidence handling for queries with partial context.
3. Low confidence handling and graceful fallback for vague messages ("Do it", "Make this better").
4. Non-crashing resilience on empty strings, punctuation only, and malformed inputs.
"""

import unittest
from ai_routing.intent import intent_resolver, UserIntentRequest, IntentConfidenceLevel


class TestAmbiguityAndConfidence(unittest.TestCase):

    def test_high_confidence_resolution(self):
        """Verifies clear requests achieve high confidence (>= 0.85)."""
        req = UserIntentRequest(query="Fix this Python code: error aa raha hai")
        res = intent_resolver.resolve(req)

        self.assertGreaterEqual(res.confidence, 0.85)
        self.assertEqual(res.confidence_level, IntentConfidenceLevel.HIGH.value)
        self.assertEqual(res.primary_intent, "debug_code")

    def test_medium_confidence_resolution(self):
        """Verifies queries with implicit context or moderate signals classify as medium."""
        req = UserIntentRequest(query="Explain Python")
        res = intent_resolver.resolve(req)

        self.assertGreaterEqual(res.confidence, 0.60)
        self.assertIn(res.confidence_level, [IntentConfidenceLevel.HIGH.value, IntentConfidenceLevel.MEDIUM.value])

    def test_vague_elliptical_without_context_graceful_fallback(self):
        """Verifies vague requests without context fallback safely without crashing."""
        vague_queries = [
            "Do it",
            "Make this better",
            "Which is best?",
            "Explain that"
        ]

        for q in vague_queries:
            res = intent_resolver.resolve(UserIntentRequest(query=q))
            self.assertIsNotNone(res.primary_intent)
            self.assertIsNotNone(res.workflow)
            self.assertIn(res.workflow, ["normal_chat", "educational"])
            self.assertFalse(res.search_required)

    def test_empty_and_punctuation_resilience(self):
        """Verifies engine never raises exceptions on edge-case empty or whitespace inputs."""
        edge_cases = [
            "",
            "   ",
            "???",
            "...",
            "!!!",
            "\n\n\t",
            "123"
        ]

        for ec in edge_cases:
            res = intent_resolver.resolve(UserIntentRequest(query=ec))
            self.assertIsNotNone(res)
            self.assertEqual(res.workflow, "normal_chat")
            self.assertFalse(res.search_required)


if __name__ == "__main__":
    unittest.main()
