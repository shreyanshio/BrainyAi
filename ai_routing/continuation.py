"""
BrainyAi Automatic Response Continuation & Stitching Engine
Detects output-limit truncations across all AI providers (Groq, Gemini, SambaNova, OpenRouter, Cerebras),
seamlessly continues generation from the exact point of interruption, and deduplicates boundary overlaps.
"""

from typing import Optional

# Maximum follow-up continuation rounds to avoid infinite runaway loops
MAX_CONTINUATION_ROUNDS = 3

CONTINUATION_PROMPT = (
    "Continue generating the response directly and seamlessly from the exact character where you stopped. "
    "Do not repeat any text, introduction, or headings that were already output. "
    "Complete all remaining code, explanations, lists, or steps."
)


def is_length_truncated(finish_reason: Optional[str]) -> bool:
    """
    Standardizes length truncation detection across all providers:
    - Groq, SambaNova, OpenRouter, Cerebras: 'length'
    - Google Gemini: 'MAX_TOKENS'
    """
    if not finish_reason:
        return False
    fr = str(finish_reason).strip().lower()
    return fr in ("length", "max_tokens", "max_output_tokens")


def stitch_continuation(accumulated: str, continuation: str) -> str:
    """
    Stitches a follow-up continuation chunk onto the accumulated text with boundary deduplication.
    Prevents repeated lines, duplicate function declarations, or duplicated sentences.
    """
    if not accumulated:
        return continuation or ""
    if not continuation:
        return accumulated

    tail = accumulated[-300:]
    max_overlap = min(len(tail), len(continuation), 300)
    best_overlap = 0

    # Scan for longest overlapping substring at the boundary
    for l in range(max_overlap, 2, -1):
        if tail.endswith(continuation[:l]):
            best_overlap = l
            break

    continuation_clean = continuation[best_overlap:] if best_overlap > 0 else continuation
    return accumulated + continuation_clean


def deduplicate_stream_overlap(accumulated: str, first_chunk: str) -> str:
    """
    Deduplicates any repeated prefix on the very first token/chunk of a streaming continuation round.
    """
    if not accumulated or not first_chunk:
        return first_chunk or ""

    tail = accumulated[-300:]
    max_overlap = min(len(tail), len(first_chunk), 300)
    best_overlap = 0

    for l in range(max_overlap, 2, -1):
        if tail.endswith(first_chunk[:l]):
            best_overlap = l
            break

    if best_overlap > 0:
        return first_chunk[best_overlap:]
    return first_chunk
