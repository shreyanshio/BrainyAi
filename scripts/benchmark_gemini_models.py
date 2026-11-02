#!/usr/bin/env python3
"""Live Gemini model validation/benchmark. Reports metadata, latency, tokens and errors.

Run with GEMINI_API_KEY set. This intentionally sends short prompts to each selected model.
Quality scoring is left as not_scored; no synthetic benchmark claims are produced.
"""

import argparse
import json
import time
from typing import Any, Dict, Optional

import requests

from ai_routing.registry import registry, CostCategory


CASES = {
    "conversation": "Explain what a variable is in one sentence.",
    "long_explanation": "Explain photosynthesis in four clear steps for a high school student.",
    "coding": "Write a Python function that returns the first repeated integer in a list.",
    "reasoning": "A clock loses 5 minutes every hour. How many real hours pass before it is 20 minutes slow? Explain.",
    "mathematics": "Solve 3x + 7 = 22 and show the key steps.",
    "pdf_analysis_text_fixture": "Summarize this sample document in one sentence: Photosynthesis converts light, water, and carbon dioxide into sugars and oxygen.",
}


def classify_error(status: Optional[int], message: str) -> str:
    text = message.lower()
    if status in (401,):
        return "api_key_invalid"
    if status == 403:
        return "model_access_denied_or_project_policy"
    if status == 404:
        return "model_unavailable"
    if status == 429:
        return "rate_limit_or_project_quota"
    if status in (500, 502, 503, 504):
        return "provider_outage"
    if any(t in text for t in ("context", "token limit", "too large")):
        return "context_length_violation"
    if any(t in text for t in ("parameter", "unsupported", "invalid argument")):
        return "unsupported_parameter"
    return "request_failed"


def request_model(key: str, model: str, prompt: str, streaming: bool = False) -> Dict[str, Any]:
    suffix = ":streamGenerateContent?alt=sse" if streaming else ":generateContent"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}{suffix}"
    started = time.perf_counter()
    try:
        with requests.post(
            url,
            headers={"x-goog-api-key": key},
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 256}},
            stream=streaming,
            timeout=90,
        ) as response:
            if response.status_code >= 400:
                message = response.text[:300]
                return {"success": False, "error_category": classify_error(response.status_code, message), "http_status": response.status_code}
            first_token_ms = None
            text = ""
            usage = {}
            if streaming:
                for line in response.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data: "):
                        continue
                    try:
                        chunk = json.loads(line[6:])
                        chunk_text = "".join(p.get("text", "") for c in chunk.get("candidates", []) for p in c.get("content", {}).get("parts", []))
                        if chunk_text and first_token_ms is None:
                            first_token_ms = (time.perf_counter() - started) * 1000
                        text += chunk_text
                        usage.update(chunk.get("usageMetadata", {}))
                    except ValueError:
                        continue
            else:
                payload = response.json()
                text = "".join(p.get("text", "") for c in payload.get("candidates", []) for p in c.get("content", {}).get("parts", []))
                usage = payload.get("usageMetadata", {})
            return {
                "success": bool(text),
                "ttft_ms": round(first_token_ms, 1) if first_token_ms is not None else None,
                "total_ms": round((time.perf_counter() - started) * 1000, 1),
                "input_tokens": usage.get("promptTokenCount"),
                "output_tokens": usage.get("candidatesTokenCount"),
                "quality_score": "not_scored",
                "error_category": None if text else "empty_response",
            }
    except requests.Timeout:
        return {"success": False, "error_category": "timeout"}
    except requests.RequestException:
        return {"success": False, "error_category": "network_error"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", help="Validate one model ID; can be repeated")
    parser.add_argument("--include-paid", action="store_true", help="Include paid-only models in live calls")
    parser.add_argument("--image", help="Optional local image fixture for multimodal validation")
    parser.add_argument("--pdf", help="Optional local PDF fixture for document validation")
    args = parser.parse_args()
    key_rotator = registry.get_rotator("gemini")
    key = key_rotator.keys[0].strip() if key_rotator and key_rotator.keys else ""
    if not key:
        parser.error("Configure a Gemini API key to run live project-access checks.")
    models = args.model or [s.model_id for s in registry.get_model_catalog() if s["provider"] == "gemini"]
    results = []
    for model in models:
        spec = registry.get_model_spec(model)
        if not spec or not spec.documentation_verified:
            results.append({"model_id": model, "availability_status": "not_documented"})
            continue
        if spec.is_paid_only and not args.include_paid:
            results.append({"model_id": model, "availability_status": "not_tested_paid_model_requires_flag"})
            continue
        try:
            meta = requests.get(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}",
                headers={"x-goog-api-key": key}, timeout=20,
            )
        except requests.RequestException:
            results.append({"model_id": model, "availability_status": "network_error"})
            continue
        if meta.status_code != 200:
            category = classify_error(meta.status_code, meta.text[:300])
            if category == "model_access_denied_or_project_policy":
                registry.mark_model_access_denied(model)
            elif category == "model_unavailable":
                registry.mark_model_unavailable(model)
            results.append({"model_id": model, "availability_status": category, "http_status": meta.status_code})
            continue
        metadata = meta.json()
        model_result: Dict[str, Any] = {
            "model_id": model,
            "availability_status": "metadata_accessible",
            "supported_generation_methods": metadata.get("supportedGenerationMethods", []),
            "input_token_limit": metadata.get("inputTokenLimit"),
            "output_token_limit": metadata.get("outputTokenLimit"),
            "cases": {},
        }
        for name, prompt in CASES.items():
            model_result["cases"][name] = request_model(key, model, prompt)
        model_result["cases"]["streaming"] = request_model(key, model, CASES["conversation"], streaming=True)
        if args.image:
            import base64
            mime = "image/png" if args.image.lower().endswith(".png") else "image/jpeg"
            with open(args.image, "rb") as image_file:
                data = base64.b64encode(image_file.read()).decode("ascii")
            model_result["cases"]["image"] = request_model_with_part(key, model, {"inline_data": {"mime_type": mime, "data": data}, "text": "Describe this image in one sentence."})
        if args.pdf:
            with open(args.pdf, "rb") as pdf_file:
                data = __import__("base64").b64encode(pdf_file.read()).decode("ascii")
            model_result["cases"]["pdf"] = request_model_with_part(key, model, {"inline_data": {"mime_type": "application/pdf", "data": data}, "text": "Summarize this document in one sentence."})
        if any(case.get("success") for case in model_result["cases"].values()):
            registry.mark_model_validated(model)
            model_result["availability_status"] = "available"
        results.append(model_result)
    print(json.dumps({"models": results}, indent=2))
    return 0


def request_model_with_part(key: str, model: str, part: Dict[str, Any]) -> Dict[str, Any]:
    # Inline media is held only in memory and never written to the report.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    started = time.perf_counter()
    try:
        response = requests.post(url, headers={"x-goog-api-key": key}, json={"contents": [{"parts": [part]}]}, timeout=90)
        if response.status_code >= 400:
            return {"success": False, "error_category": classify_error(response.status_code, response.text[:300]), "http_status": response.status_code}
        payload = response.json()
        text = "".join(p.get("text", "") for c in payload.get("candidates", []) for p in c.get("content", {}).get("parts", []))
        usage = payload.get("usageMetadata", {})
        return {"success": bool(text), "ttft_ms": round((time.perf_counter() - started) * 1000, 1), "total_ms": round((time.perf_counter() - started) * 1000, 1), "input_tokens": usage.get("promptTokenCount"), "output_tokens": usage.get("candidatesTokenCount"), "quality_score": "not_scored"}
    except requests.Timeout:
        return {"success": False, "error_category": "timeout"}
    except requests.RequestException:
        return {"success": False, "error_category": "network_error"}


if __name__ == "__main__":
    raise SystemExit(main())
