"""
BrainyAi Centralized Model-Aware Output-Budget Manager
Dynamically computes optimal token allowances per request based on verified model capabilities,
provider hardware constraints, task complexity, response depth, and available context headroom.
Eliminates arbitrary response caps while preventing context overflow and runaway costs.
"""

from typing import Optional
from ai_routing.tasks import TaskType, ResponseDepth
from ai_routing.registry import registry, ModelSpec

# Hardware & Provider Per-Call Upper Bounds
PROVIDER_MAX_OUTPUT_LIMITS = {
    "gemini": 8192,
    "groq": 8192,
    "sambanova": 4096,
    "openrouter": 8192,
    "cerebras": 2048,  # Hardware limit per single invocation; extended via seamless continuation
}

# Task-Specific Minimum Token Allowances (ensures complex requests never get choked)
TASK_MIN_BUDGETS = {
    TaskType.CODING: 4096,
    TaskType.DETAILED_EXPLANATION: 4096,
    TaskType.DEEP_REASONING: 4096,
    TaskType.MATH_AND_LOGIC: 4096,
    TaskType.PDF_SUMMARY: 4096,
    TaskType.PDF_QUESTION_ANSWERING: 3072,
    TaskType.NOTE_GENERATION: 4096,
    TaskType.QUIZ_GENERATION: 3072,
    TaskType.FLASHCARD_GENERATION: 3072,
    TaskType.WEB_RESEARCH: 3072,
    TaskType.SIMPLE_EXPLANATION: 2048,
    TaskType.QUICK_CHAT: 1536,
    TaskType.CHAT_TITLE_GENERATION: 256,
}


class OutputBudgetManager:
    @staticmethod
    def resolve_budget(
        task: TaskType,
        depth: ResponseDepth,
        provider_name: str,
        model_id: str,
        requested_max_tokens: Optional[int] = None,
        estimated_input_tokens: int = 0
    ) -> int:
        provider = (provider_name or "").lower().strip()
        spec: Optional[ModelSpec] = registry.get_model_spec(model_id)

        # 1. Determine provider physical limit per invocation
        prov_limit = PROVIDER_MAX_OUTPUT_LIMITS.get(provider, 4096)
        if spec and spec.max_output_tokens:
            prov_limit = min(prov_limit, spec.max_output_tokens)

        # Special hardware constraint for Cerebras
        if provider == "cerebras":
            prov_limit = min(prov_limit, 2048)

        # 2. Check if a specific budget was explicitly requested (e.g. from tests or specialized tools)
        if requested_max_tokens is not None and requested_max_tokens > 0:
            return min(requested_max_tokens, prov_limit)

        # 3. Base budget by Task Type
        task_base = TASK_MIN_BUDGETS.get(task, 2048)

        # 4. Depth multiplier
        if depth == ResponseDepth.DEEP:
            depth_budget = prov_limit  # Maximize model capacity for deep academic reasoning
        elif depth == ResponseDepth.FAST:
            depth_budget = min(task_base, 2048)
        else:  # BALANCED
            depth_budget = min(max(task_base, 3072), prov_limit)

        chosen_budget = max(task_base, depth_budget)
        chosen_budget = min(chosen_budget, prov_limit)

        # 5. Context window accounting (prevent exceeding total context)
        max_context = spec.max_context_tokens if spec and spec.max_context_tokens else 32768
        if estimated_input_tokens > 0:
            headroom = max_context - estimated_input_tokens - 256
            if headroom > 512:
                chosen_budget = min(chosen_budget, headroom)

        return max(512, chosen_budget)
