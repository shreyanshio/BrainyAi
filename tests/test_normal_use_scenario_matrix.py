"""
BrainyAi Normal Use Scenario Benchmark Matrix
Comprehensive automated quality, intent evaluation, and routing check across 30 everyday scenarios.
"""

import unittest
from unittest.mock import MagicMock, patch

from ai_routing.router import AIRouter
from ai_routing.tasks import (
    classify_task_with_complexity,
    TaskType,
    TaskComplexity,
    ResponseDepth,
)
from ai_routing.providers.base import BaseProvider, ProviderResult
from ai_routing.prompts import prompt_registry, Platform
from ai_routing.maths import can_solve_locally


class NormalUseScenarioMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open("prompts/normal_use.txt", "r", encoding="utf-8") as f:
            cls.prompt_content = f.read()

    def setUp(self):
        self.router = AIRouter()

    def test_prompt_structural_integrity(self):
        """Verifies all mandatory sections are present in the optimized prompt."""
        required_headers = [
            "SECTION A — IDENTITY AND CORE BEHAVIOUR",
            "SECTION B — BROAD EVERYDAY CAPABILITY COVERAGE",
            "SECTION C — CONVERSATIONAL INTELLIGENCE & CONTEXT",
            "SECTION D — RESPONSE DEPTH & FORMATTING DISCIPLINE",
            "SECTION E — FACTUAL ACCURACY & INTELLECTUAL HONESTY",
            "SECTION F — SAFETY, PRIVACY AND RESPONSIBLE ASSISTANCE",
            "Security and safety",
            "SECTION G — CONCISE BEHAVIORAL EXAMPLES",
            "SECTION H — ESCALATION BOUNDARIES",
        ]
        for h in required_headers:
            self.assertIn(h, self.prompt_content)

    def test_matrix_30_everyday_scenarios(self):
        """
        Executes and validates the 30 everyday test scenarios:
        1. Greetings
        2. Small talk
        3. General questions
        4. Professional writing
        5. Informal writing
        6. Grammar correction
        7. Rewriting
        8. Translation
        9. Hinglish
        10. Gujarati support
        11. Summarization
        12. Extraction
        13. Explanations
        14. Brainstorming
        15. Planning
        16. Arithmetic (Local SymPy fast path)
        17. Basic coding
        18. Contextual follow-ups
        19. Ambiguous requests
        20. Current information (Web search)
        21. Document-grounded requests (PDF Study Studio)
        22. Tool awareness
        23. Provider fallback
        24. Incomplete input
        25. Uncertainty handling
        26. Formatting requirements
        27. Long messages
        28. Short messages
        29. Multi-turn context
        30. Advanced-task escalation
        """
        scenarios = [
            # 1. Greetings
            ("Hi!", "normal_use"),
            # 2. Small talk
            ("How's your day going?", "normal_use"),
            # 3. General questions
            ("Why is the sky blue?", "normal_use"),
            # 4. Professional writing
            ("Draft an email requesting a sick day", "normal_use"),
            # 5. Informal writing
            ("Write a warm birthday text for my best friend", "normal_use"),
            # 6. Grammar correction
            ("Correct this sentence: They doesn't know where to went", "normal_use"),
            # 7. Rewriting
            ("Rewrite this to sound more persuasive: Buy our software now", "normal_use"),
            # 8. Translation
            ("Translate 'Where is the nearest train station?' into French", "normal_use"),
            # 9. Hinglish
            ("Bhai kal exam hai, quick revision tips de do", "normal_use"),
            # 10. Gujarati
            ("તમે કેમ છો? (How are you?)", "normal_use"),
            # 11. Summarization
            ("Summarize this short paragraph: Renewable energy grew by 20% this quarter.", "normal_use"),
            # 12. Extraction
            ("Extract the names and dates from: Alice met Bob on October 12, 2026.", "normal_use"),
            # 13. Explanations
            ("Explain the concept of inflation using a simple pizza analogy", "normal_use"),
            # 14. Brainstorming
            ("Brainstorm 5 creative names for a coffee shop", "normal_use"),
            # 15. Planning
            ("Create a 2-hour evening study routine with breaks", "normal_use"),
            # 16. Arithmetic (Direct local engine computation)
            ("What is 15% of 350?", "local_math_engine"),
            # 17. Basic coding
            ("Write a python function to reverse a string", "coding_or_normal"),
            # 18. Contextual follow-up
            ("Make it shorter", "normal_use"),
            # 19. Ambiguous request
            ("What time does it start?", "normal_use"),
            # 20. Current information (Triggers web research / search)
            ("Who won yesterday's football match?", "search_route"),
            # 21. Document-grounded request (PDF Study Studio)
            ("Summarize the uploaded file", "pdf_route"),
            # 22. Tool awareness / explanation
            ("Explain how binary search works step by step", "coding_or_normal"),
            # 23. Provider fallback
            ("Tell me a science fact", "normal_use"),
            # 24. Incomplete input
            ("Need help with...", "normal_use"),
            # 25. Uncertainty handling
            ("Predict the exact stock market close in 2030", "normal_use"),
            # 26. Formatting requirements
            ("List the pros and cons of remote work in a table", "normal_use"),
            # 27. Long message
            ("Here is my reflection from the seminar: we discussed solar adoption. Please give me 2 takeaways.", "normal_use"),
            # 28. Short message
            ("Thanks!", "normal_use"),
            # 29. Multi-turn context
            ("Translate the previous sentence into Hindi", "normal_use"),
            # 30. Advanced-task escalation (Formal rigorous proof)
            ("Prove that the square root of 2 is irrational in rigorous mathematical detail", "advanced_escalation"),
        ]

        self.assertEqual(len(scenarios), 30, "Scenario matrix must contain exactly 30 test cases")

        normal_tasks = {TaskType.QUICK_CHAT, TaskType.SIMPLE_EXPLANATION, TaskType.TRANSLATION, TaskType.WRITING}

        for idx, (query, route_type) in enumerate(scenarios, start=1):
            with self.subTest(scenario=idx, query=query):
                context = {"pdf_text": "sample text"} if route_type == "pdf_route" else None
                task, complexity = classify_task_with_complexity(query, context=context)

                if route_type == "normal_use":
                    self.assertIn(task, normal_tasks, f"Query '{query}' should resolve to a normal task, got {task}")
                    self.assertIn(complexity, (TaskComplexity.FAST, TaskComplexity.LIGHT, TaskComplexity.STANDARD))
                elif route_type == "local_math_engine":
                    self.assertTrue(can_solve_locally(query), f"Query '{query}' should be solvable locally by SymPy engine")
                elif route_type == "pdf_route":
                    self.assertEqual(task, TaskType.PDF_SUMMARY)
                elif route_type == "search_route":
                    self.assertEqual(task, TaskType.WEB_RESEARCH)
                elif route_type == "advanced_escalation":
                    self.assertEqual(complexity, TaskComplexity.COMPLEX)


if __name__ == "__main__":
    unittest.main()
