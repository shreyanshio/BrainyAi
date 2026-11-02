"""
Brainy Conversation Memory & Topic State Engine
Maintains structured topic state, rolling conversation summaries,
topic boundary detection, exact reference preservation, and dynamic context assembly.
"""

import re
import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class TopicState:
    conversation_id: str
    current_topic: str = "general"
    current_task: str = "learning"
    user_goal: str = ""
    important_facts: List[str] = field(default_factory=list)
    previous_decisions: List[str] = field(default_factory=list)
    user_constraints: List[str] = field(default_factory=list)
    important_references: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    last_summary_message_id: Optional[int] = None
    summary_version: int = 1
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TopicState":
        if not isinstance(data, dict):
            return cls(conversation_id="default")
        return cls(
            conversation_id=str(data.get("conversation_id") or "default"),
            current_topic=str(data.get("current_topic") or "general"),
            current_task=str(data.get("current_task") or "learning"),
            user_goal=str(data.get("user_goal") or ""),
            important_facts=list(data.get("important_facts") or []),
            previous_decisions=list(data.get("previous_decisions") or []),
            user_constraints=list(data.get("user_constraints") or []),
            important_references=list(data.get("important_references") or []),
            open_questions=list(data.get("open_questions") or []),
            last_summary_message_id=data.get("last_summary_message_id"),
            summary_version=int(data.get("summary_version") or 1),
            updated_at=data.get("updated_at"),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "TopicState":
        try:
            return cls.from_dict(json.loads(json_str))
        except Exception:
            return cls(conversation_id="default")

    def format_context_block(self) -> str:
        """Renders compact structured summary for prompt injection."""
        lines = [f"[TOPIC STATE: {self.current_topic}]"]
        if self.user_goal:
            lines.append(f"Goal: {self.user_goal}")
        if self.important_facts:
            lines.append("Facts: " + "; ".join(self.important_facts[:5]))
        if self.user_constraints:
            lines.append("Constraints: " + "; ".join(self.user_constraints[:4]))
        if self.previous_decisions:
            lines.append("Decisions: " + "; ".join(self.previous_decisions[:4]))
        if self.important_references:
            lines.append("Exact identifiers: " + ", ".join(self.important_references[:8]))
        if self.open_questions:
            lines.append("Open items: " + "; ".join(self.open_questions[:3]))
        return "\n".join(lines)


# Regex patterns for preserving exact technical identifiers that must NEVER be lost
_IDENTIFIER_PATTERN = re.compile(
    r"`([^`]+)`|"                                # Backticked code / terms
    r"\b([A-Za-z0-9_]+\.[A-Za-z0-9_]+)\b|"       # Dotted identifiers (e.g. math.sin, app.py)
    r"\b([A-Z][a-zA-Z0-9]{2,}\b)|"              # CamelCase classes (e.g. SessionManager)
    r"\b([a-z_][a-z0-9_]{3,}\(\))|"             # Function calls (e.g. get_user())
    r"(https?://[^\s\)]+)|"                      # URLs
    r"\b([A-Z_]{3,})\b"                          # ENUM / CONSTANT names
)


def extract_exact_identifiers(text: str) -> List[str]:
    """Extracts exact variable names, function calls, classes, endpoints, and constants."""
    if not text:
        return []
    matches = _IDENTIFIER_PATTERN.findall(text)
    identifiers = set()
    for groups in matches:
        for item in groups:
            clean = item.strip()
            if clean and len(clean) >= 3 and clean not in ("True", "False", "None", "HTTP", "JSON", "GET", "POST"):
                identifiers.add(clean)
    return sorted(list(identifiers))[:12]


# High-signal domain topic dictionaries for boundary detection
_DOMAIN_TAXONOMY = {
    "python": {"python", "def", "self", "django", "flask", "pydantic", "pip", "pytest", "fastapi"},
    "javascript": {"javascript", "typescript", "react", "nextjs", "node", "npm", "const", "props", "jsx"},
    "java": {"java", "jvm", "spring", "class", "interface", "maven", "gradle", "hibernate"},
    "cpp": {"cpp", "c++", "pointer", "malloc", "template", "vector", "destructor", "stl"},
    "database": {"sql", "postgres", "supabase", "database", "query", "select", "table", "index", "join"},
    "math": {"integral", "derivative", "matrix", "eigenvalue", "polynomial", "algebra", "theorem", "equation", "proof"},
    "physics": {"thermodynamics", "quantum", "velocity", "acceleration", "entropy", "friction", "photon", "gravity"},
    "chemistry": {"reaction", "molecule", "orbital", "acid", "base", "synthesis", "organic", "catalyst", "electron"},
    "biology": {"photosynthesis", "cell", "mitosis", "dna", "rna", "protein", "enzyme", "organism", "genetics"},
    "history": {"empire", "war", "treaty", "dynasty", "revolution", "century", "monarch", "civilization"},
    "economics": {"inflation", "gdp", "market", "monopoly", "fiscal", "currency", "supply", "demand", "interest"},
}


def infer_topic_domain(text: str) -> Optional[str]:
    """Infers the high-level subject domain from text keywords."""
    if not text:
        return None
    lower = text.lower()
    words = set(re.findall(r"\b[a-z]{3,}\b", lower))
    domain_scores: Dict[str, int] = {}
    for domain, kws in _DOMAIN_TAXONOMY.items():
        overlap = len(words.intersection(kws))
        if overlap > 0:
            domain_scores[domain] = overlap
    if domain_scores:
        return max(domain_scores, key=domain_scores.get)
    return None


def detect_topic_change(current_text: str, current_topic: str) -> bool:
    """
    Detects whether the user's latest query is an abrupt topic switch.
    Prevents injecting outdated topic summaries (e.g. Python class details into a Biology turn).
    """
    if not current_text or not current_topic or current_topic in ("general", "chat"):
        return False

    current_domain = infer_topic_domain(current_text)
    topic_domain = infer_topic_domain(current_topic) or current_topic.lower()

    if current_domain and topic_domain and current_domain != topic_domain:
        # Check if current_text mentions the old topic explicitly (cross-domain comparison)
        if topic_domain in current_text.lower():
            return False  # User is comparing or connecting both domains
        return True

    return False


def should_update_summary(
    unsummarized_count: int,
    topic_changed: bool = False,
    threshold: int = 10
) -> bool:
    """
    Threshold-based summary decision.
    Triggered when unsummarized turns reach threshold (default 10) or upon topic shift.
    Never invokes expensive summarization on every single turn.
    """
    if topic_changed:
        return True
    return unsummarized_count >= threshold


def assemble_dynamic_context(
    messages: List[Dict[str, str]],
    topic_state: Optional[TopicState] = None,
    user_preferences: Optional[Dict[str, Any]] = None,
    sliding_window_size: int = 10,
    current_topic_active: bool = True
) -> Tuple[List[Dict[str, str]], Optional[str]]:
    """
    Assembles a compact, high-signal conversational context.
    - Preserves 8-12 recent turns verbatim.
    - Injects structured topic summary only if topic is active and not bypassed by topic-change.
    - Injects user preferences when relevant.
    """
    recent_turns = messages[-sliding_window_size:] if len(messages) > sliding_window_size else list(messages)
    context_prefix_parts = []

    if user_preferences:
        pref_lines = [f"- {k}: {v}" for k, v in user_preferences.items() if v]
        if pref_lines:
            context_prefix_parts.append("Student preferences:\n" + "\n".join(pref_lines[:4]))

    if topic_state and current_topic_active and topic_state.current_topic != "general":
        topic_summary = topic_state.format_context_block()
        if topic_summary:
            context_prefix_parts.append(topic_summary)

    injected_context = "\n\n".join(context_prefix_parts) if context_prefix_parts else None
    return recent_turns, injected_context
