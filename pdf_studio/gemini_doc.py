"""
BrainyAi PDF Study Studio - Gemini Multimodal Document Understanding
Handles multimodal PDF understanding, scanned page OCR, and diagram comprehension.
"""

import base64
import logging
from typing import Dict, Any, List, Optional
from ai_routing.registry import registry
from ai_routing.router import router
from ai_routing.tasks import TaskType, ResponseDepth

logger = logging.getLogger("gemini_doc")

def ocr_scanned_page(image_bytes: bytes, page_number: int) -> str:
    """
    Uses Gemini multimodal vision to extract text, formulas, and diagrams from a scanned page image.
    """
    if not image_bytes:
        return ""

    rot = registry.get_rotator("gemini")
    if not rot or rot.key_count == 0:
        return "[Scanned page without extractable text]"

    b64_img = base64.b64encode(image_bytes).decode("utf-8")
    multimodal_parts = [{
        "inline_data": {
            "mime_type": "image/png",
            "data": b64_img
        }
    }]

    prompt = (
        f"Transcribe and clearly extract all text, formulas, mathematical notation, and diagrams "
        f"from this scanned page #{page_number}. Format formulas in clean LaTeX. Do not add conversational fluff."
    )

    try:
        resp = router.generate(
            prompt=prompt,
            task=TaskType.DOCUMENT_INGESTION,
            depth=ResponseDepth.FAST,
            max_tokens=1500,
            document_context={"multimodal_parts": multimodal_parts}
        )
        return resp.text.strip()
    except Exception as e:
        logger.warning("OCR for page %d failed (%s); continuing with plain metadata", page_number, e)
        return f"[Scanned page {page_number}: Image content present]"
