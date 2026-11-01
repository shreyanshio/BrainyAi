"""
Base abstractions and standardized result objects for all AI providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Iterator

@dataclass
class ProviderResult:
    text: str
    model: str
    provider: str
    finish_reason: str = "stop"
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_ms: float = 0.0
    tokens_out: Optional[int] = None
    tokens_in: Optional[int] = None

    def __post_init__(self):
        if self.tokens_out is not None and self.output_tokens is None:
            self.output_tokens = self.tokens_out
        elif self.output_tokens is not None and self.tokens_out is None:
            self.tokens_out = self.output_tokens
        if self.tokens_in is not None and self.input_tokens is None:
            self.input_tokens = self.tokens_in
        elif self.input_tokens is not None and self.tokens_in is None:
            self.tokens_in = self.input_tokens

def is_rate_limit(exc: Exception) -> bool:
    s = str(exc).lower()
    return any(w in s for w in [
        "rate limit", "quota", "exceeded", "429", "402", "too many",
        "resource_exhausted", "tokens per minute", "requests per minute",
        "tpm", "rpm", "throttled", "overloaded"
    ])

def is_auth_error(exc: Exception) -> bool:
    s = str(exc).lower()
    return any(w in s for w in [
        "401", "403", "unauthorized", "forbidden", "invalid_api_key",
        "api key not valid", "invalid api key", "credit", "balance", "insufficient"
    ])

def is_model_not_found(exc: Exception) -> bool:
    s = str(exc).lower()
    return any(w in s for w in [
        "404", "410", "gone", "model_not_found", "model not found", "does not exist", "no endpoints found"
    ])

def is_model_context_or_limit_error(exc: Exception) -> bool:
    """True if error is specific to this model's context or rate limit rather than the API key."""
    s = str(exc).lower()
    return any(w in s for w in [
        "413", "request too large", "payload too large", "context_length_exceeded",
        "maximum context length", "itpm", "input tokens per minute", "tokens per minute (itpm)"
    ]) or is_model_not_found(exc)

class BaseProvider(ABC):
    def __init__(self):
        self.last_stream_finish_reason: Optional[str] = None

    def is_available(self) -> bool:
        return True

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        max_tokens: int,
        model_id: Optional[str] = None,
        json_output: bool = False,
        multimodal_parts: Optional[List[Dict[str, Any]]] = None
    ) -> ProviderResult:
        pass

    @abstractmethod
    def stream(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        max_tokens: int,
        model_id: Optional[str] = None,
        multimodal_parts: Optional[List[Dict[str, Any]]] = None
    ) -> Iterator[str]:
        pass
