"""
BrainyAi Central Prompt Registry & Layered Composer
Provides deterministic, multi-platform, and task-specific prompt composition
across Web, Telegram DM, and Telegram Group environments.
Enforces the 5-Layer Prompt Architecture:
  Layer A: Core Assistant Identity & Universal Behavioral Policy
  Layer B: Platform-Specific Output Directives (Web Markdown/LaTeX vs Telegram)
  Layer C: Task-Specific Expert Protocol (Coding, Math, Search, Quiz, Notes, etc.)
  Layer D: Request Context & Grounding Data
  Layer E: Runtime Model & Continuation Configuration
"""

import os
import re
import logging
from enum import Enum
from typing import Optional, Dict, Any

from ai_routing.tasks import TaskType

logger = logging.getLogger("ai_prompts")

# Resolve repository prompts directory robustly
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS_DIR = os.path.join(_BASE_DIR, "prompts")


class Platform(str, Enum):
    WEB = "web"
    TELEGRAM_DM = "telegram_dm"
    TELEGRAM_GROUP = "telegram_group"

    @classmethod
    def from_str(cls, val: Optional[str]) -> "Platform":
        if not val:
            return cls.WEB
        v = str(val).strip().lower()
        if "group" in v:
            return cls.TELEGRAM_GROUP
        if "telegram" in v or "tg" in v or "bot" in v:
            return cls.TELEGRAM_DM
        return cls.WEB


# Task Type to Prompt File Mapping
TASK_TO_PROMPT_FILE: Dict[TaskType, str] = {
    TaskType.CODING: "coding_prompt.txt",
    TaskType.MATH_AND_LOGIC: "math_prompt.txt",
    TaskType.DEEP_REASONING: "brainy_prompt.txt",
    TaskType.DETAILED_EXPLANATION: "brainy_prompt.txt",
    TaskType.SIMPLE_EXPLANATION: "summarize_prompt.txt",
    TaskType.QUICK_CHAT: "system_prompt.txt",
    TaskType.WEB_RESEARCH: "search_prompt.txt",
    TaskType.NOTE_GENERATION: "pdf_notes_prompt.txt",
    TaskType.DOCUMENT_INGESTION: "pdf_notes_prompt.txt",
    TaskType.PDF_SUMMARY: "summarize_prompt.txt",
    TaskType.PDF_QUESTION_ANSWERING: "pdf_qa_prompt.txt",
    TaskType.QUIZ_GENERATION: "pdf_quiz_prompt.txt",
    TaskType.FLASHCARD_GENERATION: "pdf_flashcards_prompt.txt",
    TaskType.CHAT_TITLE_GENERATION: "title_prompt.txt",
}

# Slash Command / Intent String to Prompt File Mapping
INTENT_TO_PROMPT_FILE: Dict[str, str] = {
    "brainy": "brainy_prompt.txt",
    "ask5": "ask5_prompt.txt",
    "define": "define_prompt.txt",
    "fact": "fact_prompt.txt",
    "joke": "joke_prompt.txt",
    "motivate": "motivate_prompt.txt",
    "plan": "plan_prompt.txt",
    "roast": "roast_command_prompt.txt",
    "roast_defense": "roast_prompt.txt",
    "search": "search_prompt.txt",
    "summarize": "summarize_prompt.txt",
    "tip": "tip_prompt.txt",
    "translate": "translate_prompt.txt",
    "banter": "banter_prompt.txt",
    "image": "image_prompt.txt",
    "group": "group_prompt.txt",
    "quiz_telegram": "quiz_prompt.txt",
    "pdf_notes": "pdf_notes_prompt.txt",
    "pdf_qa": "pdf_qa_prompt.txt",
    "pdf_quiz": "pdf_quiz_prompt.txt",
    "pdf_flashcards": "pdf_flashcards_prompt.txt",
    "coding": "coding_prompt.txt",
    "math": "math_prompt.txt",
    "title": "title_prompt.txt",
}

# Platform Directives (Layer B)
PLATFORM_DIRECTIVES = {
    Platform.WEB: (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌐 PLATFORM FORMATTING CONTRACT — WEB (RICH MARKDOWN & LATEX)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "1. MARKDOWN: Use full GitHub-Flavored Markdown. Use ## and ### for headings, **bold** for key terms, "
        "*italic* for definitions/variables, and clean bullet lists (- or *).\n"
        "2. MATHEMATICS & FORMULAS: Format ALL mathematical equations, variables, matrices, and scientific units with KaTeX/LaTeX:\n"
        "   - Use inline $...$ for equations inside sentences (e.g. $E = mc^2$, $\\lambda = 500\\text{ nm}$, $v_{\\text{rms}} = \\sqrt{3RT/M}$).\n"
        "   - Use block $$...$$ on its own line for major derivations or standalone equations.\n"
        "3. CODE BLOCKS: Wrap all code snippets in triple backticks with explicit language identifiers (e.g., ```python, ```javascript, ```typescript, ```html, ```sql).\n"
        "4. TABLES: Use standard Markdown tables (| Feature | Description |) for all structured comparisons."
    ),
    Platform.TELEGRAM_DM: (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📱 PLATFORM FORMATTING CONTRACT — TELEGRAM DIRECT MESSAGE\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "1. FORMATTING: Use clean Unicode symbols and emojis. Avoid raw markdown symbols that may break in Telegram clients.\n"
        "2. MATH SYMBOLS: Use clean Unicode characters for math (α, β, θ, π, ×, ÷, ±, √, ∞, ∫, ∑, ≤, ≥, ≠, ≈, →, ⇒).\n"
        "3. STRUCTURE: Use arrows (→), numbered steps, and emoji headers for clean, legible spacing."
    ),
    Platform.TELEGRAM_GROUP: (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👥 PLATFORM FORMATTING CONTRACT — TELEGRAM GROUP\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "1. HIGH SIGNAL & CONCISENESS: Multiple students are active. Keep responses crisp and punchy (typically under 8-10 lines for general queries).\n"
        "2. FORMATTING: Use clean Unicode formatting and emojis. No broken raw markdown symbols.\n"
        "3. DEEP STUDY NUDGE: If a problem requires a long multi-page derivation, provide the core steps and final result, and suggest continuing in direct message for the full breakdown."
    ),
}

COMPLETENESS_DIRECTIVE = (
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "🎯 COMPLETENESS DIRECTIVE — ZERO TRUNCATION GUARANTEE\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "Answer the user's complete request accurately, comprehensively, and coherently. "
    "Address every question, subtask, and step. Use sufficient detail to explain the answer properly, "
    "while avoiding unnecessary fluff. Complete all code blocks, formulas, derivations, and examples "
    "thoroughly without cutting off or omitting requested sections."
)


class PromptRegistry:
    def __init__(self, prompts_dir: str = PROMPTS_DIR):
        self.prompts_dir = prompts_dir
        self._cache: Dict[str, str] = {}
        self._load_all()

    def _load_all(self):
        if not os.path.exists(self.prompts_dir):
            logger.warning("Prompts directory not found at: %s", self.prompts_dir)
            return

        for fname in os.listdir(self.prompts_dir):
            if fname.endswith(".txt"):
                fpath = os.path.join(self.prompts_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            self._cache[fname] = content
                        else:
                            logger.warning("Prompt file %s is empty!", fname)
                except Exception as e:
                    logger.error("Failed to load prompt file %s: %s", fname, e)

    def get_template(self, filename: str) -> str:
        """Retrieves cached template or loads from disk on demand."""
        if filename in self._cache:
            return self._cache[filename]

        fpath = os.path.join(self.prompts_dir, filename)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    self._cache[filename] = content
                    return content
            except Exception as e:
                logger.error("Error reading %s: %s", fpath, e)

        logger.warning("Prompt template '%s' not found. Returning empty string.", filename)
        return ""

    def get_task_prompt(self, task: TaskType | str, platform: Platform = Platform.WEB) -> str:
        """Resolves task-specific expert protocol."""
        if isinstance(task, TaskType):
            # Special case: Telegram quiz uses Telegram Poll API schema
            if task == TaskType.QUIZ_GENERATION and platform in (Platform.TELEGRAM_DM, Platform.TELEGRAM_GROUP):
                return self.get_template("quiz_prompt.txt")
            fname = TASK_TO_PROMPT_FILE.get(task, "system_prompt.txt")
            return self.get_template(fname)

        task_str = str(task).lower().strip()
        if task_str in INTENT_TO_PROMPT_FILE:
            return self.get_template(INTENT_TO_PROMPT_FILE[task_str])

        return self.get_template("system_prompt.txt")

    def compose_prompt(
        self,
        task: Optional[TaskType | str] = None,
        platform: Platform = Platform.WEB,
        system_prompt_override: Optional[str] = None,
        request_context: Optional[str] = None,
        model_capability_override: Optional[str] = None,
        answer_length_override: Optional[str] = None,
        include_completeness: bool = True
    ) -> str:
        """
        Composes a unified, layered prompt following the deterministic priority model:
        1. Layer A: Universal Assistant Core (or caller-supplied override)
        2. Layer B: Platform-Specific Output Directives (Web Markdown/LaTeX vs Telegram)
        3. Layer C: Task-Specific Expert Protocol (Coding, Math, Search, Notes, etc.)
        4. Layer D: Request-Specific Context & Model Directives
        5. Completeness Directive
        """
        # 1. Base Core Prompt (Layer A)
        if system_prompt_override and system_prompt_override.strip():
            base_prompt = system_prompt_override.strip()
        else:
            base_prompt = self.get_template("system_prompt.txt")

        # Handle completeness directive inclusion/exclusion
        comp_block = ""
        if not include_completeness:
            # Strip completeness directive if it exists in base_prompt
            base_prompt = re.sub(
                r"\n*━+\s*🎯\s*COMPLETENESS DIRECTIVE[^\n]*\n*━+\s*Answer the user's complete request.*?omitting requested sections\.",
                "",
                base_prompt,
                flags=re.DOTALL
            ).strip()
        elif "COMPLETENESS DIRECTIVE" not in base_prompt:
            comp_block = f"\n\n{COMPLETENESS_DIRECTIVE}"

        # 2. Platform Directives (Layer B)
        plat_directive = PLATFORM_DIRECTIVES.get(platform, PLATFORM_DIRECTIVES[Platform.WEB])

        # 3. Task-Specific Protocol (Layer C)
        task_prompt = ""
        if task:
            resolved_task_prompt = self.get_task_prompt(task, platform=platform)
            # Only append if not already identical to base prompt or already included
            if resolved_task_prompt and resolved_task_prompt != base_prompt and resolved_task_prompt not in base_prompt:
                task_prompt = f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🎯 ACTIVE TASK SPECIALIST PROTOCOL\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{resolved_task_prompt}"

        # 4. Context & Model Overrides (Layer D)
        context_parts = []
        if model_capability_override:
            context_parts.append(model_capability_override.strip())
        if answer_length_override:
            context_parts.append(answer_length_override.strip())
        if request_context:
            context_parts.append(request_context.strip())

        context_block = ""
        if context_parts:
            context_block = "\n\n" + "\n\n".join(context_parts)

        # Avoid redundant platform directive injection if already in prompt
        plat_block = ""
        if "PLATFORM FORMATTING CONTRACT" not in base_prompt:
            plat_block = f"\n\n{plat_directive}"

        composed = f"{base_prompt}{plat_block}{task_prompt}{context_block}{comp_block}".strip()
        return composed


# Global prompt registry singleton
prompt_registry = PromptRegistry()
