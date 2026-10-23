"""
Cerebras Cloud Provider Adapter (ultra-fast 1000+ tok/s).
"""

import json
import time
import logging
import requests
from typing import List, Dict, Any, Optional, Iterator
from ai_routing.providers.base import BaseProvider, ProviderResult, is_model_not_found
from ai_routing.registry import registry

logger = logging.getLogger("cerebras_provider")

class CerebrasProvider(BaseProvider):
    def generate(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        max_tokens: int,
        model_id: Optional[str] = None,
        json_output: bool = False,
        multimodal_parts: Optional[List[Dict[str, Any]]] = None
    ) -> ProviderResult:
        rot = registry.get_rotator("cerebras")
        if not rot or rot.key_count == 0:
            raise RuntimeError("NO_KEYS: cerebras")

        primary_model = model_id or "gpt-oss-120b"
        model_chain = [primary_model, "qwen-3.8-27b", "llama3.1-8b"]
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
                        "max_tokens": min(max_tokens or 2048, 2048)
                    }
                    resp = requests.post(
                        "https://api.cerebras.ai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                        json=payload,
                        timeout=20
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
                        provider="cerebras",
                        finish_reason=finish,
                        latency_ms=latency
                    )
                except Exception as e:
                    last_exc = e
                    if is_model_not_found(e):
                        continue
                    logger.warning("Cerebras key failure (%s), rotating...", type(e).__name__)
                    break

        raise RuntimeError(f"All Cerebras keys/models failed: {last_exc}")

    def stream(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        max_tokens: int,
        model_id: Optional[str] = None,
        multimodal_parts: Optional[List[Dict[str, Any]]] = None
    ) -> Iterator[str]:
        self.last_stream_finish_reason = None
        rot = registry.get_rotator("cerebras")
        if not rot or rot.key_count == 0:
            raise RuntimeError("NO_KEYS: cerebras")

        primary_model = model_id or "gpt-oss-120b"
        model_chain = [primary_model, "qwen-3.8-27b", "llama3.1-8b"]
        model_chain = list(dict.fromkeys(model_chain))

        last_exc = None
        for _ in range(rot.key_count):
            key = rot.get_key()
            for model in model_chain:
                try:
                    payload = {
                        "model": model,
                        "messages": [{"role": "system", "content": system_prompt}] + messages,
                        "max_tokens": min(max_tokens or 2048, 2048),
                        "stream": True
                    }
                    resp = requests.post(
                        "https://api.cerebras.ai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                        json=payload,
                        stream=True,
                        timeout=20
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
                                    choices = chunk_obj.get("choices", [])
                                    if choices:
                                        c0 = choices[0]
                                        fr = c0.get("finish_reason")
                                        if fr:
                                            self.last_stream_finish_reason = fr
                                        delta = c0.get("delta", {}).get("content")
                                        if delta:
                                            yield delta
                                except Exception:
                                    continue
                    return
                except Exception as e:
                    last_exc = e
                    if is_model_not_found(e):
                        continue
                    logger.warning("Cerebras stream failure (%s), rotating...", type(e).__name__)
                    break

        raise RuntimeError(f"All Cerebras stream keys failed: {last_exc}")
