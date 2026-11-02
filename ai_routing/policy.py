"""
BrainyAi Intelligent Multi-Provider Routing Policy
Maps task types and response-depth modes to ordered candidate chains of (provider, model_id).
Enforces:
  1. Gemini-first high-intelligence routing for PDF Study Studio with zero-cost failover.
  2. Strict Zero-Budget model eligibility filtering (zero-price and free-tier models only).
  3. Modality validation (multimodal models for images/diagrams).
  4. Specialist model assignment (Math, Science, Coding, Web Research).
  5. Hybrid multi-factor scoring (Task suitability, latency, reliability, quality, quota).
"""

from typing import List, Tuple, Dict, Any, Optional
from ai_routing.tasks import TaskType, ResponseDepth, TaskComplexity
from ai_routing.registry import registry, CostCategory
from ai_routing.gemini_selection import select_gemini_model

Candidate = Tuple[str, str]  # (provider_name, model_id)

PDF_STUDY_TASKS = {
    TaskType.DOCUMENT_INGESTION,
    TaskType.PDF_SUMMARY,
    TaskType.PDF_QUESTION_ANSWERING,
    TaskType.NOTE_GENERATION,
    TaskType.QUIZ_GENERATION,
    TaskType.FLASHCARD_GENERATION,
    TaskType.IMPORTANT_QUESTION_GENERATION,
    TaskType.LONG_DOC_SYNTHESIS,
    TaskType.MCQ_GENERATION,
}

CODING_TASKS = {
    TaskType.CODING,
    TaskType.CODING_DEBUGGING,
    TaskType.CODING_EXPLANATION,
    TaskType.DSA,
    TaskType.SQL,
    TaskType.COMPLEX_DEBUGGING,
    TaskType.CODE_ARCHITECTURE,
}

MATH_TASKS = {
    TaskType.MATHEMATICS,
    TaskType.ADVANCED_MATHEMATICS,
    TaskType.ALGEBRA,
    TaskType.CALCULUS,
    TaskType.STATISTICS,
    TaskType.MATH_AND_LOGIC,
    TaskType.COMPLEX_MATH,
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
    TaskType.PDF_IMAGE,
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
    complexity: Optional[TaskComplexity] = None,
    document_context: Optional[Dict[str, Any]] = None,
    estimated_input_tokens: int = 0,
) -> List[Candidate]:
    """
    Returns one selected Gemini model followed by provider-level backups.
    Gemini model changes happen only inside the Gemini adapter after a
    model-specific failure; this list never fans an ordinary request across models.
    """
    return _get_provider_failover_candidates(task, depth, complexity, document_context, estimated_input_tokens)


def _get_provider_failover_candidates(
    task: TaskType,
    depth: ResponseDepth = ResponseDepth.BALANCED,
    complexity: Optional[TaskComplexity] = None,
    document_context: Optional[Dict[str, Any]] = None,
    estimated_input_tokens: int = 0,
) -> List[Candidate]:
    """Select one Gemini model first, then apply provider-level Groq/OpenRouter failover."""
    try:
        selection = select_gemini_model(task, depth, complexity, document_context, estimated_input_tokens)
        gemini = ("gemini", selection.model_id)
    except RuntimeError:
        gemini = None

    groq_fast = registry.groq_fast_model
    groq_balanced = registry.groq_balanced_model
    openrouter_free = registry.openrouter_free_model

    candidates: List[Candidate] = []
    if gemini:
        candidates.append(gemini)
    context = document_context or {}
    multimodal_parts = context.get("multimodal_parts") or []
    image_input = bool(context.get("has_image")) or task in MULTIMODAL_TASKS or any(
        "image" in str(part.get("mime_type", part.get("mimeType", ""))).lower()
        for part in multimodal_parts if isinstance(part, dict)
    )
    binary_pdf_input = any(
        "application/pdf" in str(part.get("mime_type", part.get("mimeType", ""))).lower()
        for part in multimodal_parts if isinstance(part, dict)
    ) and not context.get("pdf_text")
    if image_input:
        # Groq's configured models are text-only. Preserve modality by allowing only
        # a registered image model as the provider backup.
        candidates.append(("openrouter", "nvidia/nemotron-3.5-super-vl:free"))
        return _filter_eligible(candidates, require_vision=True)
    if binary_pdf_input:
        # Do not send raw PDF bytes to providers without verified PDF input support.
        return _filter_eligible(candidates)
    if task == TaskType.QUICK_CHAT or complexity in (TaskComplexity.FAST, TaskComplexity.LIGHT):
        candidates.append(("groq", groq_fast))
    else:
        candidates.append(("groq", groq_balanced))
    candidates.append(("openrouter", openrouter_free))
    return _filter_eligible(candidates)


def _filter_eligible(
    candidates: List[Candidate],
    disallow_gemini: bool = False,
    require_vision: bool = False
) -> List[Candidate]:
    """
    Filters candidates by:
      1. Hard privacy constraint: completely strips Gemini if disallow_gemini is True.
      2. Vision requirement: if require_vision is True, excludes any model without verified vision capabilities.
      3. Provider enablement switches.
      4. Zero-budget pricing & availability eligibility.
      5. Preserves order and deduplicates.
    """
    eligible: List[Candidate] = []
    seen = set()

    for prov, model in candidates:
        if disallow_gemini and prov.lower() == "gemini":
            continue
        if (prov, model) in seen:
            continue

        spec = registry.get_model_spec(model)
        if require_vision:
            if not spec or not spec.supports_vision:
                continue

        # Check provider availability & zero-budget eligibility
        if registry.is_model_eligible(prov, model):
            eligible.append((prov, model))
            seen.add((prov, model))

    if eligible:
        return eligible

    # Keep the static policy visible during a cold start with no configured
    # credentials. When credentials exist, honor disabled/denied model policy.
    any_provider_configured = any(registry.is_provider_available(prov) for prov, _ in candidates)
    if any_provider_configured:
        return []

    fallback: List[Candidate] = []
    for prov, model in candidates:
        if disallow_gemini and prov.lower() == "gemini":
            continue
        spec = registry.get_model_spec(model)
        if require_vision:
            if not spec or not spec.supports_vision:
                continue
        if (prov, model) not in seen:
            fallback.append((prov, model))
            seen.add((prov, model))
    return fallback
