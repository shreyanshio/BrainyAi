"""
BrainyAi Routing & Workflow Mapping Test Suite
Tests:
1. Complete mapping from Intent ID to Brainy Workflows and Central Prompt Registry IDs.
2. Search requirement enforcement and Tavily + DuckDuckGo configuration.
3. Provider and model prioritization (Gemini primary, Groq fallback).
4. Fast path vs Deep path execution flags.
5. End-to-end integration via WorkflowRouter.route().
"""

import unittest
from ai_routing.workflow_router import workflow_router
from ai_routing.intent import intent_resolver, UserIntentRequest


class TestRoutingMapping(unittest.TestCase):

    def test_workflow_and_prompt_mappings(self):
        """Verifies every major intent maps to the authoritative workflow and prompt."""
        cases = [
            ("Explain the theory of relativity", "educational", "brainy_comprehensive", False, False),
            ("Write Python code for mergesort", "coding", "coding", False, True),
            ("Solve the differential equation dy/dx = 3x^2", "mathematics", "mathematics", False, True),
            ("Find the latest news about solar flare events in 2026", "web_search", "web_search", True, False),
            ("Check official Next.js App Router documentation", "coding_search", "coding", True, False),
            ("Define momentum", "normal_chat", "normal_chat", False, True),
            ("Hi Brainy!", "normal_chat", "normal_chat", False, True),
        ]

        for query, expected_wf, expected_prompt, expected_search, expected_fast in cases:
            decision = workflow_router.route(content=query)
            self.assertEqual(decision.workflow, expected_wf, f"Wrong workflow for {query}")
            self.assertEqual(decision.prompt_id, expected_prompt, f"Wrong prompt for {query}")
            self.assertEqual(decision.search_required, expected_search, f"Wrong search policy for {query}")
            self.assertEqual(decision.is_fast_path, expected_fast, f"Wrong fast_path for {query}")
            self.assertIsNotNone(decision.intent_result, f"Missing intent_result on decision for {query}")

    def test_gemini_first_groq_fallback_policy(self):
        """Verifies provider routing strictly adheres to Gemini primary, Groq fallback."""
        educational_decision = workflow_router.route(content="Explain mitosis in cellular biology")
        self.assertEqual(educational_decision.primary_provider, "gemini")
        self.assertEqual(educational_decision.primary_model, "gemini-3.8-flash")
        self.assertEqual(educational_decision.fallback_provider, "groq")
        self.assertEqual(educational_decision.fallback_model, "llama-3.3-70b-versatile")

        normal_decision = workflow_router.route(content="Hello, who are you?")
        self.assertEqual(normal_decision.primary_provider, "gemini")
        self.assertEqual(normal_decision.primary_model, "gemini-3.5-flash-lite")
        self.assertEqual(normal_decision.fallback_provider, "groq")
        self.assertEqual(normal_decision.fallback_model, "llama-3.1-8b-instant")

    def test_pdf_studio_grounded_workflows(self):
        """Verifies document context routes strictly to PDF Studio with search forbidden."""
        doc_ctx = {"doc_id": "doc-123", "pdf_text": "Sample lecture notes on machine learning..."}

        # PDF Q&A
        qa_decision = workflow_router.route(
            content="What does the document state about loss functions?",
            document_context=doc_ctx
        )
        self.assertEqual(qa_decision.workflow, "pdf_qa")
        self.assertEqual(qa_decision.prompt_id, "pdf_qa")
        self.assertFalse(qa_decision.search_required)

        # PDF Notes
        notes_decision = workflow_router.route(
            content="Make study notes from this PDF",
            document_context=doc_ctx
        )
        self.assertEqual(notes_decision.workflow, "pdf_notes")
        self.assertEqual(notes_decision.prompt_id, "pdf_notes")
        self.assertFalse(notes_decision.search_required)

        # PDF Quiz
        quiz_decision = workflow_router.route(
            content="Create 5 MCQs from the uploaded file",
            document_context=doc_ctx
        )
        self.assertEqual(quiz_decision.workflow, "pdf_quiz")
        self.assertEqual(quiz_decision.prompt_id, "pdf_quiz")
        self.assertFalse(quiz_decision.search_required)

    def test_search_provider_duo_tavily_duckduckgo(self):
        """Verifies search requests always specify both Tavily and DuckDuckGo."""
        decision = workflow_router.route(content="Find latest news about AI safety guidelines 2026")
        self.assertTrue(decision.search_required)
        self.assertIn("tavily", decision.search_providers)
        self.assertIn("duckduckgo", decision.search_providers)


if __name__ == "__main__":
    unittest.main()
