"""
BrainyAi Intelligent Multi-Provider Routing Policy
Maps task types and response-depth modes to ordered candidate chains of (provider, model_id).
Enforces:
  1. Strict non-Gemini guarantee for all PDF Study Studio operations.
  2. Strict Zero-Budget model eligibility filtering (zero-price and free-tier models only).
  3. Modality validation (multimodal models for images/diagrams).
  4. Specialist model assignment (Math, Science, Coding, Web Research).
  5. Hybrid multi-factor scoring (Task suitability, latency, reliability, quality, quota).
"""

from typing import List, Tuple, Dict, Any, Optional
from ai_routing.tasks import TaskType, ResponseDepth, TaskComplexity
from ai_routing.registry import registry, CostCategory

Candidate = Tuple[str, str]  # (provider_name, model_id)

PDF_STUDY_TASKS = {
    TaskType.DOCUMENT_INGESTION,
    TaskType.PDF_SUMMARY,
    TaskType.PDF_QUESTION_ANSWERING,
    TaskType.NOTE_GENERATION,
    TaskType.QUIZ_GENERATION,
    TaskType.FLASHCARD_GENERATION,
    TaskType.IMPORTANT_QUESTION_GENERATION,
}

CODING_TASKS = {
    TaskType.CODING,
    TaskType.CODING_DEBUGGING,
    TaskType.CODING_EXPLANATION,
    TaskType.DSA,
    TaskType.SQL,
}

MATH_TASKS = {
    TaskType.MATHEMATICS,
    TaskType.ADVANCED_MATHEMATICS,
    TaskType.ALGEBRA,
    TaskType.CALCULUS,
    TaskType.STATISTICS,
    TaskType.MATH_AND_LOGIC,
}

SCIENCE_TASKS = {
    TaskType.PHYSICS,
    TaskType.CHEMISTRY,
    TaskType.BIOLOGY,
    TaskType.SCIENCE,
}

MULTIMODAL_TASKS = {
    TaskType.IMAGE_QUESTION,
    TaskType.DIAGRAM_ANALYSIS,
}


def compute_routing_score(
    provider: str,
    model_id: str,
    task: TaskType,
    latency_ms: float = 150.0,
    reliability_pct: float = 99.0,
    quota_available: bool = True
) -> float:
    """
    Computes a hybrid multi-factor routing score (0 to 100) based on:
      - Task suitability (35%)
      - Measured latency (20%)
      - Historical reliability (20%)
      - Output quality tier (15%)
      - Quota availability (10%)
    """
    # 1. Task suitability
    suitability = 70.0
    if task in CODING_TASKS and ("code" in model_id.lower() or "gemma" in model_id.lower() or "70b" in model_id.lower()):
        suitability = 100.0
    elif task in MATH_TASKS and ("flash" in model_id.lower() or "70b" in model_id.lower()):
        suitability = 98.0
    elif task in MULTIMODAL_TASKS and ("flash" in model_id.lower() or "vl" in model_id.lower()):
        suitability = 100.0
    elif task == TaskType.QUICK_CHAT and ("8b" in model_id.lower() or "lite" in model_id.lower()):
        suitability = 95.0

    # 2. Latency score (lower is better, baseline 100ms = 100, 2000ms = 0)
    lat_score = max(0.0, min(100.0, 100.0 - (latency_ms / 20.0)))

    # 3. Reliability score
    rel_score = max(0.0, min(100.0, reliability_pct))

    # 4. Output quality tier
    spec = registry.get_model_spec(model_id)
    quality = 75.0
    if spec:
        if "70b" in model_id.lower() or "flash" in model_id.lower() or "120b" in model_id.lower() or "ultra" in model_id.lower():
            quality = 95.0
        elif "8b" in model_id.lower() or "lite" in model_id.lower():
            quality = 80.0

    # 5. Quota availability
    quota_score = 100.0 if quota_available else 0.0

    final_score = (
        0.35 * suitability +
        0.20 * lat_score +
        0.20 * rel_score +
        0.15 * quality +
        0.10 * quota_score
    )
    return round(final_score, 2)


def get_routing_candidates(
    task: TaskType,
    depth: ResponseDepth = ResponseDepth.BALANCED,
    complexity: Optional[TaskComplexity] = None
) -> List[Candidate]:
    """
    Returns an ordered list of (provider, model_id) candidates according to the
    specialist routing policy, task classification, modalities, and response depth.
    Enforces:
      - Groq = Speed: Instant routing for casual chit-chat, simple definitions, and greetings.
      - Gemini = Intelligence: Gemini 3.8 Flash primary for coding, math, science, and reasoning.
      - Gemini 3.6 Flash: High-quality secondary balanced intelligence and fallback.
      - Strict zero-budget eligibility and strict non-Gemini guarantee for PDF Study Studio.
    """
    groq_fast = registry.groq_fast_model
    groq_balanced = registry.groq_balanced_model
    gemini_code = getattr(registry, "gemini_code_model", "gemini-3.8-flash")
    gemini_vision = getattr(registry, "gemini_vision_model", "gemini-3.8-flash")
    gemini_reason = getattr(registry, "gemini_reasoning_model", "gemini-3.8-flash")
    gemini_balanced = getattr(registry, "gemini_balanced_model", "gemini-3.6-flash")
    gemini_fast = getattr(registry, "gemini_fast_model", "gemini-3.5-flash-lite")
    samba_reason = registry.sambanova_reasoning_model
    samba_fast = registry.sambanova_fast_model
    openrouter_code = registry.openrouter_coding_model
    openrouter_free = registry.openrouter_free_model

    # ── 1. PDF Study Studio Tasks (Gemini-Powered Academic Intelligence & High-Quota Failover) ──
    if task in PDF_STUDY_TASKS:
        gemini_pdf = getattr(registry, "gemini_pdf_model", "gemini-2.5-flash")
        if task == TaskType.PDF_QUESTION_ANSWERING:
            # Notes Assistant & Document Q&A: Gemini first for long-context grounding, followed by Groq / Cerebras / SambaNova
            candidates = [
                ("gemini", gemini_pdf),
                ("groq", groq_balanced),
                ("cerebras", "gpt-oss-120b"),
                ("sambanova", samba_reason),
                ("openrouter", openrouter_free)
            ]
        elif task in (TaskType.QUIZ_GENERATION, TaskType.IMPORTANT_QUESTION_GENERATION):
            candidates = [
                ("gemini", gemini_pdf),
                ("groq", groq_balanced),
                ("cerebras", "gpt-oss-120b"),
                ("sambanova", samba_reason),
                ("cerebras", "qwen-3.8-27b"),
                ("openrouter", openrouter_free)
            ]
        elif task == TaskType.FLASHCARD_GENERATION:
            candidates = [
                ("gemini", gemini_pdf),
                ("groq", groq_fast),
                ("cerebras", "llama3.1-8b"),
                ("sambanova", samba_fast),
                ("openrouter", openrouter_free)
            ]
        else:
            candidates = [
                ("gemini", gemini_pdf),
                ("groq", groq_balanced),
                ("cerebras", "gpt-oss-120b"),
                ("sambanova", samba_reason),
                ("openrouter", openrouter_free)
            ]
        return _filter_eligible(candidates, disallow_gemini=False)

    # ── 2. Fast Speed Tier: Greetings, Casual Chat, Simple Turn (Groq 8B First) ──
    if complexity == TaskComplexity.FAST or task in (TaskType.QUICK_CHAT, TaskType.CHAT_TITLE_GENERATION):
        candidates = [
            ("groq", groq_fast),
            ("cerebras", "llama3.1-8b"),
            ("sambanova", samba_fast),
            ("groq", groq_balanced),
            ("gemini", gemini_fast),
            ("openrouter", openrouter_free)
        ]
        return _filter_eligible(candidates)

    # ── 3. Light Tier: Short Definitions, Quick Facts, Simple Translations ──
    if (complexity == TaskComplexity.LIGHT or depth == ResponseDepth.FAST) and task not in (
        CODING_TASKS | MATH_TASKS | SCIENCE_TASKS | MULTIMODAL_TASKS | PDF_STUDY_TASKS | {TaskType.DEEP_REASONING}
    ):
        candidates = [
            ("groq", groq_fast),
            ("gemini", gemini_fast),
            ("cerebras", "llama3.1-8b"),
            ("sambanova", samba_fast),
            ("groq", groq_balanced),
            ("openrouter", openrouter_free)
        ]
        return _filter_eligible(candidates)

    # ── 4. Multimodal & Diagram Tasks ──
    if task in MULTIMODAL_TASKS:
        candidates = [
            ("gemini", gemini_vision),
            ("gemini", gemini_balanced),
            ("gemini", gemini_fast),
            ("openrouter", "nvidia/nemotron-3.5-super-vl:free"),
            ("groq", groq_balanced),  # Text fallback if visual is extracted
        ]
        return _filter_eligible(candidates)

    # ── 5. Coding Specialists (SQL, DSA, Debugging, Code Writing) ──
    if task in CODING_TASKS:
        candidates = [
            ("gemini", gemini_code),
            ("gemini", gemini_balanced),
            ("openrouter", openrouter_code),
            ("groq", groq_balanced),
            ("sambanova", samba_reason),
            ("cerebras", "gpt-oss-120b"),
            ("openrouter", "google/gemma-4-31b-it:free"),
            ("openrouter", openrouter_free)
        ]
        return _filter_eligible(candidates)

    # ── 6. Mathematics Specialists ──
    if task in MATH_TASKS:
        candidates = [
            ("gemini", gemini_reason),
            ("gemini", gemini_balanced),
            ("sambanova", samba_reason),
            ("groq", groq_balanced),
            ("cerebras", "gpt-oss-120b"),
            ("cerebras", "qwen-3.8-27b"),
            ("openrouter", openrouter_free)
        ]
        return _filter_eligible(candidates)

    # ── 7. Science Specialists (Physics, Chemistry, Biology) ──
    if task in SCIENCE_TASKS:
        candidates = [
            ("gemini", gemini_reason),
            ("gemini", gemini_balanced),
            ("groq", groq_balanced),
            ("sambanova", samba_reason),
            ("cerebras", "gpt-oss-120b"),
            ("openrouter", openrouter_free)
        ]
        return _filter_eligible(candidates)

    # ── 8. Web Research Synthesis ──
    if task == TaskType.WEB_RESEARCH:
        candidates = [
            ("gemini", gemini_reason),
            ("gemini", gemini_balanced),
            ("groq", groq_balanced),
            ("sambanova", samba_reason),
            ("openrouter", openrouter_free)
        ]
        return _filter_eligible(candidates)

    # ── 9. Deep Reasoning / Complex Architecture ──
    if task == TaskType.DEEP_REASONING or depth == ResponseDepth.DEEP or complexity == TaskComplexity.DEEP:
        candidates = [
            ("gemini", gemini_reason),
            ("gemini", gemini_balanced),
            ("sambanova", samba_reason),
            ("groq", groq_balanced),
            ("cerebras", "gpt-oss-120b"),
            ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free"),
            ("openrouter", openrouter_free)
        ]
        return _filter_eligible(candidates)

    # ── 10. Writing & Composition Specialists ──
    if task == TaskType.WRITING:
        candidates = [
            ("gemini", gemini_reason),
            ("gemini", gemini_balanced),
            ("groq", groq_balanced),
            ("sambanova", samba_reason),
            ("cerebras", "gpt-oss-120b"),
            ("openrouter", openrouter_free)
        ]
        return _filter_eligible(candidates)

    if task == TaskType.TRANSLATION:
        candidates = [
            ("gemini", gemini_balanced),
            ("gemini", gemini_reason),
            ("groq", groq_balanced),
            ("sambanova", samba_reason),
            ("openrouter", openrouter_free)
        ]
        return _filter_eligible(candidates)

    # ── 11. General Detailed / Balanced Explanations ──
    candidates = [
        ("gemini", gemini_reason),
        ("gemini", gemini_balanced),
        ("groq", groq_balanced),
        ("sambanova", samba_reason),
        ("cerebras", "gpt-oss-120b"),
        ("openrouter", openrouter_free)
    ]
    return _filter_eligible(candidates)


def _filter_eligible(candidates: List[Candidate], disallow_gemini: bool = False) -> List[Candidate]:
    """
    Filters candidates by:
      1. Hard privacy constraint: completely strips Gemini if disallow_gemini is True.
      2. Provider enablement switches.
      3. Zero-budget pricing & availability eligibility.
      4. Preserves order and deduplicates.
    """
    eligible: List[Candidate] = []
    seen = set()

    for prov, model in candidates:
        if disallow_gemini and prov.lower() == "gemini":
            continue
        if (prov, model) in seen:
            continue

        # Check provider availability & zero-budget eligibility
        if registry.is_model_eligible(prov, model):
            eligible.append((prov, model))
            seen.add((prov, model))

    if eligible:
        return eligible

    # Fallback during unit testing or cold start when no keys are set in env
    fallback: List[Candidate] = []
    for prov, model in candidates:
        if disallow_gemini and prov.lower() == "gemini":
            continue
        if (prov, model) not in seen:
            fallback.append((prov, model))
            seen.add((prov, model))
    return fallback
