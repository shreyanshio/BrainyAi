"""
Groq AI Provider Adapter with key-pooling, model fallbacks, and real-time streaming.
"""

import time
import logging
from typing import List, Dict, Any, Optional, Iterator
from groq import Groq
from ai_routing.providers.base import BaseProvider, ProviderResult, is_rate_limit, is_auth_error, is_model_not_found
from ai_routing.registry import registry

logger = logging.getLogger("groq_provider")

class GroqProvider(BaseProvider):
    def __init__(self):
        self._client_pool: Dict[str, Groq] = {}

    def _get_client(self, api_key: str) -> Groq:
        client = self._client_pool.get(api_key)
        if client is None:
            client = Groq(api_key=api_key, timeout=25.0)
            self._client_pool[api_key] = client
        return client

    def generate(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        max_tokens: int,
        model_id: Optional[str] = None,
        json_output: bool = False,
        multimodal_parts: Optional[List[Dict[str, Any]]] = None
    ) -> ProviderResult:
        rot = registry.get_rotator("groq")
        if not rot or rot.key_count == 0:
            raise RuntimeError("NO_KEYS: groq")

        primary_model = model_id or registry.groq_fast_model
        model_chain = [primary_model, registry.groq_balanced_model, "qwen/qwen3.8-27b", "llama-3.1-8b-instant"]
        # De-duplicate
        model_chain = list(dict.fromkeys(model_chain))

        last_exc = None
        start_t = time.perf_counter()

        for _ in range(rot.key_count):
            key = rot.get_key()
            client = self._get_client(key)

            for model in model_chain:
                try:
                    kwargs: Dict[str, Any] = {
                        "model": model,
                        "messages": [{"role": "system", "content": system_prompt}] + messages,
                        "max_tokens": max_tokens or 1024,
                    }
                    if json_output:
                        kwargs["response_format"] = {"type": "json_object"}
                    if any(term in model.lower() for term in ("r1", "reasoning", "deepseek")):
                        kwargs["reasoning_effort"] = "medium"

                    resp = client.chat.completions.create(**kwargs)
                    latency = (time.perf_counter() - start_t) * 1000.0
                    content = resp.choices[0].message.content or ""
                    finish = resp.choices[0].finish_reason or "stop"
                    in_tok = getattr(resp.usage, "prompt_tokens", None) if hasattr(resp, "usage") else None
                    out_tok = getattr(resp.usage, "completion_tokens", None) if hasattr(resp, "usage") else None

                    return ProviderResult(
                        text=content,
                        model=model,
                        provider="groq",
                        finish_reason=finish,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        latency_ms=latency
                    )
                except Exception as e:
                    last_exc = e
                    if is_model_not_found(e):
                        continue
                    # Key rate-limited or auth error: switch to next key in pool
                    logger.warning("Groq key error (%s), rotating key...", type(e).__name__)
                    break

        raise RuntimeError(f"All Groq keys/models failed: {last_exc}")

    def stream(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        max_tokens: int,
        model_id: Optional[str] = None,
        multimodal_parts: Optional[List[Dict[str, Any]]] = None
    ) -> Iterator[str]:
        rot = registry.get_rotator("groq")
        if not rot or rot.key_count == 0:
            raise RuntimeError("NO_KEYS: groq")

        primary_model = model_id or registry.groq_fast_model
        model_chain = [primary_model, registry.groq_balanced_model, "qwen/qwen3.8-27b", "llama-3.1-8b-instant"]
        model_chain = list(dict.fromkeys(model_chain))

        last_exc = None
        for _ in range(rot.key_count):
            key = rot.get_key()
            client = self._get_client(key)

            for model in model_chain:
                try:
                    kwargs: Dict[str, Any] = {
                        "model": model,
                        "messages": [{"role": "system", "content": system_prompt}] + messages,
                        "max_tokens": max_tokens or 1024,
                        "stream": True
                    }
                    if any(term in model.lower() for term in ("r1", "reasoning", "deepseek")):
                        kwargs["reasoning_effort"] = "low"

                    stream_resp = client.chat.completions.create(**kwargs)
                    for chunk in stream_resp:
                        if chunk.choices and len(chunk.choices) > 0:
                            delta = chunk.choices[0].delta
                            if delta and delta.content:
                                yield delta.content
                    return
                except Exception as e:
                    last_exc = e
                    if is_model_not_found(e):
                        continue
                    logger.warning("Groq stream key failure (%s), rotating...", type(e).__name__)
                    break

        raise RuntimeError(f"All Groq streaming keys failed: {last_exc}")
