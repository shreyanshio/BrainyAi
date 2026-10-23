"""
SambaNova Cloud Provider Adapter (SN40L high-speed 70B & 72B models).
"""

import json
import time
import logging
import requests
from typing import List, Dict, Any, Optional, Iterator
from ai_routing.providers.base import BaseProvider, ProviderResult, is_model_not_found
from ai_routing.registry import registry

logger = logging.getLogger("sambanova_provider")

class SambaNovaProvider(BaseProvider):
    def generate(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        max_tokens: int,
        model_id: Optional[str] = None,
        json_output: bool = False,
        multimodal_parts: Optional[List[Dict[str, Any]]] = None
    ) -> ProviderResult:
        rot = registry.get_rotator("sambanova")
        if not rot or rot.key_count == 0:
            raise RuntimeError("NO_KEYS: sambanova")

        primary_model = model_id or registry.sambanova_reasoning_model
        model_chain = [primary_model, "Qwen2.5-72B-Instruct", registry.sambanova_fast_model]
        model_chain = list(dict.fromkeys(model_chain))

        start_t = time.perf_counter()
        last_exc = None

        for _ in range(rot.key_count):
            key = rot.get_key()
            for model in model_chain:
                try:
                    payload = {
                        "model": model,
                        "messages": [{"role": "system", "content": system_prompt}] + messages,
                        "max_tokens": max_tokens or 2048
                    }
                    if json_output:
                        payload["response_format"] = {"type": "json_object"}

                    resp = requests.post(
                        "https://api.sambanova.ai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
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
                        provider="sambanova",
                        finish_reason=finish,
                        latency_ms=latency
                    )
                except Exception as e:
                    last_exc = e
                    if is_model_not_found(e):
                        continue
                    logger.warning("SambaNova key failure (%s), rotating...", type(e).__name__)
                    break

        raise RuntimeError(f"All SambaNova keys/models failed: {last_exc}")

    def stream(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        max_tokens: int,
        model_id: Optional[str] = None,
        multimodal_parts: Optional[List[Dict[str, Any]]] = None
    ) -> Iterator[str]:
        rot = registry.get_rotator("sambanova")
        if not rot or rot.key_count == 0:
            raise RuntimeError("NO_KEYS: sambanova")

        primary_model = model_id or registry.sambanova_reasoning_model
        model_chain = [primary_model, "Qwen2.5-72B-Instruct", registry.sambanova_fast_model]
        model_chain = list(dict.fromkeys(model_chain))

        last_exc = None
        for _ in range(rot.key_count):
            key = rot.get_key()
            for model in model_chain:
                try:
                    payload = {
                        "model": model,
                        "messages": [{"role": "system", "content": system_prompt}] + messages,
                        "max_tokens": max_tokens or 1024,
                        "stream": True
                    }
                    resp = requests.post(
                        "https://api.sambanova.ai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
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
                                    delta = chunk_obj["choices"][0]["delta"].get("content")
                                    if delta:
                                        yield delta
                                except Exception:
                                    continue
                    return
                except Exception as e:
                    last_exc = e
                    if is_model_not_found(e):
                        continue
                    logger.warning("SambaNova stream failure (%s), rotating...", type(e).__name__)
                    break

        raise RuntimeError(f"All SambaNova stream keys failed: {last_exc}")
