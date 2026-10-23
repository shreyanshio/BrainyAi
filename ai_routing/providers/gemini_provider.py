"""
Google Gemini AI Provider Adapter with multimodal PDF ingestion and SSE streaming.
"""

import json
import time
import logging
import requests
from typing import List, Dict, Any, Optional, Iterator
from ai_routing.providers.base import BaseProvider, ProviderResult, is_model_not_found
from ai_routing.registry import registry

logger = logging.getLogger("gemini_provider")

class GeminiProvider(BaseProvider):
    def generate(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        max_tokens: int,
        model_id: Optional[str] = None,
        json_output: bool = False,
        multimodal_parts: Optional[List[Dict[str, Any]]] = None
    ) -> ProviderResult:
        rot = registry.get_rotator("gemini")
        if not rot or rot.key_count == 0:
            raise RuntimeError("NO_KEYS: gemini")

        primary_model = model_id or registry.gemini_reasoning_model
        model_chain = [primary_model, "gemini-2.0-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"]
        model_chain = list(dict.fromkeys(model_chain))

        start_t = time.perf_counter()
        last_exc = None

        # Build contents
        contents = []
        for idx, m in enumerate(messages):
            role = "user" if m.get("role") == "user" else "model"
            parts: List[Dict[str, Any]] = []
            # Attach multimodal parts (PDF / Images) to the first user message if provided
            if idx == 0 and role == "user" and multimodal_parts:
                parts.extend(multimodal_parts)
            text_val = m.get("content") or ""
            if text_val:
                parts.append({"text": text_val})
            if parts:
                contents.append({"role": role, "parts": parts})

        if not contents and multimodal_parts:
            contents.append({"role": "user", "parts": multimodal_parts})

        payload: Dict[str, Any] = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens or 2048}
        }
        if json_output:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        for _ in range(rot.key_count):
            key = rot.get_key()
            for model in model_chain:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                    resp = requests.post(url, json=payload, timeout=30)
                    resp.raise_for_status()
                    data = resp.json()
                    candidate = data["candidates"][0]
                    parts_resp = candidate.get("content", {}).get("parts", [])
                    if not parts_resp:
                        raise RuntimeError("Gemini returned empty parts in candidate")
                    text = parts_resp[0].get("text", "")
                    latency = (time.perf_counter() - start_t) * 1000.0
                    finish = candidate.get("finishReason", "stop")

                    return ProviderResult(
                        text=text,
                        model=model,
                        provider="gemini",
                        finish_reason=finish,
                        latency_ms=latency
                    )
                except Exception as e:
                    last_exc = e
                    if is_model_not_found(e):
                        continue
                    logger.warning("Gemini key failure (%s), rotating to next key...", type(e).__name__)
                    break

        raise RuntimeError(f"All Gemini keys/models failed: {last_exc}")

    def stream(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        max_tokens: int,
        model_id: Optional[str] = None,
        multimodal_parts: Optional[List[Dict[str, Any]]] = None
    ) -> Iterator[str]:
        rot = registry.get_rotator("gemini")
        if not rot or rot.key_count == 0:
            raise RuntimeError("NO_KEYS: gemini")

        primary_model = model_id or registry.gemini_reasoning_model
        model_chain = [primary_model, "gemini-2.0-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"]
        model_chain = list(dict.fromkeys(model_chain))

        contents = []
        for idx, m in enumerate(messages):
            role = "user" if m.get("role") == "user" else "model"
            parts = []
            if idx == 0 and role == "user" and multimodal_parts:
                parts.extend(multimodal_parts)
            text_val = m.get("content") or ""
            if text_val:
                parts.append({"text": text_val})
            if parts:
                contents.append({"role": role, "parts": parts})

        if not contents and multimodal_parts:
            contents.append({"role": "user", "parts": multimodal_parts})

        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens or 2048}
        }

        last_exc = None
        for _ in range(rot.key_count):
            key = rot.get_key()
            for model in model_chain:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={key}"
                    resp = requests.post(url, json=payload, stream=True, timeout=25)
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if line:
                            line_str = line.decode("utf-8")
                            if line_str.startswith("data: "):
                                try:
                                    chunk_obj = json.loads(line_str[6:].strip())
                                    candidates = chunk_obj.get("candidates", [])
                                    if candidates:
                                        p = candidates[0].get("content", {}).get("parts", [])
                                        if p and "text" in p[0]:
                                            yield p[0]["text"]
                                except Exception:
                                    continue
                    return
                except Exception as e:
                    last_exc = e
                    if is_model_not_found(e):
                        continue
                    logger.warning("Gemini stream failure (%s), rotating...", type(e).__name__)
                    break

        raise RuntimeError(f"All Gemini stream keys failed: {last_exc}")
