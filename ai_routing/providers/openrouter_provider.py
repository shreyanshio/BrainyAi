"""
OpenRouter Provider Adapter (Free model catalog fallback).
"""

import json
import time
import logging
import requests
from typing import List, Dict, Any, Optional, Iterator
from ai_routing.providers.base import BaseProvider, ProviderResult, is_model_not_found
from ai_routing.registry import registry

logger = logging.getLogger("openrouter_provider")

def _format_openrouter_messages(
    messages: List[Dict[str, Any]],
    system_prompt: str,
    multimodal_parts: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    out_msgs: List[Dict[str, Any]] = []
    if system_prompt:
        out_msgs.append({"role": "system", "content": system_prompt})

    has_multimodal = bool(multimodal_parts)
    last_user_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_idx = i
            break

    for i, m in enumerate(messages):
        role = m.get("role", "user")
        text_content = m.get("content", "")
        if i == last_user_idx and has_multimodal:
            parts: List[Dict[str, Any]] = []
            if text_content:
                parts.append({"type": "text", "text": text_content})
            for part in (multimodal_parts or []):
                if isinstance(part, dict):
                    inline = part.get("inline_data") or part.get("inlineData")
                    if inline and isinstance(inline, dict):
                        mime = inline.get("mime_type") or inline.get("mimeType") or "image/jpeg"
                        data = inline.get("data") or ""
                        parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{data}"}
                        })
            if parts:
                out_msgs.append({"role": role, "content": parts})
            else:
                out_msgs.append({"role": role, "content": text_content})
        else:
            out_msgs.append({"role": role, "content": text_content})

    if not any(m.get("role") == "user" for m in out_msgs) and has_multimodal:
        parts = []
        for part in (multimodal_parts or []):
            if isinstance(part, dict):
                inline = part.get("inline_data") or part.get("inlineData")
                if inline and isinstance(inline, dict):
                    mime = inline.get("mime_type") or inline.get("mimeType") or "image/jpeg"
                    data = inline.get("data") or ""
                    parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{data}"}
                    })
        if parts:
            out_msgs.append({"role": "user", "content": parts})

    return out_msgs


class OpenRouterProvider(BaseProvider):
    def generate(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        max_tokens: int,
        model_id: Optional[str] = None,
        json_output: bool = False,
        multimodal_parts: Optional[List[Dict[str, Any]]] = None
    ) -> ProviderResult:
        rot = registry.get_rotator("openrouter")
        if not rot or rot.key_count == 0:
            raise RuntimeError("NO_KEYS: openrouter")

        if multimodal_parts:
            # Strictly use vision-capable models only
            model_chain = [
                model_id or "nvidia/nemotron-3.5-super-vl:free",
                "nvidia/nemotron-3.5-super-vl:free",
            ]
        else:
            primary_model = model_id or registry.openrouter_free_model
            model_chain = [
                primary_model,
                "google/gemma-4-31b-it:free",
                "google/gemma-4-26b-a4b-it:free",
                "liquid/lfm-2.5-2.6b:free",
                "thinkingmachines/inkling:free",
                "cohere/north-mini-code:free"
            ]
        model_chain = list(dict.fromkeys(model_chain))

        start_t = time.perf_counter()
        last_exc = None

        formatted_messages = _format_openrouter_messages(messages, system_prompt, multimodal_parts)

        for _ in range(rot.key_count):
            key = rot.get_key()
            for model in model_chain:
                try:
                    payload = {
                        "model": model,
                        "messages": formatted_messages,
                        "max_tokens": max_tokens or 4096
                    }
                    if json_output:
                        payload["response_format"] = {"type": "json_object"}

                    resp = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://brainyai.cenai.workers.dev",
                            "X-Title": "BrainyAi"
                        },
                        json=payload,
                        timeout=25
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    choice = data["choices"][0]
                    content = choice["message"]["content"] or ""
                    finish = choice.get("finish_reason", "stop")
                    latency = (time.perf_counter() - start_t) * 1000.0

                    return ProviderResult(
                        text=content,
                        model=model,
                        provider="openrouter",
                        finish_reason=finish,
                        latency_ms=latency
                    )
                except Exception as e:
                    last_exc = e
                    if is_model_not_found(e):
                        continue
                    logger.warning("OpenRouter key failure (%s), rotating...", type(e).__name__)
                    break

        raise RuntimeError(f"All OpenRouter keys/models failed: {last_exc}")

    def stream(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        max_tokens: int,
        model_id: Optional[str] = None,
        multimodal_parts: Optional[List[Dict[str, Any]]] = None
    ) -> Iterator[str]:
        self.last_stream_finish_reason = None
        rot = registry.get_rotator("openrouter")
        if not rot or rot.key_count == 0:
            raise RuntimeError("NO_KEYS: openrouter")

        if multimodal_parts:
            model_chain = [
                model_id or "nvidia/nemotron-3.5-super-vl:free",
                "nvidia/nemotron-3.5-super-vl:free",
            ]
        else:
            primary_model = model_id or registry.openrouter_free_model
            model_chain = [
                primary_model,
                "google/gemma-4-31b-it:free",
                "google/gemma-4-26b-a4b-it:free",
                "liquid/lfm-2.5-2.6b:free",
                "thinkingmachines/inkling:free",
                "cohere/north-mini-code:free"
            ]
        model_chain = list(dict.fromkeys(model_chain))

        formatted_messages = _format_openrouter_messages(messages, system_prompt, multimodal_parts)

        last_exc = None
        for _ in range(rot.key_count):
            key = rot.get_key()
            for model in model_chain:
                try:
                    payload = {
                        "model": model,
                        "messages": formatted_messages,
                        "max_tokens": max_tokens or 4096,
                        "stream": True
                    }
                    resp = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://brainyai.cenai.workers.dev",
                            "X-Title": "BrainyAi"
                        },
                        json=payload,
                        stream=True,
                        timeout=25
                    )
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if line:
                            line_str = line.decode("utf-8")
                            if line_str.startswith("data: "):
                                data_str = line_str[6:].strip()
                                if data_str == "[DONE]":
                                    break
                                try:
                                    chunk_obj = json.loads(data_str)
                                    c0 = chunk_obj["choices"][0]
                                    fr = c0.get("finish_reason")
                                    if fr:
                                        self.last_stream_finish_reason = fr
                                    delta = c0["delta"].get("content")
                                    if delta:
                                        yield delta
                                except Exception:
                                    continue
                    return
                except Exception as e:
                    last_exc = e
                    if is_model_not_found(e):
                        continue
                    logger.warning("OpenRouter stream failure (%s), rotating...", type(e).__name__)
                    break

        raise RuntimeError(f"All OpenRouter stream keys failed: {last_exc}")
