"""
BrainyAi Search Query Planner
Transforms conversational user queries into focused, high-precision search keywords.
Decomposes comparative multi-subject requests into up to 3 targeted subqueries
without search loops or duplicate API calls.
"""

import re
from typing import List, Optional

_FILLER_WORDS = re.compile(
    r"\b(?:"
    r"please|can\s+you|could\s+you|tell\s+me|i\s+want\s+to\s+know|find\s+out|search\s+for|search\s+the\s+web\s+for"
    r"|look\s+up|give\s+me|what\s+is|what\s+are|explain\s+to\s+me|browse\s+internet|google|hey\s+brainy"
    r")\b",
    re.IGNORECASE
)


def plan_search_queries(user_text: str, max_queries: int = 3) -> List[str]:
    """
    Formulates 1 to 3 targeted search queries based on the user's request.
    """
    clean_text = (user_text or "").strip()
    if not clean_text:
        return []

    # 1. Comparative queries (e.g. "Compare X, Y and Z for ...")
    comp_match = re.search(
        r"\b(?:compare|comparison\s+between|differences?\s+between)\s+([^.]+)",
        clean_text,
        re.IGNORECASE
    )
    if comp_match:
        target = comp_match.group(1).strip()
        # Look for "X, Y and Z" or "X vs Y"
        items = re.split(r",\s*|\s+and\s+|\s+vs\.?\s+", target, flags=re.IGNORECASE)
        items = [i.strip() for i in items if i.strip() and len(i.strip().split()) <= 4]
        if len(items) >= 2:
            queries = []
            for item in items[:max_queries]:
                # Clean filler from item
                cleaned_item = _FILLER_WORDS.sub("", item).strip()
                queries.append(f"{cleaned_item} official capabilities pricing")
            if queries:
                return queries

    # 2. Website/Company Legitimacy Verification (e.g. "Is this website legitimate: example.com")
    url_match = re.search(r"https?://([a-zA-Z0-9.-]+)", clean_text)
    if url_match:
        domain = url_match.group(1)
        return [f"{domain} legitimate safe reviews scam", f"{domain} official website"]

    site_match = re.search(r"\b([a-zA-Z0-9-]+\.(?:com|org|net|io|in|ai|co))\b", clean_text, re.IGNORECASE)
    if site_match:
        domain = site_match.group(1)
        return [f"{domain} reviews scam legitimate", f"{domain} official company"]

    # 3. Official Documentation / Error checks (e.g. "Check the latest official Python documentation for this error")
    if "documentation" in clean_text.lower() or "doc" in clean_text.lower():
        # Extract tech and error if present
        tech_match = re.search(r"\b(python|javascript|typescript|fastapi|react|next\.?js|django|flask|rust|go|gemini|groq)\b", clean_text, re.IGNORECASE)
        tech = tech_match.group(1) if tech_match else ""
        remainder = _FILLER_WORDS.sub("", clean_text)
        clean_query = f"{tech} official documentation {remainder}".strip()
        clean_query = re.sub(r"\s+", " ", clean_query)
        return [clean_query[:100]]

    # 4. Standard targeted search query: strip conversational fluff
    distilled = _FILLER_WORDS.sub("", clean_text).strip()
    distilled = re.sub(r"^[!?,.\s]+|[!?,.\s]+$", "", distilled)
    distilled = re.sub(r"\s+", " ", distilled)

    if not distilled:
        distilled = clean_text

    return [distilled[:120]]
