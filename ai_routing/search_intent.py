"""
BrainyAi Search Intent Detector
Deterministic, multi-pattern, context-aware engine that determines whether
a user's request strictly requires real-time web research via Tavily and DuckDuckGo.
Prevents hallucinated answers for time-sensitive facts while protecting token
budget on stable academic concepts, basic math, coding, and casual conversation.
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class SearchIntentResult:
    search_required: bool
    intent_category: str  # "explicit_search", "time_sensitive", "verification", "complex_research", "none"
    reason: str
    confidence: float
    trigger_match: Optional[str] = None


# ── POSITIVE SEARCH TRIGGERS ──

_EXPLICIT_SEARCH_PATTERN = re.compile(
    r"\b(?:"
    r"(?<!binary\s)(?<!linear\s)(?<!tree\s)(?<!graph\s)search(?:\s+the\s+web|\s+online|\s+google|\s+internet|\s+and\s+explain)"
    r"|find(?:\s+the)?\s+(?:latest|current|recent|newest)"
    r"|look(?:\s+this)?\s+up(?:\s+online|\s+on\s+the\s+web)?"
    r"|browse\s+the\s+(?:internet|web)"
    r"|research\s+this(?:\s+topic)?"
    r"|verify\s+(?:whether|if|this)"
    r"|fact[- ]check"
    r"|find\s+official\s+doc(?:umentation)?"
    r"|find\s+current\s+prices?"
    r"|compare\s+(?:the\s+latest|available\s+options|current)"
    r"|find\s+recent\s+developments?"
    r"|give\s+me\s+sources?"
    r")\b",
    re.IGNORECASE
)

_TIME_SENSITIVE_PATTERN = re.compile(
    r"\b(?:"
    r"latest(?:\s+(?:news|updates?|changes?|features?|release|version|docs?|documentation|events?|research|models?|api))"
    r"|today(?:'s)?\s+(?:news|events?|weather|headlines?)"
    r"|current(?:ly)?\s+(?:prices?|availability|leadership|ceo|minister|president|laws?|regulations?|versions?|models?|schedule|events?|cutoffs?|dates?)"
    r"|recent(?:\s+(?:scientific\s+developments?|research|advancements?|announcements?|papers?))"
    r"|admission\s+dates?|application\s+deadlines?|exam\s+(?:dates?|schedule|notifications?|cutoffs?)"
    r"|recently\s+announced"
    r"|whats?\s+new\s+in\s+[a-z0-9_.\-]+"
    r")\b",
    re.IGNORECASE
)

_VERIFICATION_PATTERN = re.compile(
    r"\b(?:"
    r"is\s+this\s+(?:website|site|url|company|service|platform|app|product|announcement|information)\s+(?:legitimate|real|authentic|fake|scam|genuine|safe)"
    r"|is\s+this\s+api\s+(?:free|deprecated|active|open\s+source)"
    r"|does\s+this\s+doc(?:umentation)?\s+still\s+apply"
    r"|check\s+whether\s+this\s+(?:website|domain|company|info)\s+is"
    r"|can\s+i\s+trust\s+(?:this\s+site|https?://\S+)"
    r")\b",
    re.IGNORECASE
)

_COMPLEX_RESEARCH_PATTERN = re.compile(
    r"\b(?:"
    r"research\s+report\s+on"
    r"|multiple[- ]source\s+comparison"
    r"|competitor\s+analysis"
    r"|market\s+research\s+(?:on|for)"
    r"|recent\s+academic\s+developments?"
    r"|detailed\s+comparison\s+of\s+currently\s+available"
    r"|compare\s+(?:the\s+latest|current)\s+(?:ai\s+coding\s+models|llms?|tools?|services?|apis?)"
    r")\b",
    re.IGNORECASE
)

_CODING_DOC_SEARCH_PATTERN = re.compile(
    r"\b(?:"
    r"check\s+(?:the\s+)?latest\s+official\s+(?:python|javascript|typescript|fastapi|react|next\.?js|django|flask|rust|go)\s+doc(?:umentation)?"
    r"|check\s+latest\s+doc(?:s|umentation)?\s+for"
    r"|official\s+doc(?:s|umentation)?\s+for\s+this\s+error"
    r")\b",
    re.IGNORECASE
)

# ── NEGATIVE FILTERS (Never trigger search) ──

_GREETINGS_PATTERN = re.compile(
    r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening)|namaste|hola|sup|yo|brainy)\b[!.\s]*$",
    re.IGNORECASE
)

_STABLE_ACADEMIC_PATTERN = re.compile(
    r"^(?:explain(?:\s+the)?|what\s+is(?:\s+a|\s+an|\s+the)?|define(?:\s+a|\s+an|\s+the)?|how\s+does(?:\s+a|\s+an|\s+the)?)\s+(?:"
    r"photosynthesis|binary\s+search(?:\s+tree)?|gravity|mitosis|meiosis|dna\s+replication"
    r"|newton(?:'s)?\s+(?:first|second|third|laws?)|pythagoras|thermodynamics|polymorphism"
    r"|inheritance(?:\s+in\s+[a-z]+)?|encapsulation|recursion|sorting\s+algorithms?|compiler"
    r"|operating\s+system|turing\s+machine|relativity|quantum\s+entanglement|coulomb(?:'s)?\s+law"
    r"|ohm(?:'s)?\s+law|kirchhoff(?:'s)?\s+law|bubble\s+sort|merge\s+sort|quick\s+sort"
    r")\b[?.\s]*$",
    re.IGNORECASE
)

_BASIC_MATH_PATTERN = re.compile(
    r"^(?:solve|calculate|evaluate|find\s+the\s+derivative\s+of|integrate|what\s+is)\s+[\d\s+\-*/^=()xXyYzZsqrt\\]+[?.\s]*$",
    re.IGNORECASE
)

_CASUAL_CHAT_PATTERN = re.compile(
    r"^(?:how\s+are\s+you|who\s+are\s+you|who\s+made\s+you|what\s+can\s+you\s+do|tell\s+me\s+a\s+joke|make\s+me\s+laugh|roast\s+me)\b[?.\s]*$",
    re.IGNORECASE
)


def detect_search_intent(
    text: str,
    context_turns: Optional[List[Dict[str, str]]] = None,
    document_present: bool = False
) -> SearchIntentResult:
    """
    Evaluates whether the user's input strictly requires web search via Tavily and DuckDuckGo.
    """
    clean_text = (text or "").strip()
    if not clean_text:
        return SearchIntentResult(False, "none", "Empty request", 1.0)

    # 1. Negative Filter: Casual Greetings
    if _GREETINGS_PATTERN.match(clean_text):
        return SearchIntentResult(False, "none", "Greeting does not require external search", 1.0)

    # 2. Negative Filter: Casual Smalltalk
    if _CASUAL_CHAT_PATTERN.match(clean_text):
        return SearchIntentResult(False, "none", "Casual conversational banter does not require search", 1.0)

    # 3. Negative Filter: Basic Mathematics
    if _BASIC_MATH_PATTERN.match(clean_text) and not any(w in clean_text.lower() for w in ["latest", "current", "news", "price"]):
        return SearchIntentResult(False, "none", "Mathematical computation is solved directly", 1.0)

    # 4. Negative Filter: Document-scoped queries (unless outside verification is asked)
    if document_present and not any(w in clean_text.lower() for w in ["latest", "google", "web", "internet", "current", "verify", "outside"]):
        return SearchIntentResult(False, "none", "PDF document context is available; local extraction preferred", 0.95)

    # 5. Negative Filter: Stable Academic Concepts (e.g., "Explain photosynthesis", "What is a binary search tree?", "Explain inheritance in Java")
    if _STABLE_ACADEMIC_PATTERN.match(clean_text):
        return SearchIntentResult(False, "none", "Stable academic / STEM concept answered from verified knowledge base", 0.98)

    # ── POSITIVE TRIGGERS ──

    # Check for Coding + Web Search
    match_code_search = _CODING_DOC_SEARCH_PATTERN.search(clean_text)
    if match_code_search:
        return SearchIntentResult(
            search_required=True,
            intent_category="explicit_search",
            reason="User explicitly requested current official programming documentation",
            confidence=0.99,
            trigger_match=match_code_search.group(0)
        )

    # Check for Explicit Search
    match_explicit = _EXPLICIT_SEARCH_PATTERN.search(clean_text)
    if match_explicit:
        return SearchIntentResult(
            search_required=True,
            intent_category="explicit_search",
            reason="User issued explicit search directive",
            confidence=0.99,
            trigger_match=match_explicit.group(0)
        )

    # Check for Verification & Legitimacy
    match_verif = _VERIFICATION_PATTERN.search(clean_text)
    if match_verif:
        return SearchIntentResult(
            search_required=True,
            intent_category="verification",
            reason="User asked for external factual or website verification",
            confidence=0.98,
            trigger_match=match_verif.group(0)
        )

    # Check for Time-Sensitive Information
    match_time = _TIME_SENSITIVE_PATTERN.search(clean_text)
    if match_time:
        return SearchIntentResult(
            search_required=True,
            intent_category="time_sensitive",
            reason="Request involves current, fast-moving, or time-sensitive external data",
            confidence=0.95,
            trigger_match=match_time.group(0)
        )

    # Check for Complex Research
    match_research = _COMPLEX_RESEARCH_PATTERN.search(clean_text)
    if match_research:
        return SearchIntentResult(
            search_required=True,
            intent_category="complex_research",
            reason="User requested multi-source research report or comparative analysis",
            confidence=0.95,
            trigger_match=match_research.group(0)
        )

    # Contextual Follow-up checking:
    # If prior turn involved web search and user says "explain the second result",
    # that is a follow-up that relies on prior search context.
    if context_turns and len(context_turns) >= 2:
        prev_user = context_turns[-2].get("content", "")
        if re.search(r"\b(?:explain|tell me more about|expand on)\s+(?:the\s+)?(?:first|second|third|fourth|1st|2nd|3rd|4th|last)\s+result\b", clean_text, re.IGNORECASE):
            return SearchIntentResult(
                search_required=False,  # Reuses prior evidence rather than re-searching
                intent_category="followup_reuse",
                reason="User is referencing search results from the previous turn",
                confidence=0.95
            )

    return SearchIntentResult(False, "none", "Defaulted to internal knowledge base for stable content", 0.8)
