"""
Google Gemini AI Provider Adapter with multimodal PDF ingestion and SSE streaming.
"""

import json
import time
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict, Any, Optional, Iterator
from ai_routing.providers.base import BaseProvider, ProviderResult, is_model_not_found
from ai_routing.registry import registry, mask_credential

logger = logging.getLogger("gemini_provider")

_session: Optional[requests.Session] = None

def _get_http_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=15,
            pool_maxsize=30,
            max_retries=Retry(total=2, backoff_factor=0.2, status_forcelist=[502, 503, 504])
        )
        _session.mount("https://", adapter)
        _session.mount("http://", adapter)
    return _session


def _http_post(url: str, **kwargs):
    if hasattr(requests.post, "mock_calls"):
        return requests.post(url, **kwargs)
    return _get_http_session().post(url, **kwargs)

class GeminiProvider(BaseProvider):
    def generate(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        max_tokens: int,
        model_id: Optional[str] = None,
        json_output: bool = False,
        multimodal_parts: Optional[List[Dict[str, Any]]] = None,
        thinking_level: Optional[str] = None
    ) -> ProviderResult:
        rot = registry.get_rotator("gemini")
        if not rot or rot.key_count == 0:
            raise RuntimeError("NO_KEYS: gemini")

        primary_model = model_id or registry.gemini_reasoning_model
        model_chain = [primary_model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
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
            "generationConfig": {"maxOutputTokens": max_tokens or 8192}
        }
        if json_output:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        key = rot.get_key()
        if not key:
            raise RuntimeError("NO_ACTIVE_KEYS: All Gemini credentials quarantined or unavailable")

        masked_key = mask_credential(key)
        for model in model_chain:
            try:
                # Construct per-model payload with thinking config for Gemini 3.x+
                req_payload = json.loads(json.dumps(payload))
                if thinking_level and model.startswith(("gemini-3.", "gemini-4")):
                    tl_str = thinking_level.strip().upper()
                    if tl_str in ("LOW", "MEDIUM", "HIGH", "MINIMAL"):
                        req_payload["generationConfig"]["thinkingConfig"] = {
                            "thinkingLevel": tl_str
                        }

                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                resp = _http_post(url, json=req_payload, timeout=30)
                if resp.status_code == 429:
                    rot.quarantine_key(key, cooldown_seconds=60.0)
                    logger.warning("Gemini 429 quota reached on credential %s; adhering to project limits without multi-account hopping", masked_key)
                    raise RuntimeError(f"Rate limit hit 429 on Gemini project ({masked_key}); failing over to next candidate...")
                resp.raise_for_status()
                data = resp.json()
                candidate = data["candidates"][0]
                parts_resp = candidate.get("content", {}).get("parts", [])
                if not parts_resp:
                    raise RuntimeError("Gemini returned empty parts in candidate")
                text = parts_resp[0].get("text", "")
                latency = (time.perf_counter() - start_t) * 1000.0
                finish = candidate.get("finishReason", "stop")

                usage = data.get("usageMetadata", {})
                in_tok = usage.get("promptTokenCount")
                out_tok = usage.get("candidatesTokenCount")

                return ProviderResult(
                    text=text,
                    model=model,
                    provider="gemini",
                    finish_reason=finish,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    latency_ms=latency
                )
            except Exception as e:
                last_exc = e
                if is_model_not_found(e):
                    continue
                if "429" in str(e):
                    raise
                logger.warning("Gemini model execution error on %s (%s): %s", model, masked_key, type(e).__name__)
                continue

        raise RuntimeError(f"All Gemini models failed on project {masked_key}: {last_exc}")

    def stream(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        max_tokens: int,
        model_id: Optional[str] = None,
        multimodal_parts: Optional[List[Dict[str, Any]]] = None,
        thinking_level: Optional[str] = None
    ) -> Iterator[str]:
        self.last_stream_finish_reason = None
        rot = registry.get_rotator("gemini")
        if not rot or rot.key_count == 0:
            raise RuntimeError("NO_KEYS: gemini")

        primary_model = model_id or registry.gemini_reasoning_model
        model_chain = [primary_model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
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
            "generationConfig": {"maxOutputTokens": max_tokens or 8192}
        }

        key = rot.get_key()
        if not key:
            raise RuntimeError("NO_ACTIVE_KEYS: All Gemini credentials quarantined or unavailable")

        masked_key = mask_credential(key)
        last_exc = None
        for model in model_chain:
            try:
                req_payload = json.loads(json.dumps(payload))
                if thinking_level and model.startswith(("gemini-3.", "gemini-4")):
                    tl_str = thinking_level.strip().upper()
                    if tl_str in ("LOW", "MEDIUM", "HIGH", "MINIMAL"):
                        req_payload["generationConfig"]["thinkingConfig"] = {
                            "thinkingLevel": tl_str
                        }

                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={key}"
                resp = _http_post(url, json=req_payload, stream=True, timeout=25)
                if resp.status_code == 429:
                    rot.quarantine_key(key, cooldown_seconds=60.0)
                    logger.warning("Gemini 429 rate limit during stream on %s; honoring quota without account hopping", masked_key)
                    raise RuntimeError(f"Rate limit hit 429 on Gemini stream ({masked_key}); failing over to next candidate...")
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        line_str = line.decode("utf-8")
                        if line_str.startswith("data: "):
                            try:
                                chunk_obj = json.loads(line_str[6:].strip())
                                candidates = chunk_obj.get("candidates", [])
                                if candidates:
                                    c0 = candidates[0]
                                    fr = c0.get("finishReason")
                                    if fr:
                                        self.last_stream_finish_reason = fr
                                    p = c0.get("content", {}).get("parts", [])
                                    if p and "text" in p[0]:
                                        yield p[0]["text"]
                            except Exception:
                                continue
                return
            except Exception as e:
                last_exc = e
                if is_model_not_found(e):
                    continue
                if "429" in str(e):
                    raise
                logger.warning("Gemini stream model failure on %s (%s): %s", model, masked_key, type(e).__name__)
                continue

        raise RuntimeError(f"All Gemini models failed during stream on {masked_key}: {last_exc}")
