"""
BrainyAi PDF Study Studio - Document OCR Adapter
Deprecates external AI API calls in favor of local, deterministic OCR.
Guarantees zero AI API consumption during PDF text extraction.
"""

import logging
from typing import Optional
from pdf_studio.ocr import ocr_page_image, is_ocr_available

logger = logging.getLogger("gemini_doc")


def ocr_scanned_page(image_bytes: bytes, page_number: int) -> str:
    """
    Extracts text from a scanned page image locally without AI APIs.
    Delegates to local OCR (Tesseract / pytesseract) when available.
    """
    if not image_bytes:
        return ""

    text, method, status = ocr_page_image(image_bytes, page_number)
    if status == "success" and text:
        return text

    if status == "ocr_unavailable":
        return f"[Scanned page {page_number}: Image content present (local OCR not configured)]"

    return f"[Scanned page {page_number}: Image content present]"
