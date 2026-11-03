"""
Groq AI Provider Adapter with key-pooling, model fallbacks, and real-time streaming.
"""

import time
import logging
from typing import List, Dict, Any, Optional, Iterator
from groq import Groq
from ai_routing.providers.base import BaseProvider, ProviderResult, is_rate_limit, is_auth_error, is_model_not_found, is_model_context_or_limit_error
from ai_routing.registry import registry

logger = logging.getLogger("groq_provider")


def _prune_messages_for_groq(
    messages: List[Dict[str, Any]],
    system_prompt: str,
    max_chars: int = 18000,
    multimodal_parts: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Groq free tier models enforce a strict 7,000 ITPM (Input Tokens Per Minute) ceiling.
    Keep system prompt + latest turns strictly under max_chars (~4,500 tokens) to prevent HTTP 413.
    Always preserves the most recent user turn in its entirety and formats OpenAI-compatible
    multimodal image_url blocks when multimodal parts are provided.
    """
    sys_len = len(system_prompt or "")
    budget = max(4000, max_chars - sys_len)
    
    if not messages:
        if multimodal_parts:
            parts: List[Dict[str, Any]] = []
            for p in multimodal_parts:
                if isinstance(p, dict):
                    blob = p.get("inline_data") or p.get("inlineData") or {}
                    mime = blob.get("mime_type") or blob.get("mimeType") or "image/jpeg"
                    data = blob.get("data") or ""
                    if data:
                        parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}})
            if parts:
                return [{"role": "user", "content": parts}]
        return []
    
    # Process from newest to oldest
    selected = []
    used_chars = 0
    last_user_processed = False
    for m in reversed(messages):
        c = m.get("content")
        c_len = len(c) if isinstance(c, str) else 200
        if not selected:
            # Most recent turn
            if m.get("role") == "user" and multimodal_parts:
                last_user_processed = True
                parts: List[Dict[str, Any]] = []
                text_part = c if isinstance(c, str) else ""
                if text_part:
                    if len(text_part) > budget:
                        text_part = text_part[-budget:]
                    parts.append({"type": "text", "text": text_part})
                for p in multimodal_parts:
                    if isinstance(p, dict):
                        blob = p.get("inline_data") or p.get("inlineData") or {}
                        mime = blob.get("mime_type") or blob.get("mimeType") or "image/jpeg"
                        data = blob.get("data") or ""
                        if data:
                            parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}})
                selected.append({**m, "content": parts if parts else text_part})
                used_chars += len(text_part)
            elif c_len > budget and isinstance(c, str):
                c = c[-budget:]
                selected.append({**m, "content": c})
                used_chars += len(c)
            else:
                selected.append(m)
                used_chars += c_len
        elif used_chars + c_len <= budget:
            selected.append(m)
            used_chars += c_len
        else:
            break
            
    selected.reverse()
    return selected

class GroqProvider(BaseProvider):
    def __init__(self):
        super().__init__()
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
        model_chain = [primary_model, registry.groq_balanced_model, "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
        # If multimodal parts are provided, strictly filter to models with verified vision support
        if multimodal_parts:
            model_chain = [
                m for m in model_chain
                if registry.get_model_spec(m) and registry.get_model_spec(m).supports_vision
            ]
            if not model_chain:
                model_chain = ["qwen/qwen3.8-27b"]

        # Filter eligible active models
        model_chain = [m for m in dict.fromkeys(model_chain) if registry.is_model_eligible("groq", m)]
        if not model_chain and not multimodal_parts:
            model_chain = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]

        last_exc = None
        start_t = time.perf_counter()

        for _ in range(rot.key_count):
            key = rot.get_key()
            client = self._get_client(key)

            for model in model_chain:
                try:
                    pruned = _prune_messages_for_groq(messages, system_prompt, multimodal_parts=multimodal_parts)
                    kwargs: Dict[str, Any] = {
                        "model": model,
                        "messages": [{"role": "system", "content": system_prompt}] + pruned,
                        "max_tokens": max_tokens or 4096,
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
                        logger.warning("Groq model %s returned 404 Not Found; quarantining in registry", model)
                        registry.mark_model_unavailable(model, reason="404_not_found")
                        continue
                    if is_model_context_or_limit_error(e):
                        logger.info("Groq model %s context/limit error (%s), falling to next model in chain...", model, type(e).__name__)
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
        self.last_stream_finish_reason = None
        self.last_stream_model = None
        rot = registry.get_rotator("groq")
        if not rot or rot.key_count == 0:
            raise RuntimeError("NO_KEYS: groq")

        primary_model = model_id or registry.groq_fast_model
        model_chain = [primary_model, registry.groq_balanced_model, "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
        # If multimodal parts are provided, strictly filter to models with verified vision support
        if multimodal_parts:
            model_chain = [
                m for m in model_chain
                if registry.get_model_spec(m) and registry.get_model_spec(m).supports_vision
            ]
            if not model_chain:
                model_chain = ["qwen/qwen3.8-27b"]

        model_chain = [m for m in dict.fromkeys(model_chain) if registry.is_model_eligible("groq", m)]
        if not model_chain and not multimodal_parts:
            model_chain = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]

        last_exc = None
        for _ in range(rot.key_count):
            key = rot.get_key()
            client = self._get_client(key)

            for model in model_chain:
                try:
                    pruned = _prune_messages_for_groq(messages, system_prompt, multimodal_parts=multimodal_parts)
                    kwargs: Dict[str, Any] = {
                        "model": model,
                        "messages": [{"role": "system", "content": system_prompt}] + pruned,
                        "max_tokens": max_tokens or 4096,
                        "stream": True
                    }
                    if any(term in model.lower() for term in ("r1", "reasoning", "deepseek")):
                        kwargs["reasoning_effort"] = "low"

                    stream_resp = client.chat.completions.create(**kwargs)
                    self.last_stream_model = model
                    for chunk in stream_resp:
                        if chunk.choices and len(chunk.choices) > 0:
                            c0 = chunk.choices[0]
                            fr = getattr(c0, "finish_reason", None)
                            if fr:
                                self.last_stream_finish_reason = fr
                            delta = c0.delta
                            if delta and delta.content:
                                yield delta.content
                    return
                except Exception as e:
                    last_exc = e
                    if is_model_not_found(e):
                        logger.warning("Groq stream model %s returned 404 Not Found; quarantining in registry", model)
                        registry.mark_model_unavailable(model, reason="404_not_found")
                        continue
                    if is_model_context_or_limit_error(e):
                        logger.info("Groq stream model %s context/limit error (%s), falling to next model in chain...", model, type(e).__name__)
                        continue
                    logger.warning("Groq stream key failure (%s), rotating...", type(e).__name__)
                    break

        raise RuntimeError(f"All Groq streaming keys failed: {last_exc}")
