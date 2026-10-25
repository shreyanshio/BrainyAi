"""
BrainyAi PDF Study Studio - Page-Aware Document Extractor
Extracts text page-by-page locally using PyMuPDF (fitz), preserving accurate page numbering,
structural headings, token counts, and delegating scanned pages to local OCR fallback.
Zero AI API calls are made during text extraction.
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

from pdf_studio.ocr import ocr_page_image, is_ocr_available

logger = logging.getLogger("pdf_extractor")


@dataclass
class PageExtraction:
    page_number: int  # 1-based index
    text: str
    token_count: int
    has_images: bool = False
    headings: List[str] = field(default_factory=list)
    is_scanned: bool = False
    extraction_method: str = "native_text"  # native_text | local_ocr | empty | failed
    extraction_status: str = "success"      # success | ocr_fallback | ocr_unavailable | empty | failed
    image_bytes: Optional[bytes] = None
    error_message: Optional[str] = None


def extract_pdf_pages(
    pdf_bytes: bytes,
    max_pages: Optional[int] = None,
    perform_ocr_fallback: bool = True
) -> List[PageExtraction]:
    """
    Extracts text page by page from PDF bytes using PyMuPDF.
    Preserves exact 1-based page numbering for academic citation.
    Uses local OCR only for scanned/image pages when configured.
    Never calls external AI APIs.
    """
    if not fitz:
        raise RuntimeError("PyMuPDF is not installed. Please install pymupdf.")

    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("Invalid PDF file: Missing %PDF- file header signature.")

    results: List[PageExtraction] = []
    doc = None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        if doc.is_encrypted:
            raise ValueError("Encrypted or password-protected PDF files cannot be processed.")

        total_pages = len(doc)
        if total_pages == 0:
            raise ValueError("PDF file contains zero pages.")

        pages_to_process = min(total_pages, max_pages) if max_pages and max_pages > 0 else total_pages

        for idx in range(pages_to_process):
            page_num = idx + 1
            page = doc[idx]

            try:
                # 1. Extract structural text blocks (preserving reading order and paragraph boundaries)
                text_blocks = []
                headings: List[str] = []

                page_dict = page.get_text("dict")
                blocks = page_dict.get("blocks", [])

                for b in blocks:
                    if b.get("type") == 0:  # text block
                        block_lines = []
                        for line in b.get("lines", []):
                            line_spans = []
                            for span in line.get("spans", []):
                                span_text = span.get("text", "")
                                font_size = span.get("size", 10.0)
                                line_spans.append(span_text)

                                # Heading heuristic: larger font size and concise text
                                clean_span = span_text.strip()
                                if font_size >= 13.0 and 2 <= len(clean_span.split()) <= 16:
                                    if clean_span not in headings:
                                        headings.append(clean_span)

                            line_str = "".join(line_spans).strip()
                            if line_str:
                                block_lines.append(line_str)

                        if block_lines:
                            text_blocks.append("\n".join(block_lines))

                clean_text = "\n\n".join(text_blocks).strip()

                # If dict extraction yielded empty string, try plain text extraction
                if not clean_text:
                    raw_text = page.get_text("text") or ""
                    clean_text = "\n".join(line.strip() for line in raw_text.splitlines() if line.strip())

                # 2. Check for images
                image_list = page.get_images()
                has_images = len(image_list) > 0

                # 3. Detect scanned / image-only page
                # If very little selectable text and images are present, or completely blank with drawings/images
                is_scanned = (len(clean_text) < 50 and has_images)
                rendered_image = None
                method = "native_text"
                status = "success" if clean_text else "empty"

                if is_scanned:
                    try:
                        pix = page.get_pixmap(dpi=150)
                        rendered_image = pix.tobytes("png")
                    except Exception as ie:
                        logger.warning("Could not render page %d to image: %s", page_num, ie)

                    if perform_ocr_fallback and rendered_image:
                        ocr_text, ocr_method, ocr_status = ocr_page_image(rendered_image, page_num)
                        method = ocr_method
                        if ocr_status == "success" and ocr_text:
                            clean_text = ocr_text
                            status = "ocr_fallback"
                        elif ocr_status == "ocr_unavailable":
                            status = "ocr_unavailable"
                        else:
                            status = ocr_status
                    else:
                        method = "local_ocr"
                        status = "ocr_unavailable"

                token_count = max(1, int(len(clean_text.split()) * 1.3)) if clean_text else 0

                results.append(PageExtraction(
                    page_number=page_num,
                    text=clean_text,
                    token_count=token_count,
                    has_images=has_images,
                    headings=headings,
                    is_scanned=is_scanned,
                    extraction_method=method,
                    extraction_status=status,
                    image_bytes=rendered_image
                ))

            except Exception as page_err:
                logger.error("Error extracting page %d: %s", page_num, page_err)
                results.append(PageExtraction(
                    page_number=page_num,
                    text="",
                    token_count=0,
                    has_images=False,
                    headings=[],
                    is_scanned=False,
                    extraction_method="failed",
                    extraction_status="failed",
                    error_message=str(page_err)
                ))

        return results
    finally:
        if doc:
            doc.close()
