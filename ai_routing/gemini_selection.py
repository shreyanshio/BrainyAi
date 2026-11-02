"""Task based Gemini model selection, kept independent from provider failover."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ai_routing.registry import registry
from ai_routing.tasks import ResponseDepth, TaskComplexity, TaskType


@dataclass(frozen=True)
class GeminiModelSelection:
    model_id: str
    category: str
    reason: str
    priority: int


def select_gemini_model(
    task: TaskType,
    depth: ResponseDepth = ResponseDepth.BALANCED,
    complexity: Optional[TaskComplexity] = None,
    document_context: Optional[Dict[str, Any]] = None,
    estimated_input_tokens: int = 0,
) -> GeminiModelSelection:
    """Choose one documentation-verified, eligible Gemini model for this request."""
    context = document_context or {}
    is_image = bool(context.get("has_image") or context.get("multimodal_parts")) or task in {
        TaskType.IMAGE_QUESTION, TaskType.DIAGRAM_ANALYSIS, TaskType.PDF_IMAGE
    }
    is_pdf = task in {
        TaskType.DOCUMENT_INGESTION, TaskType.PDF_SUMMARY,
        TaskType.PDF_QUESTION_ANSWERING, TaskType.NOTE_GENERATION,
        TaskType.QUIZ_GENERATION, TaskType.FLASHCARD_GENERATION,
        TaskType.IMPORTANT_QUESTION_GENERATION, TaskType.LONG_DOC_SYNTHESIS,
        TaskType.MCQ_GENERATION,
    }
    comp = complexity or TaskComplexity.STANDARD
    if estimated_input_tokens > 900_000:
        desired = ["gemini-4-argon", "gemini-3.1-pro-preview", "gemini-3.8-flash"]
        category, reason = "high_context", "input context requires a verified million-token context model"
    elif (comp == TaskComplexity.DEEP or depth == ResponseDepth.DEEP or task in {
        TaskType.DEEP_REASONING, TaskType.UNCERTAIN_COMPLEX, TaskType.ADVANCED_MATHEMATICS,
        TaskType.COMPLEX_MATH,
    }) and task not in {
        TaskType.CODING, TaskType.CODING_DEBUGGING, TaskType.CODING_EXPLANATION,
        TaskType.DSA, TaskType.SQL, TaskType.COMPLEX_DEBUGGING, TaskType.CODE_ARCHITECTURE,
    }:
        desired = [registry.gemini_flagship_model, registry.gemini_reasoning_model, registry.gemini_primary_model,
                   "gemini-3.1-pro-preview", "gemini-2.5-pro"]
        category, reason = "advanced_reasoning", "deep reasoning or architecture task"
    elif is_image:
        desired = [registry.gemini_vision_model, registry.gemini_primary_model, "gemini-3.6-flash", "gemini-2.5-flash"]
        category, reason = "multimodal", "image or diagram input requires a verified multimodal model"
    elif is_pdf:
        desired = [registry.gemini_pdf_model, registry.gemini_primary_model, "gemini-2.5-flash"]
        category, reason = "document", "ordinary document analysis uses the configured Flash model"
    elif comp in (TaskComplexity.FAST, TaskComplexity.LIGHT) or depth == ResponseDepth.FAST:
        desired = [registry.gemini_fast_model, "gemini-3.5-flash-lite", "gemini-2.5-flash-lite", registry.gemini_primary_model]
        category, reason = "lightweight", "short or latency-sensitive task"
    elif task in {
        TaskType.CODING, TaskType.CODING_DEBUGGING, TaskType.CODING_EXPLANATION,
        TaskType.DSA, TaskType.SQL, TaskType.COMPLEX_DEBUGGING, TaskType.CODE_ARCHITECTURE,
        TaskType.MATHEMATICS, TaskType.ADVANCED_MATHEMATICS, TaskType.COMPLEX_MATH,
    }:
        desired = [registry.gemini_code_model if task in {
            TaskType.CODING, TaskType.CODING_DEBUGGING, TaskType.CODING_EXPLANATION,
            TaskType.DSA, TaskType.SQL, TaskType.COMPLEX_DEBUGGING, TaskType.CODE_ARCHITECTURE,
        } else registry.gemini_reasoning_model, "gemini-3.1-pro-preview", "gemini-2.5-pro", registry.gemini_primary_model]
        category, reason = ("coding", "coding task") if task in {
            TaskType.CODING, TaskType.CODING_DEBUGGING, TaskType.CODING_EXPLANATION,
            TaskType.DSA, TaskType.SQL, TaskType.COMPLEX_DEBUGGING, TaskType.CODE_ARCHITECTURE,
        } else ("mathematics", "mathematical task")
    else:
        desired = [registry.gemini_primary_model, "gemini-3.6-flash", "gemini-2.5-flash"]
        category, reason = "conversation", "standard conversation and study assistance"

    modalities = {"image"} if is_image else {"text"}
    unique_ids = list(dict.fromkeys(model_id for model_id in desired if model_id))
    for model_id in unique_ids:
        spec = registry.get_model_spec(model_id)
        if not spec or spec.provider != "gemini" or not spec.documentation_verified:
            continue
        if spec.availability_status in {"unavailable", "access_denied", "quarantined", "disabled"}:
            continue
        if not modalities.issubset(set(spec.supported_input_modalities)):
            continue
        if estimated_input_tokens and estimated_input_tokens > spec.max_context_tokens:
            continue
        if not registry.is_model_policy_eligible("gemini", model_id):
            continue
        return GeminiModelSelection(
            model_id=model_id,
            category=category,
            reason=f"{reason}; selected {spec.lifecycle} Gemini model within configured budget and capability policy",
            priority=spec.configuration_priority,
        )
    raise RuntimeError("No eligible, documentation-verified Gemini model is configured for this request")
