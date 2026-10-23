"""
BrainyAi Dynamic Routing Policy
Maps task types and response-depth modes to ordered candidate chains of (provider, model_id).
"""

from typing import List, Tuple
from ai_routing.tasks import TaskType, ResponseDepth
from ai_routing.registry import registry

Candidate = Tuple[str, str]  # (provider_name, model_id)

def get_routing_candidates(task: TaskType, depth: ResponseDepth = ResponseDepth.BALANCED) -> List[Candidate]:
    """
    Returns an ordered list of (provider, model_id) candidates according to the
    architectural routing policy, task classification, and response depth.
    """
    groq_fast = registry.groq_fast_model
    groq_balanced = registry.groq_balanced_model
    gemini_reason = registry.gemini_reasoning_model
    gemini_pdf = registry.gemini_pdf_model
    samba_reason = registry.sambanova_reasoning_model
    samba_fast = registry.sambanova_fast_model
    openrouter_code = registry.openrouter_coding_model
    openrouter_free = registry.openrouter_free_model

    # ── A. Quick responses & Titles ──
    if task in (TaskType.QUICK_CHAT, TaskType.CHAT_TITLE_GENERATION) or depth == ResponseDepth.FAST:
        candidates = [
            ("groq", groq_fast),
            ("sambanova", samba_fast),
            ("cerebras", "llama3.1-8b"),
            ("gemini", "gemini-2.5-flash-lite"),
            ("openrouter", openrouter_free)
        ]
        return _filter_available(candidates)

    # ── B. Balanced everyday chat ──
    if task == TaskType.SIMPLE_EXPLANATION:
        candidates = [
            ("groq", groq_balanced),
            ("gemini", gemini_reason),
            ("sambanova", samba_reason),
            ("cerebras", "gpt-oss-120b"),
            ("openrouter", openrouter_free)
        ]
        return _filter_available(candidates)

    # ── C. Detailed explanations & Deep reasoning ──
    if task in (TaskType.DETAILED_EXPLANATION, TaskType.DEEP_REASONING, TaskType.MATH_AND_LOGIC) or depth == ResponseDepth.DEEP:
        candidates = [
            ("gemini", gemini_reason),
            ("sambanova", samba_reason),
            ("groq", groq_balanced),
            ("cerebras", "gpt-oss-120b"),
            ("openrouter", openrouter_free)
        ]
        return _filter_available(candidates)

    # ── D. Coding and technical reasoning ──
    if task == TaskType.CODING:
        candidates = [
            ("openrouter", openrouter_code),
            ("sambanova", samba_reason),
            ("groq", groq_balanced),
            ("gemini", gemini_reason),
            ("cerebras", "gpt-oss-120b")
        ]
        return _filter_available(candidates)

    # ── E. PDF and document tasks ──
    if task in (
        TaskType.DOCUMENT_INGESTION,
        TaskType.PDF_SUMMARY,
        TaskType.PDF_QUESTION_ANSWERING,
        TaskType.NOTE_GENERATION,
        TaskType.QUIZ_GENERATION,
        TaskType.FLASHCARD_GENERATION
    ):
        candidates = [
            ("gemini", gemini_pdf),
            ("sambanova", samba_reason),
            ("groq", groq_balanced),
            ("openrouter", openrouter_free)
        ]
        return _filter_available(candidates)

    # ── F. Web research generation ──
    if task == TaskType.WEB_RESEARCH:
        candidates = [
            ("gemini", gemini_reason),
            ("groq", groq_balanced),
            ("sambanova", samba_reason),
            ("openrouter", openrouter_free)
        ]
        return _filter_available(candidates)

    # Default fallback
    candidates = [
        ("groq", groq_balanced),
        ("gemini", gemini_reason),
        ("sambanova", samba_reason),
        ("openrouter", openrouter_free)
    ]
    return _filter_available(candidates)

def _filter_available(candidates: List[Candidate]) -> List[Candidate]:
    """Filters candidate list to only providers with configured keys, preserving order."""
    available = []
    seen = set()
    for prov, model in candidates:
        if registry.is_provider_available(prov) and (prov, model) not in seen:
            available.append((prov, model))
            seen.add((prov, model))
    # If no keys were configured in environment (e.g. testing or cold boot), return candidate chain anyway
    return available if available else candidates
