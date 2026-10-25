"""
Unit & Regression Tests for BrainyAi Prompt Engineering Overhaul,
Prompt Registry, and Multi-Platform Composer.
"""

import os
import unittest
from ai_routing.tasks import TaskType
from ai_routing.prompts import (
    Platform,
    PromptRegistry,
    prompt_registry,
    PROMPTS_DIR,
    TASK_TO_PROMPT_FILE,
    INTENT_TO_PROMPT_FILE,
    PLATFORM_DIRECTIVES,
    COMPLETENESS_DIRECTIVE,
)


class TestPromptLibraryIntegrity(unittest.TestCase):
    """Verifies that all 25 prompt files exist, are well-formed, non-empty, and load cleanly."""

    EXPECTED_PROMPT_FILES = [
        "system_prompt.txt",
        "brainy_prompt.txt",
        "coding_prompt.txt",
        "math_prompt.txt",
        "search_prompt.txt",
        "summarize_prompt.txt",
        "ask5_prompt.txt",
        "define_prompt.txt",
        "fact_prompt.txt",
        "tip_prompt.txt",
        "joke_prompt.txt",
        "banter_prompt.txt",
        "motivate_prompt.txt",
        "plan_prompt.txt",
        "roast_prompt.txt",
        "roast_command_prompt.txt",
        "translate_prompt.txt",
        "image_prompt.txt",
        "group_prompt.txt",
        "quiz_prompt.txt",
        "pdf_notes_prompt.txt",
        "pdf_qa_prompt.txt",
        "pdf_quiz_prompt.txt",
        "pdf_flashcards_prompt.txt",
        "title_prompt.txt",
    ]

    def test_all_expected_prompts_exist_and_non_empty(self):
        self.assertTrue(os.path.isdir(PROMPTS_DIR), f"Prompts directory missing: {PROMPTS_DIR}")

        for fname in self.EXPECTED_PROMPT_FILES:
            fpath = os.path.join(PROMPTS_DIR, fname)
            self.assertTrue(os.path.isfile(fpath), f"Prompt file does not exist: {fname}")
            
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                self.assertGreater(
                    len(content),
                    50,
                    f"Prompt file {fname} is suspiciously short ({len(content)} chars)"
                )

    def test_prompt_registry_cache_population(self):
        registry = PromptRegistry(PROMPTS_DIR)
        for fname in self.EXPECTED_PROMPT_FILES:
            cached = registry.get_template(fname)
            self.assertTrue(len(cached) > 0, f"Template {fname} could not be retrieved from registry cache")


class TestPromptPlatformSeparation(unittest.TestCase):
    """Verifies platform typography isolation between Web, Telegram DM, and Telegram Group."""

    def test_platform_enum_resolution(self):
        self.assertEqual(Platform.from_str("web"), Platform.WEB)
        self.assertEqual(Platform.from_str("telegram"), Platform.TELEGRAM_DM)
        self.assertEqual(Platform.from_str("tg"), Platform.TELEGRAM_DM)
        self.assertEqual(Platform.from_str("group"), Platform.TELEGRAM_GROUP)
        self.assertEqual(Platform.from_str("telegram_group"), Platform.TELEGRAM_GROUP)
        self.assertEqual(Platform.from_str(None), Platform.WEB)

    def test_web_platform_composition_has_markdown_and_latex(self):
        composed = prompt_registry.compose_prompt(
            task=TaskType.CODING,
            platform=Platform.WEB
        )
        self.assertIn("PLATFORM FORMATTING CONTRACT — WEB", composed)
        self.assertIn("KaTeX/LaTeX", composed)
        self.assertIn("GitHub-Flavored Markdown", composed)
        # Web prompt MUST NOT forbid markdown asterisks
        self.assertNotIn("NEVER use **bold**", composed)
        self.assertNotIn("NEVER use **asterisks**", composed)

    def test_telegram_platform_composition(self):
        composed_dm = prompt_registry.compose_prompt(
            task=TaskType.QUICK_CHAT,
            platform=Platform.TELEGRAM_DM
        )
        self.assertIn("PLATFORM FORMATTING CONTRACT — TELEGRAM DIRECT MESSAGE", composed_dm)
        self.assertIn("Unicode", composed_dm)

        composed_group = prompt_registry.compose_prompt(
            task=TaskType.QUICK_CHAT,
            platform=Platform.TELEGRAM_GROUP
        )
        self.assertIn("PLATFORM FORMATTING CONTRACT — TELEGRAM GROUP", composed_group)
        self.assertIn("HIGH SIGNAL & CONCISENESS", composed_group)


class TestPromptTaskMappingAndSpecialization(unittest.TestCase):
    """Verifies task routing, schemas, and specialist protocol resolution."""

    def test_coding_task_protocol(self):
        prompt = prompt_registry.get_task_prompt(TaskType.CODING, Platform.WEB)
        self.assertIn("Coding & Technical Architecture Protocol", prompt)
        self.assertIn("Big-O", prompt)
        self.assertIn("EDGE CASES", prompt)

    def test_math_task_protocol(self):
        prompt = prompt_registry.get_task_prompt(TaskType.MATH_AND_LOGIC, Platform.WEB)
        self.assertIn("Mathematical & Logical Reasoning Protocol", prompt)
        self.assertIn("GIVEN DATA", prompt)
        self.assertIn("FORMULAE", prompt)

    def test_quiz_schema_platform_divergence(self):
        # Web quiz must resolve to PDF Study Studio quiz schema
        web_quiz = prompt_registry.get_task_prompt(TaskType.QUIZ_GENERATION, Platform.WEB)
        self.assertIn("questions", web_quiz)
        self.assertIn("correct_index", web_quiz)
        self.assertIn("page_ref", web_quiz)

        # Telegram quiz must resolve to Telegram Poll API quiz schema
        tg_quiz = prompt_registry.get_task_prompt(TaskType.QUIZ_GENERATION, Platform.TELEGRAM_DM)
        self.assertIn("correct_option_id", tg_quiz)
        self.assertIn("options", tg_quiz)
        self.assertIn("HARD API CONSTRAINTS", tg_quiz)

    def test_pdf_studio_prompts(self):
        notes = prompt_registry.get_task_prompt(TaskType.NOTE_GENERATION, Platform.WEB)
        self.assertIn("Document Notes Generation Protocol", notes)
        self.assertIn("[Page X]", notes)

        qa = prompt_registry.get_task_prompt(TaskType.PDF_QUESTION_ANSWERING, Platform.WEB)
        self.assertIn("Document Question Answering Protocol", qa)
        self.assertIn("PAGE CITATIONS", qa)

        flashcards = prompt_registry.get_task_prompt(TaskType.FLASHCARD_GENERATION, Platform.WEB)
        self.assertIn("Document Flashcards Protocol", flashcards)
        self.assertIn("cards", flashcards)
        self.assertIn("front", flashcards)
        self.assertIn("back", flashcards)

    def test_intent_string_mapping(self):
        self.assertEqual(
            prompt_registry.get_task_prompt("brainy"),
            prompt_registry.get_template("brainy_prompt.txt")
        )
        self.assertEqual(
            prompt_registry.get_task_prompt("ask5"),
            prompt_registry.get_template("ask5_prompt.txt")
        )
        self.assertEqual(
            prompt_registry.get_task_prompt("roast"),
            prompt_registry.get_template("roast_command_prompt.txt")
        )
        self.assertEqual(
            prompt_registry.get_task_prompt("quiz_telegram"),
            prompt_registry.get_template("quiz_prompt.txt")
        )


class TestPromptComposerLayers(unittest.TestCase):
    """Verifies that the 5-layer prompt composer applies layers in correct order and handles overrides."""

    def test_compose_prompt_with_all_layers(self):
        composed = prompt_registry.compose_prompt(
            task=TaskType.CODING,
            platform=Platform.WEB,
            request_context="USER QUERY CONTEXT: Python 3.12 asyncio event loop.",
            model_capability_override="MODEL INSTRUCTION: Output valid Python only.",
            answer_length_override="LENGTH: Comprehensive detail.",
            include_completeness=True
        )

        # Check Layer A
        self.assertIn("Brainy", composed)
        # Check Layer B
        self.assertIn("PLATFORM FORMATTING CONTRACT — WEB", composed)
        # Check Layer C
        self.assertIn("ACTIVE TASK SPECIALIST PROTOCOL", composed)
        self.assertIn("Coding & Technical Architecture Protocol", composed)
        # Check Layer D
        self.assertIn("USER QUERY CONTEXT: Python 3.12 asyncio event loop.", composed)
        self.assertIn("MODEL INSTRUCTION: Output valid Python only.", composed)
        self.assertIn("LENGTH: Comprehensive detail.", composed)
        # Check Completeness
        self.assertIn("COMPLETENESS DIRECTIVE — ZERO TRUNCATION GUARANTEE", composed)

    def test_caller_system_prompt_override(self):
        custom_base = "You are an elite competitive programming mentor."
        composed = prompt_registry.compose_prompt(
            task=TaskType.CODING,
            platform=Platform.WEB,
            system_prompt_override=custom_base
        )
        self.assertTrue(composed.startswith(custom_base))
        self.assertIn("ACTIVE TASK SPECIALIST PROTOCOL", composed)

    def test_include_completeness_flag(self):
        with_comp = prompt_registry.compose_prompt(task=TaskType.CODING, include_completeness=True)
        self.assertIn("COMPLETENESS DIRECTIVE", with_comp)

        without_comp = prompt_registry.compose_prompt(task=TaskType.CODING, include_completeness=False)
        self.assertNotIn("COMPLETENESS DIRECTIVE", without_comp)


if __name__ == "__main__":
    unittest.main()
