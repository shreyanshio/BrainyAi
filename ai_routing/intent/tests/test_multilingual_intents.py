"""
BrainyAi Multilingual Natural Language Intent Test Suite
Tests:
1. Hinglish conversational queries (phrases like 'samjhao', 'fix karo', 'mcq bana do').
2. Hindi (Devanagari script) queries with language preservation.
3. Gujarati (Gujarati script & Romanized Gujarati) natural phrasing.
4. Correct extraction of target response language and constraints.
"""

import unittest
from ai_routing.intent import intent_resolver, UserIntentRequest


class TestMultilingualIntents(unittest.TestCase):

    def test_hinglish_intent_recognition(self):
        """Verifies natural Hinglish queries resolve to correct intentions and workflows."""
        matrix = [
            ("Mujhe ye topic samjhao: Machine learning", "explain_concept", "educational"),
            ("Is code ko fix karo please", "debug_code", "coding"),
            ("Machine learning ke short notes bana do", "generate_notes", "educational"),
            ("Iske 5 mcq bana do", "generate_quiz", "educational"),
            ("Thoda easy karke samjhao", "simplify_content", "educational"),
        ]

        for query, expected_intent, expected_wf in matrix:
            res = intent_resolver.resolve(UserIntentRequest(query=query))
            self.assertEqual(res.primary_intent, expected_intent, f"Failed for Hinglish query: {query}")
            self.assertEqual(res.workflow, expected_wf, f"Failed workflow for Hinglish query: {query}")
            self.assertEqual(res.target_language, "hinglish")

    def test_hindi_devanagari_recognition(self):
        """Verifies Devanagari script requests resolve and retain target_language='hi'."""
        q1 = "प्रकाश संश्लेषण क्या है? सरल भाषा में समझाओ"
        res1 = intent_resolver.resolve(UserIntentRequest(query=q1))
        self.assertEqual(res1.primary_intent, "explain_concept")
        self.assertEqual(res1.topic, "photosynthesis")
        self.assertEqual(res1.target_language, "hi")
        self.assertIn("simple_language", res1.constraints)
        self.assertEqual(res1.workflow, "educational")

        q2 = "त्रुटि ठीक करो def calculate() return 10"
        res2 = intent_resolver.resolve(UserIntentRequest(query=q2))
        self.assertEqual(res2.primary_intent, "debug_code")
        self.assertEqual(res2.target_language, "hi")
        self.assertEqual(res2.workflow, "coding")

    def test_gujarati_script_and_romanized_recognition(self):
        """Verifies Gujarati script and Romanized Gujarati requests."""
        # Gujarati script
        q1 = "આ કન્સેપ્ટ સમજાવો: Binary Search Tree"
        res1 = intent_resolver.resolve(UserIntentRequest(query=q1))
        self.assertEqual(res1.primary_intent, "explain_concept")
        self.assertEqual(res1.topic, "binary search tree")
        self.assertEqual(res1.target_language, "gu")
        self.assertEqual(res1.workflow, "educational")

        # Romanized Gujarati: Notes
        q2 = "Mane notes banavi aapo: Thermodynamics"
        res2 = intent_resolver.resolve(UserIntentRequest(query=q2))
        self.assertEqual(res2.primary_intent, "generate_notes")
        self.assertEqual(res2.topic, "thermodynamics")
        self.assertEqual(res2.target_language, "gu")
        self.assertEqual(res2.workflow, "educational")

        # Romanized Gujarati: Debug code
        q3 = "Aa code fix karo error ave chhe"
        res3 = intent_resolver.resolve(UserIntentRequest(query=q3))
        self.assertEqual(res3.primary_intent, "debug_code")
        self.assertEqual(res3.target_language, "gu")
        self.assertEqual(res3.workflow, "coding")

        # Romanized Gujarati: Compare
        q4 = "Supervised ane unsupervised learning ma shu farak chhe?"
        res4 = intent_resolver.resolve(UserIntentRequest(query=q4))
        self.assertEqual(res4.primary_intent, "compare_concepts")
        self.assertIn(res4.topic, ["supervised learning", "unsupervised learning"])
        self.assertEqual(res4.target_language, "gu")
        self.assertEqual(res4.workflow, "educational")


if __name__ == "__main__":
    unittest.main()
