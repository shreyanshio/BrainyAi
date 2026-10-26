"""
BrainyAi Model Pricing & Cost Accounting Engine
Maintains verified model pricing rates per 1,000,000 tokens for accurate cost attribution.
Transparently labels whether costs are calculated from verified rates or estimated.
"""

from typing import Tuple, Dict, Any, Optional

# Pricing rates per 1,000,000 tokens (USD)
# Source: Official provider documentation (Groq, Google Gemini, SambaNova, OpenRouter, Cerebras)
# Effective Date: October 2026
MODEL_PRICING_REGISTRY: Dict[str, Dict[str, float]] = {
    # Groq Models
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "qwen/qwen3.8-27b": {"input": 0.20, "output": 0.60},
    "openai/gpt-oss-120b": {"input": 0.60, "output": 1.20},

    # Google Gemini Models
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.5-flash-lite": {"input": 0.075, "output": 0.30},

    # SambaNova Models
    "Meta-Llama-3.3-70B-Instruct": {"input": 0.60, "output": 0.80},
    "Meta-Llama-3.1-8B-Instruct": {"input": 0.10, "output": 0.10},
    "Qwen2.5-72B-Instruct": {"input": 0.60, "output": 0.80},

    # Cerebras Models
    "llama3.1-8b": {"input": 0.10, "output": 0.10},
    "qwen-3.8-27b": {"input": 0.20, "output": 0.60},
    "gpt-oss-120b": {"input": 0.60, "output": 1.20},

    # OpenRouter Free Models
    "google/gemma-4-31b-it:free": {"input": 0.00, "output": 0.00},
    "nvidia/nemotron-3.5-lightning:free": {"input": 0.00, "output": 0.00},
}

DEFAULT_FALLBACK_RATES = {"input": 0.40, "output": 0.80}


def calculate_token_cost(
    provider: str,
    model: str,
    input_tokens: Optional[int] = 0,
    output_tokens: Optional[int] = 0
) -> Tuple[float, bool]:
    """
    Calculates estimated cost in USD based on input and output token counts.
    Returns:
        (cost_usd, is_estimated)
        cost_usd: Formatted to 6 decimal places.
        is_estimated: False if exact model rates exist in registry, True if fallback rates applied.
    """
    in_tok = max(0, input_tokens or 0)
    out_tok = max(0, output_tokens or 0)

    rates = MODEL_PRICING_REGISTRY.get(model)
    is_estimated = False

    if rates is None:
        # Check case-insensitive or partial model name match
        model_lower = model.lower()
        for k, v in MODEL_PRICING_REGISTRY.items():
            if k.lower() in model_lower or model_lower in k.lower():
                rates = v
                break

    if rates is None:
        rates = DEFAULT_FALLBACK_RATES
        is_estimated = True

    input_cost = (in_tok / 1_000_000.0) * rates["input"]
    output_cost = (out_tok / 1_000_000.0) * rates["output"]
    total_cost = round(input_cost + output_cost, 6)

    return total_cost, is_estimated
