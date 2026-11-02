"""
Google Gemini AI Provider Adapter with multimodal PDF ingestion and SSE streaming.
"""

import json
import time
import logging
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict, Any, Optional, Iterator
from ai_routing.providers.base import BaseProvider, ProviderResult, is_model_not_found, is_auth_error, is_rate_limit
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


def _retry_after_seconds(response, default: float = 60.0) -> float:
    value = (getattr(response, "headers", {}) or {}).get("Retry-After")
    if not value:
        return default
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return default


def _gemini_model_chain(primary_model: str) -> List[str]:
    """Return the chosen model and at most one eligible model-specific alternate."""
    primary_spec = registry.get_model_spec(primary_model)
    if not primary_spec or not primary_spec.documentation_verified or not registry.is_model_policy_eligible("gemini", primary_model):
        raise RuntimeError("Selected Gemini model is not eligible under registry policy")
    alternate = "gemini-3.6-flash" if primary_model == "gemini-3.8-flash" else "gemini-3.8-flash"
    alternate_spec = registry.get_model_spec(alternate)
    chain = [primary_model]
    if (
        alternate_spec
        and alternate_spec.documentation_verified
        and alternate_spec.supports_streaming
        and registry.is_model_policy_eligible("gemini", alternate)
    ):
        chain.append(alternate)
    return chain

class GeminiProvider(BaseProvider):
    def __init__(self):
        super().__init__()
        self.last_stream_model: Optional[str] = None

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
        # A request uses one selected model. Only model-specific rejection can trigger
        # one eligible, documentation-verified alternate before provider failover.
        model_chain = _gemini_model_chain(primary_model)

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
                spec = registry.get_model_spec(model)
                timeout = spec.timeout_sec if spec else 30
                resp = _http_post(url, json=req_payload, timeout=timeout)
                if resp.status_code == 429:
                    cooldown = _retry_after_seconds(resp)
                    rot.quarantine_all(cooldown_seconds=cooldown)
                    error_text = str(getattr(resp, "text", "")).lower()
                    category = "project quota exhausted" if "quota" in error_text or "resource_exhausted" in error_text else "temporary rate limit"
                    logger.warning("Gemini 429 %s; applying project-wide cooldown", category)
                    raise RuntimeError(f"Gemini {category} (429)")
                if resp.status_code == 403:
                    registry.mark_model_access_denied(model)
                    last_exc = RuntimeError("Gemini model access denied (403)")
                    continue
                if resp.status_code == 401:
                    raise RuntimeError("Gemini API key invalid (401)")
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

                registry.mark_model_validated(model)
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
                    registry.mark_model_unavailable(model, cooldown_seconds=900.0)
                    continue
                if "project access denied" in str(e).lower() or "403" in str(e):
                    registry.mark_model_access_denied(model)
                    continue
                if is_auth_error(e) or is_rate_limit(e):
                    raise
                logger.warning("Gemini model execution error on %s (%s): %s", model, masked_key, type(e).__name__)
                # Invalid request parameters and transient provider failures are handled
                # at provider failover; do not fan one request out across Gemini models.
                raise

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
        self.last_stream_model = None
        rot = registry.get_rotator("gemini")
        if not rot or rot.key_count == 0:
            raise RuntimeError("NO_KEYS: gemini")

        primary_model = model_id or registry.gemini_reasoning_model
        model_chain = _gemini_model_chain(primary_model)

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
                spec = registry.get_model_spec(model)
                timeout = spec.timeout_sec if spec else 25
                resp = _http_post(url, json=req_payload, stream=True, timeout=timeout)
                if resp.status_code == 429:
                    cooldown = _retry_after_seconds(resp)
                    rot.quarantine_all(cooldown_seconds=cooldown)
                    error_text = str(getattr(resp, "text", "")).lower()
                    category = "project quota exhausted" if "quota" in error_text or "resource_exhausted" in error_text else "temporary rate limit"
                    logger.warning("Gemini stream 429 %s; applying project-wide cooldown", category)
                    raise RuntimeError(f"Gemini stream {category} (429)")
                if resp.status_code == 403:
                    registry.mark_model_access_denied(model)
                    last_exc = RuntimeError("Gemini model access denied (403)")
                    continue
                if resp.status_code == 401:
                    raise RuntimeError("Gemini API key invalid (401)")
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
                registry.mark_model_validated(model)
                self.last_stream_model = model
                return
            except Exception as e:
                last_exc = e
                if is_model_not_found(e):
                    registry.mark_model_unavailable(model, cooldown_seconds=900.0)
                    continue
                if "project access denied" in str(e).lower() or "403" in str(e):
                    registry.mark_model_access_denied(model)
                    continue
                if is_auth_error(e) or is_rate_limit(e):
                    raise
                logger.warning("Gemini stream model failure on %s (%s): %s", model, masked_key, type(e).__name__)
                raise

        raise RuntimeError(f"All Gemini models failed during stream on {masked_key}: {last_exc}")
