"""
BrainyAi Intelligent Task Classification & Response Depth Control
Defines the 14 core academic and study task categories, response-depth modes,
and a fast, deterministic, zero-overhead task classifier.
"""

from enum import Enum
import re
from typing import List, Dict, Any, Optional

class TaskType(str, Enum):
    QUICK_CHAT               = "QUICK_CHAT"
    SIMPLE_EXPLANATION       = "SIMPLE_EXPLANATION"
    DETAILED_EXPLANATION     = "DETAILED_EXPLANATION"
    DEEP_REASONING           = "DEEP_REASONING"
    CODING                   = "CODING"
    MATH_AND_LOGIC           = "MATH_AND_LOGIC"
    WEB_RESEARCH             = "WEB_RESEARCH"
    DOCUMENT_INGESTION       = "DOCUMENT_INGESTION"
    PDF_SUMMARY              = "PDF_SUMMARY"
    PDF_QUESTION_ANSWERING   = "PDF_QUESTION_ANSWERING"
    NOTE_GENERATION          = "NOTE_GENERATION"
    QUIZ_GENERATION          = "QUIZ_GENERATION"
    FLASHCARD_GENERATION     = "FLASHCARD_GENERATION"
    CHAT_TITLE_GENERATION    = "CHAT_TITLE_GENERATION"

class ResponseDepth(str, Enum):
    FAST     = "FAST"
    BALANCED = "BALANCED"
    DEEP     = "DEEP"

    @classmethod
    def from_str(cls, val: Optional[str]) -> "ResponseDepth":
        if not val:
            return cls.BALANCED
        v = str(val).strip().upper()
        if v in ("FAST", "SHORT", "QUICK", "CONCISE", "BRIEF"):
            return cls.FAST
        if v in ("DEEP", "LONG", "DETAILED", "THOROUGH", "EXTENSIVE"):
            return cls.DEEP
        return cls.BALANCED

# Regex patterns for deterministic classification
_CODE_KEYWORDS = re.compile(
    r"\b(python|javascript|typescript|c\+\+|java|html|css|sql|function|def\s+|class\s+|var\s+|let\s+|const\s+|import\s+|return\s+|debug|bug|error|traceback|syntax|algorithm|regex|stack|queue|array|pointer|malloc)\b",
    re.IGNORECASE
)

_MATH_KEYWORDS = re.compile(
    r"(\b(solve|calculate|evaluate|derive|integral|derivative|calculus|algebra|matrix|matrices|vector|limit|theorem|formula|proof|equation|probability|logarithm|trigonometry|geometry)\b|[\∫\∑\∏\√\∂\±\≤\≥\≠\≈\∞\∈\∉\⊂\⊆\∪\∩])",
    re.IGNORECASE
)

_RESEARCH_KEYWORDS = re.compile(
    r"\b(search|current|latest|news|today|recent|who won|who is the current|price of|weather in|live score|lookup)\b",
    re.IGNORECASE
)

_QUIZ_KEYWORDS = re.compile(
    r"\b(quiz|mcq|multiple choice|test me|practice questions|exam questions)\b",
    re.IGNORECASE
)

_FLASHCARD_KEYWORDS = re.compile(
    r"\b(flashcard|flashcards|study cards|anki|revision cards|qa cards)\b",
    re.IGNORECASE
)

_SUMMARY_KEYWORDS = re.compile(
    r"\b(summarize|summary|tldr|takeaways|key points|recap|condense|digest)\b",
    re.IGNORECASE
)

_NOTES_KEYWORDS = re.compile(
    r"\b(study notes|revision notes|make notes|generate notes|chapter notes|cheatsheet)\b",
    re.IGNORECASE
)

_DEEP_KEYWORDS = re.compile(
    r"\b(in detail|detailed|step by step|comprehensive|deep dive|explain thoroughly|all aspects|elaborate|in depth)\b",
    re.IGNORECASE
)

_BRIEF_KEYWORDS = re.compile(
    r"\b(briefly|short answer|in short|quick definition|in 1 line|one line|concise|tldr)\b",
    re.IGNORECASE
)

def classify_task(
    prompt: Optional[str | List[Dict[str, str]]] = None,
    messages: Optional[List[Dict[str, str]]] = None,
    context: Optional[Dict[str, Any]] = None,
    explicit_task: Optional[TaskType | str] = None,
    depth: Optional[ResponseDepth | str] = None
) -> TaskType:
    if isinstance(prompt, list):
        messages = prompt
        prompt = ""
    """
    Fast, deterministic, zero-overhead task classification.
    Takes into account explicit intent, keywords, prompt length, and document context.
    Never executes a remote LLM call just to classify.
    """
    if explicit_task:
        if isinstance(explicit_task, TaskType):
            return explicit_task
        try:
            return TaskType(str(explicit_task).upper())
        except ValueError:
            pass

    ctx = context or {}
    has_pdf_context = bool(ctx.get("document_id") or ctx.get("pdf_text") or ctx.get("document_pages"))

    text = (prompt or "").strip()
    if not text and messages:
        # Use last user message
        for m in reversed(messages):
            if m.get("role") == "user":
                text = (m.get("content") or "").strip()
                break

    # 1. Document / PDF tasks
    is_doc_topic = has_pdf_context or "pdf" in text.lower() or "document" in text.lower()
    if is_doc_topic:
        if _QUIZ_KEYWORDS.search(text):
            return TaskType.QUIZ_GENERATION
        if _FLASHCARD_KEYWORDS.search(text):
            return TaskType.FLASHCARD_GENERATION
        if _NOTES_KEYWORDS.search(text):
            return TaskType.NOTE_GENERATION
        if _SUMMARY_KEYWORDS.search(text):
            return TaskType.PDF_SUMMARY
        if has_pdf_context:
            return TaskType.PDF_QUESTION_ANSWERING

    # 2. Standalone Quizzes & Flashcards
    if _QUIZ_KEYWORDS.search(text):
        return TaskType.QUIZ_GENERATION
    if _FLASHCARD_KEYWORDS.search(text):
        return TaskType.FLASHCARD_GENERATION
    if _NOTES_KEYWORDS.search(text):
        return TaskType.NOTE_GENERATION

    # 3. Web Research
    if _RESEARCH_KEYWORDS.search(text) and len(text.split()) < 25:
        return TaskType.WEB_RESEARCH

    # 4. Coding & Technical
    if _CODE_KEYWORDS.search(text) or "```" in text:
        return TaskType.CODING

    # 5. Math & Logic
    if _MATH_KEYWORDS.search(text):
        return TaskType.MATH_AND_LOGIC

    # 6. Title Generation
    if "generate title" in text.lower() or "conversation title" in text.lower():
        return TaskType.CHAT_TITLE_GENERATION

    # 7. Summary / Explanation vs Quick chat
    resolved_depth = ResponseDepth.from_str(depth) if depth else ResponseDepth.BALANCED

    if _SUMMARY_KEYWORDS.search(text):
        return TaskType.SIMPLE_EXPLANATION if resolved_depth == ResponseDepth.FAST else TaskType.DETAILED_EXPLANATION

    if _DEEP_KEYWORDS.search(text) or resolved_depth == ResponseDepth.DEEP:
        return TaskType.DEEP_REASONING

    if _BRIEF_KEYWORDS.search(text) or resolved_depth == ResponseDepth.FAST or len(text.split()) <= 4:
        return TaskType.QUICK_CHAT

    if len(text.split()) > 40:
        return TaskType.DETAILED_EXPLANATION

    return TaskType.SIMPLE_EXPLANATION
