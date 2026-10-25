"""
BrainyAi PDF Study Studio - Reusable Document Chunking & Multi-Stage Processing Layer
Splits documents into bounded, page-aware chunks preserving headings, mathematical formulas,
definitions, and exact page citations. Eliminates arbitrary hardcoded truncations.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import math


@dataclass
class DocumentChunk:
    chunk_index: int
    start_page: int
    end_page: int
    text: str
    token_count: int
    headings: List[str] = field(default_factory=list)


def chunk_document_pages(
    pages: List[Dict[str, Any]],
    target_tokens_per_chunk: int = 3500,
    overlap_pages: int = 1
) -> List[DocumentChunk]:
    """
    Groups extracted document pages into coherent, bounded chunks.
    Preserves exact page numbering [Page X] for academic citations.
    """
    if not pages:
        return []

    chunks: List[DocumentChunk] = []
    current_pages: List[Dict[str, Any]] = []
    current_tokens = 0
    chunk_idx = 0

    i = 0
    while i < len(pages):
        page = pages[i]
        page_num = page.get("page_number", i + 1)
        page_text = page.get("text_content", "").strip()
        page_tokens = page.get("token_count", max(1, int(len(page_text.split()) * 1.3))) if page_text else 0

        # If adding this page exceeds target and we already have at least 1 page
        if current_tokens + page_tokens > target_tokens_per_chunk and current_pages:
            # Build current chunk
            start_p = current_pages[0]["page_number"]
            end_p = current_pages[-1]["page_number"]
            chunk_text = "\n\n".join(
                f"--- [Page {p['page_number']}] ---\n{p.get('text_content', '').strip()}"
                for p in current_pages if p.get("text_content", "").strip()
            )
            all_headings = []
            for p in current_pages:
                for h in p.get("headings", []):
                    if h not in all_headings:
                        all_headings.append(h)

            chunks.append(DocumentChunk(
                chunk_index=chunk_idx,
                start_page=start_p,
                end_page=end_p,
                text=chunk_text,
                token_count=current_tokens,
                headings=all_headings
            ))
            chunk_idx += 1

            # Handle overlap
            if overlap_pages > 0 and len(current_pages) > overlap_pages:
                current_pages = current_pages[-overlap_pages:]
                current_tokens = sum(
                    p.get("token_count", max(1, int(len(p.get("text_content", "").split()) * 1.3)))
                    for p in current_pages
                )
            else:
                current_pages = []
                current_tokens = 0

        current_pages.append(page)
        current_tokens += page_tokens
        i += 1

    # Remaining pages
    if current_pages:
        start_p = current_pages[0]["page_number"]
        end_p = current_pages[-1]["page_number"]
        chunk_text = "\n\n".join(
            f"--- [Page {p['page_number']}] ---\n{p.get('text_content', '').strip()}"
            for p in current_pages if p.get("text_content", "").strip()
        )
        all_headings = []
        for p in current_pages:
            for h in p.get("headings", []):
                if h not in all_headings:
                    all_headings.append(h)

        chunks.append(DocumentChunk(
            chunk_index=chunk_idx,
            start_page=start_p,
            end_page=end_p,
            text=chunk_text,
            token_count=current_tokens,
            headings=all_headings
        ))

    return chunks


def sample_pages_evenly(
    pages: List[Dict[str, Any]],
    max_pages: int = 25
) -> List[Dict[str, Any]]:
    """
    Uniformly samples pages across the entire document so quizzes and flashcards
    represent beginning, middle, and end topics rather than arbitrarily cutting off after page N.
    """
    if len(pages) <= max_pages:
        return pages

    # Calculate step to pick evenly spaced pages
    total = len(pages)
    indices = [int(round(i * (total - 1) / (max_pages - 1))) for i in range(max_pages)]
    indices = sorted(list(set(indices)))
    return [pages[idx] for idx in indices]
