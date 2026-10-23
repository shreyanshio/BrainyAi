"""
BrainyAi PDF Study Studio - Page-Aware Document Extractor
Extracts text page-by-page using PyMuPDF, preserving accurate page numbering,
structural headings, token counts, and identifying scanned pages for OCR fallback.
"""

import io
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

logger = logging.getLogger("pdf_extractor")

@dataclass
class PageExtraction:
    page_number: int  # 1-based index
    text: str
    token_count: int
    has_images: bool = False
    headings: List[str] = field(default_factory=list)
    is_scanned: bool = False
    image_bytes: Optional[bytes] = None

def extract_pdf_pages(pdf_bytes: bytes, max_pages: int = 100) -> List[PageExtraction]:
    """
    Extracts text page by page from PDF bytes using PyMuPDF.
    Preserves exact 1-based page numbering for academic citation.
    """
    if not fitz:
        raise RuntimeError("PyMuPDF is not installed. Please install pymupdf.")

    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("Invalid PDF file: Missing %PDF- file header signature.")

    results: List[PageExtraction] = []
    doc = None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        if total_pages == 0:
            raise ValueError("PDF file contains zero pages.")

        pages_to_process = min(total_pages, max_pages)

        for idx in range(pages_to_process):
            page_num = idx + 1
            page = doc[idx]

            # 1. Extract plain text
            raw_text = page.get_text("text") or ""
            clean_text = "\n".join(line.strip() for line in raw_text.splitlines() if line.strip())

            # 2. Check for images
            image_list = page.get_images()
            has_images = len(image_list) > 0

            # 3. Detect scanned / image-only page
            is_scanned = (len(clean_text) < 50 and has_images)
            rendered_image = None
            if is_scanned:
                try:
                    pix = page.get_pixmap(dpi=150)
                    rendered_image = pix.tobytes("png")
                except Exception as ie:
                    logger.warning("Could not render scanned page %d: %s", page_num, ie)

            # 4. Extract structural headings (span font-size analysis)
            headings = []
            try:
                blocks = page.get_text("dict").get("blocks", [])
                for b in blocks:
                    if b.get("type") == 0:  # text block
                        for line in b.get("lines", []):
                            for span in line.get("spans", []):
                                font_size = span.get("size", 10.0)
                                span_text = span.get("text", "").strip()
                                # Headings typically have larger font size and concise text
                                if font_size >= 13.0 and 3 <= len(span_text.split()) <= 15:
                                    if span_text not in headings:
                                        headings.append(span_text)
            except Exception:
                pass

            token_count = max(1, int(len(clean_text.split()) * 1.3))

            results.append(PageExtraction(
                page_number=page_num,
                text=clean_text,
                token_count=token_count,
                has_images=has_images,
                headings=headings,
                is_scanned=is_scanned,
                image_bytes=rendered_image
            ))

        return results
    finally:
        if doc:
            doc.close()
