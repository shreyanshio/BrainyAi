"""
BrainyAi PDF Study Studio - Local OCR Processing Module
Handles local optical character recognition for scanned/image-only PDF pages using
pytesseract / Tesseract binary. Fully local, zero external AI API calls.
"""

import os
import io
import logging
from typing import Tuple, Optional

logger = logging.getLogger("pdf_ocr")

# Optional pytesseract import
try:
    import pytesseract
    from PIL import Image
    _PYTESSERACT_AVAILABLE = True
except ImportError:
    pytesseract = None
    Image = None
    _PYTESSERACT_AVAILABLE = False

# Configurable Tesseract path and OCR language via environment
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")
OCR_DEFAULT_LANG = os.getenv("OCR_LANG", "eng")
OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() in ("true", "1", "yes")

if _PYTESSERACT_AVAILABLE and TESSERACT_CMD and pytesseract:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def is_ocr_available() -> bool:
    """
    Checks if local OCR (pytesseract + accessible tesseract binary) is available and enabled.
    """
    if not OCR_ENABLED or not _PYTESSERACT_AVAILABLE or pytesseract is None:
        return False

    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception as e:
        logger.debug("Local tesseract binary not available: %s", e)
        return False


def ocr_page_image(
    image_bytes: bytes,
    page_number: int,
    lang: Optional[str] = None
) -> Tuple[str, str, str]:
    """
    Performs local OCR on a rendered page image.
    Returns:
        (text, extraction_method, extraction_status)
        method: "local_ocr"
        status: "success" | "ocr_unavailable" | "empty" | "failed"
    """
    if not image_bytes:
        return "", "local_ocr", "empty"

    if not is_ocr_available():
        logger.info(
            "Local OCR unavailable or disabled; page %d marked as scanned without local OCR",
            page_number
        )
        return "", "local_ocr", "ocr_unavailable"

    ocr_lang = lang or OCR_DEFAULT_LANG
    try:
        img = Image.open(io.BytesIO(image_bytes))
        raw_text = pytesseract.image_to_string(img, lang=ocr_lang)
        cleaned = "\n".join(line.strip() for line in raw_text.splitlines() if line.strip())
        if cleaned:
            return cleaned, "local_ocr", "success"
        else:
            return "", "local_ocr", "empty"
    except Exception as e:
        logger.warning("Local OCR failed on page %d: %s", page_number, e)
        return "", "local_ocr", "failed"
