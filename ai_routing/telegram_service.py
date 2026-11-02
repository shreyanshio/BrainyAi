"""
Application & Use-Case Layer for Brainy Telegram Experience.
Decouples Telegram Interface Adapter (study_bot.py) from AI Routing,
Memory Persistence, Quota Reservation, and Language Intelligence.
"""

import io
import os
import uuid
import base64
import logging
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass

from ai_routing.idempotency import idempotency_engine
from ai_routing.quota import (
    IMAGE_FREE_LIMIT,
    get_user_image_quota,
    reserve_image_quota,
    commit_image_quota,
    release_image_quota,
    link_telegram_to_web_account,
    resolve_effective_identity,
)
from ai_routing.language import detect_language, apply_language_directive, LanguageProfile

logger = logging.getLogger(__name__)


@dataclass
class ServiceResult:
    success: bool
    text: str
    remaining_quota: Optional[int] = None
    is_duplicate: bool = False
    error_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TelegramService:
    """Enterprise application service for Telegram bot use-cases."""

    def __init__(self):
        self._vision_models = [
            os.getenv("GEMINI_VISION_MODEL", "gemini-3.8-flash"),
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-2.5-flash",
        ]

    def process_chat_query(
        self,
        user_id: int,
        query: str,
        is_group: bool,
        update_id: Optional[int] = None,
        system_prompt: Optional[str] = None,
        liked_context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> ServiceResult:
        """
        Coordinates chat query processing:
        1. Checks idempotency on update_id to prevent duplicate processing.
        2. Detects user language/script and applies deterministic directives.
        3. Enforces group chat isolation (zero memory pollution).
        4. Invokes central AI routing engine.
        """
        idem_key = f"tg_msg_{update_id}" if update_id else None
        if idem_key:
            claimed, rec = idempotency_engine.claim(idem_key)
            if not claimed:
                logger.info(f"Duplicate update_id {update_id} dropped by idempotency engine.")
                return ServiceResult(
                    success=True,
                    text=rec.result if rec and rec.result else "",
                    is_duplicate=True
                )

        clean_query = (query or "").strip()
        if not clean_query:
            if idem_key:
                idempotency_engine.release_or_fail(idem_key)
            return ServiceResult(success=False, text="Empty query received.", error_code="EMPTY_QUERY")

        # Language intelligence
        lang_profile = detect_language(clean_query)
        base_prompt = system_prompt or "You are Brainy, an intelligent study assistant."
        if liked_context and not is_group:
            base_prompt = f"{base_prompt}\n\n{liked_context}"
        effective_prompt = apply_language_directive(base_prompt, lang_profile)

        # Context isolation
        if is_group:
            messages = [{"role": "user", "content": clean_query}]
            platform_str = "telegram_group"
        else:
            messages = list(history or [])
            messages.append({"role": "user", "content": clean_query})
            platform_str = "telegram_dm"

        # Routing to AI
        try:
            from ai_routing.router import router
            from ai_routing.tasks import classify_task, ResponseDepth
            task = classify_task(messages, effective_prompt)
            depth = ResponseDepth.FAST if is_group else ResponseDepth.BALANCED

            res = router.generate(
                messages=messages,
                task=task,
                depth=depth,
                system_prompt=effective_prompt,
                platform=platform_str,
                user_id=resolve_effective_identity(user_id)
            )

            result_text = res.text if res and res.text else ""
            if not result_text:
                raise RuntimeError("Empty response received from AI router.")

            if idem_key:
                idempotency_engine.complete(idem_key, result=result_text)

            return ServiceResult(
                success=True,
                text=result_text,
                metadata={"provider": getattr(res, "provider", "unknown"), "lang": lang_profile.language}
            )

        except Exception as exc:
            logger.error(f"Error in TelegramService.process_chat_query: {exc}")
            if idem_key:
                idempotency_engine.release_or_fail(idem_key)
            return ServiceResult(
                success=False,
                text=str(exc),
                error_code="AI_ROUTING_FAILURE"
            )

    def process_image_analysis(
        self,
        user_id: int,
        image_bytes: bytes,
        question: str,
        is_group: bool,
        update_id: Optional[int] = None,
    ) -> ServiceResult:
        """
        Coordinates multimodal image analysis:
        1. Two-phase quota reservation (reserve -> inference -> commit/release).
        2. Idempotency against duplicate update_id delivery.
        3. Real Gemini Vision reasoning.
        """
        idem_key = f"tg_img_{update_id}" if update_id else None
        if idem_key:
            claimed, rec = idempotency_engine.claim(idem_key)
            if not claimed:
                logger.info(f"Duplicate image update {update_id} dropped by idempotency engine.")
                return ServiceResult(
                    success=True,
                    text=rec.result if rec and rec.result else "",
                    is_duplicate=True
                )

        if not image_bytes or len(image_bytes) == 0:
            if idem_key:
                idempotency_engine.release_or_fail(idem_key)
            return ServiceResult(success=False, text="Empty image payload received.", error_code="INVALID_IMAGE")

        # Step 1: Two-Phase Quota Reservation
        res_id, remaining, effective_id = reserve_image_quota(user_id, idempotency_key=idem_key)
        if not res_id:
            if idem_key:
                idempotency_engine.release_or_fail(idem_key)
            return ServiceResult(
                success=False,
                text=(
                    "⚠️ You've used your 5 free image requests.\n\n"
                    "Your image allowance is currently exhausted. You can continue asking text questions anytime, "
                    "or link your account with /link."
                ),
                remaining_quota=0,
                error_code="IMAGE_QUOTA_EXHAUSTED"
            )

        # Step 2: Gemini Vision Processing
        try:
            import google.generativeai as genai
            from study_bot import GEMINI_API_KEYS, _rotate_key, clean_response

            if not GEMINI_API_KEYS:
                raise RuntimeError("NO_KEYS: No Gemini API keys configured.")

            key = _rotate_key("gemini", GEMINI_API_KEYS)
            genai.configure(api_key=key)

            img_part = {"mime_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode("utf-8")}
            prompt_text = question or "Please analyze and explain this study material in detail."

            # Apply language intelligence to prompt
            lang_profile = detect_language(prompt_text)
            directive = apply_language_directive(
                "You are Brainy, an expert multimodal study assistant. Provide clear, step-by-step solutions.",
                lang_profile
            )

            result_text = None
            last_err = None
            for model_name in self._vision_models:
                try:
                    model = genai.GenerativeModel(model_name=model_name, system_instruction=directive)
                    resp = model.generate_content([img_part, prompt_text])
                    if resp and resp.text:
                        result_text = clean_response(resp.text)
                        break
                except Exception as m_err:
                    last_err = m_err
                    logger.warning(f"Vision model {model_name} failed: {m_err}")

            if not result_text:
                raise RuntimeError(f"All vision models failed. Last error: {last_err}")

            # Step 3: Commit Quota on Success
            commit_image_quota(res_id)
            if idem_key:
                idempotency_engine.complete(idem_key, result=result_text)

            return ServiceResult(
                success=True,
                text=result_text,
                remaining_quota=remaining,
                metadata={"effective_id": effective_id}
            )

        except Exception as exc:
            # Step 4: Release Quota on Failure
            release_image_quota(res_id)
            if idem_key:
                idempotency_engine.release_or_fail(idem_key)
            logger.error(f"Image analysis failed: {exc}")
            return ServiceResult(
                success=False,
                text=f"❌ Error scanning image: {str(exc)[:100]}\n\n⏳ Free quota refunded. Try again in a bit!",
                remaining_quota=remaining + 1,
                error_code="VISION_FAILURE"
            )

    def link_account(self, telegram_id: int, link_code: str) -> ServiceResult:
        """Executes account linking via single-use 6-character code."""
        success, res = link_telegram_to_web_account(telegram_id, link_code)
        if success:
            return ServiceResult(
                success=True,
                text=(
                    "✅ 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆 𝗟𝗶𝗻𝗸𝗲𝗱!\n\n"
                    "Your Telegram account is now unified with your Brainy Web account.\n"
                    "• Shared 5-image reasoning allowance active\n"
                    "• Unified study memory enabled"
                ),
                metadata={"web_user_id": res}
            )
        return ServiceResult(
            success=False,
            text=f"❌ Linking failed: {res}\n\nPlease generate a fresh link code from Web Settings and try again.",
            error_code="LINK_FAILED"
        )

    def get_user_status(self, user_id: int) -> Dict[str, Any]:
        """Returns account quota and link state."""
        return get_user_image_quota(user_id)


telegram_service = TelegramService()
