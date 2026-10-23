"""
BrainyAi Intelligent Multi-Provider AI Router
Dispatches requests to optimal providers with automatic failover,
bounded retries, telemetry, and pre-output streaming fallback guarantees.
"""

import time
import json
import uuid
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Iterator, Tuple

from ai_routing.tasks import TaskType, ResponseDepth, classify_task
from ai_routing.policy import get_routing_candidates
from ai_routing.telemetry import global_telemetry, TelemetryRecord
from ai_routing.providers.base import BaseProvider, ProviderResult
from ai_routing.providers.groq_provider import GroqProvider
from ai_routing.providers.gemini_provider import GeminiProvider
from ai_routing.providers.sambanova_provider import SambaNovaProvider
from ai_routing.providers.cerebras_provider import CerebrasProvider
from ai_routing.providers.openrouter_provider import OpenRouterProvider
from ai_routing.providers.search_provider import execute_search

logger = logging.getLogger("ai_router")

@dataclass
class RouterResponse:
    text: str
    task: TaskType
    depth: ResponseDepth
    provider: str
    model: str
    latency_ms: float
    fallback_used: bool = False
    fallback_from: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    citations: Optional[List[Dict[str, str]]] = None

class AIRouter:
    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {
            "groq": GroqProvider(),
            "gemini": GeminiProvider(),
            "sambanova": SambaNovaProvider(),
            "cerebras": CerebrasProvider(),
            "openrouter": OpenRouterProvider(),
        }

    def get_provider(self, name: str) -> Optional[BaseProvider]:
        return self._providers.get(name.lower())

    def _resolve_budget(self, task: TaskType, depth: ResponseDepth, max_tokens: Optional[int] = None) -> int:
        if max_tokens:
            return max_tokens
        if depth == ResponseDepth.FAST:
            return 1024
        if depth == ResponseDepth.DEEP or task in (TaskType.DEEP_REASONING, TaskType.MATH_AND_LOGIC, TaskType.DETAILED_EXPLANATION, TaskType.NOTE_GENERATION):
            return 3200
        return 2048

    def generate(
        self,
        prompt: str | List[Dict[str, str]] = "",
        messages: Optional[List[Dict[str, str]]] = None,
        task: Optional[TaskType | str] = None,
        depth: Optional[ResponseDepth | str] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        json_output: bool = False,
        document_context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        candidate_chain: Optional[List[Tuple[str, str]]] = None
    ) -> RouterResponse:
        """
        Unified non-streaming AI generation with automatic task inference and failover.
        """
        if isinstance(prompt, list):
            messages = prompt
            prompt = ""
        if isinstance(prompt, list):
            messages = prompt
            prompt = ""
        req_id = request_id or str(uuid.uuid4())
        resolved_depth = ResponseDepth.from_str(str(depth)) if depth else ResponseDepth.BALANCED
        resolved_task = classify_task(prompt, messages, document_context, explicit_task=task, depth=resolved_depth)
        token_budget = self._resolve_budget(resolved_task, resolved_depth, max_tokens)
        sys_prompt = system_prompt or "You are Brainy, an intelligent, empathetic, academic AI study companion."

        # Prepare messages
        call_messages = list(messages) if messages else []
        if prompt and (not call_messages or call_messages[-1].get("content") != prompt):
            call_messages.append({"role": "user", "content": prompt})

        # ── Web Research Pre-Search Hook ──
        citations = []
        if resolved_task == TaskType.WEB_RESEARCH:
            search_data = execute_search(prompt or (call_messages[-1]["content"] if call_messages else ""))
            citations = search_data.get("citations", [])
            if citations or search_data.get("direct_answer"):
                snippet_text = "\n\n".join(
                    f"[{idx+1}] {c.get('title')}: {c.get('snippet')} (URL: {c.get('url')})"
                    for idx, c in enumerate(citations)
                )
                grounding_block = (
                    f"\n\n--- LIVE WEB RETRIEVAL DATA ---\n"
                    f"Direct fact: {search_data.get('direct_answer')}\n\n"
                    f"Sources:\n{snippet_text}\n"
                    f"Instructions: Use the above factual search findings to answer accurately. "
                    f"Cite sources using markdown links [Source Name](url)."
                )
                call_messages[-1]["content"] += grounding_block

        candidates = candidate_chain or get_routing_candidates(resolved_task, resolved_depth)
        fallback_used = False
        fallback_from = None
        last_exc = None
        start_all = time.perf_counter()

        for idx, (provider_name, model_id) in enumerate(candidates):
            provider = self.get_provider(provider_name)
            if not provider:
                continue

            try:
                res = provider.generate(
                    messages=call_messages,
                    system_prompt=sys_prompt,
                    max_tokens=token_budget,
                    model_id=model_id,
                    json_output=json_output,
                    multimodal_parts=document_context.get("multimodal_parts") if document_context else None
                )

                # Record successful telemetry
                global_telemetry.record(TelemetryRecord(
                    request_id=req_id,
                    task=resolved_task.value,
                    depth=resolved_depth.value,
                    provider=provider_name,
                    model=res.model,
                    latency_ms=res.latency_ms,
                    input_tokens=res.input_tokens,
                    output_tokens=res.output_tokens,
                    fallback_used=fallback_used,
                    fallback_from=fallback_from,
                    status="success" if not fallback_used else "fallback_recovered"
                ))

                return RouterResponse(
                    text=res.text,
                    task=resolved_task,
                    depth=resolved_depth,
                    provider=provider_name,
                    model=res.model,
                    latency_ms=(time.perf_counter() - start_all) * 1000.0,
                    fallback_used=fallback_used,
                    fallback_from=fallback_from,
                    input_tokens=res.input_tokens,
                    output_tokens=res.output_tokens,
                    citations=citations
                )
            except Exception as e:
                last_exc = e
                fallback_used = True
                if fallback_from is None:
                    fallback_from = provider_name
                logger.warning(
                    "Candidate failed (%s/%s) req_id=%s error=%s; falling back to next candidate...",
                    provider_name, model_id, req_id, str(e)[:80]
                )
                continue

        # Record failure telemetry if all candidates failed
        global_telemetry.record(TelemetryRecord(
            request_id=req_id,
            task=resolved_task.value,
            depth=resolved_depth.value,
            provider="none",
            model="none",
            latency_ms=(time.perf_counter() - start_all) * 1000.0,
            fallback_used=fallback_used,
            fallback_from=fallback_from,
            error_category=type(last_exc).__name__ if last_exc else "Exhausted",
            status="error"
        ))
        raise RuntimeError(f"All AI routing candidates failed: {last_exc}")

    def stream(
        self,
        prompt: str | List[Dict[str, str]] = "",
        messages: Optional[List[Dict[str, str]]] = None,
        task: Optional[TaskType | str] = None,
        depth: Optional[ResponseDepth | str] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        document_context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        candidate_chain: Optional[List[Tuple[str, str]]] = None
    ) -> Iterator[str]:
        """
        Unified real-time streaming with pre-output fallback guarantee.
        If a provider errors before emitting the first token, it falls back to the next candidate.
        If stream breaks midway after tokens were delivered, it raises cleanly without duplicating text.
        """
        req_id = request_id or str(uuid.uuid4())
        resolved_depth = ResponseDepth.from_str(str(depth)) if depth else ResponseDepth.BALANCED
        resolved_task = classify_task(prompt, messages, document_context, explicit_task=task, depth=resolved_depth)
        token_budget = self._resolve_budget(resolved_task, resolved_depth, max_tokens)
        sys_prompt = system_prompt or "You are Brainy, an intelligent, empathetic, academic AI study companion."

        call_messages = list(messages) if messages else []
        if prompt and (not call_messages or call_messages[-1].get("content") != prompt):
            call_messages.append({"role": "user", "content": prompt})

        candidates = candidate_chain or get_routing_candidates(resolved_task, resolved_depth)
        fallback_used = False
        fallback_from = None
        last_exc = None
        start_t = time.perf_counter()

        for provider_name, model_id in candidates:
            provider = self.get_provider(provider_name)
            if not provider:
                continue

            started = False
            first_token_t = None
            try:
                for token in provider.stream(
                    messages=call_messages,
                    system_prompt=sys_prompt,
                    max_tokens=token_budget,
                    model_id=model_id,
                    multimodal_parts=document_context.get("multimodal_parts") if document_context else None
                ):
                    if token:
                        if not started:
                            started = True
                            first_token_t = (time.perf_counter() - start_t) * 1000.0
                        yield token

                if started:
                    # Successfully completed stream
                    total_lat = (time.perf_counter() - start_t) * 1000.0
                    global_telemetry.record(TelemetryRecord(
                        request_id=req_id,
                        task=resolved_task.value,
                        depth=resolved_depth.value,
                        provider=provider_name,
                        model=model_id,
                        latency_ms=total_lat,
                        ttft_ms=first_token_t,
                        fallback_used=fallback_used,
                        fallback_from=fallback_from,
                        status="success" if not fallback_used else "fallback_recovered"
                    ))
                    return
            except Exception as e:
                last_exc = e
                if started:
                    # Stream interrupted midway: do not attempt to replay stream with a second provider
                    logger.error("Stream interrupted midway on %s req_id=%s: %s", provider_name, req_id, e)
                    raise
                else:
                    # Failed before emitting any token: safely try next candidate
                    fallback_used = True
                    if fallback_from is None:
                        fallback_from = provider_name
                    logger.warning("Streaming candidate %s failed before first token: %s, rotating...", provider_name, e)
                    continue

        raise RuntimeError(f"All streaming candidates exhausted: {last_exc}")

    def generate_structured(
        self,
        prompt: str,
        system_prompt: str,
        task: TaskType,
        max_tokens: int = 2500,
        retries: int = 2,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates and parses guaranteed JSON output. If JSON decode fails, retries once.
        """
        for attempt in range(retries):
            resp = self.generate(
                prompt=prompt,
                task=task,
                depth=ResponseDepth.BALANCED,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
                json_output=True,
                request_id=request_id
            )
            raw = resp.text.strip()
            # Strip markdown json code fences if present
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.startswith("```"):
                raw = raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                if attempt == retries - 1:
                    logger.error("JSON decode error on structured output: %s", raw[:200])
                    raise RuntimeError(f"Model output could not be parsed as JSON: {exc}")
                continue

        raise RuntimeError("Failed to generate structured JSON output")

# Global singleton router
router = AIRouter()
