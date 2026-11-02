"""
BrainyAi Intent Schema & Data Models
Defines the strongly typed structures for intent classification, multi-intent task ordering,
constraints parsing, and resolution telemetry.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional


class IntentConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TaskIntentItem:
    """An individual intent item within a single or multi-intent request."""
    intent_id: str
    name: str = ""
    action: str = ""
    topic: Optional[str] = None
    domain: Optional[str] = None
    desired_output: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    confidence: float = 1.0
    order: int = 1
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UserIntentRequest:
    """Inbound context for the intent resolver."""
    query: str
    messages: Optional[List[Dict[str, str]]] = None
    document_context: Optional[Dict[str, Any]] = None
    explicit_intent: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class IntentResolutionResult:
    """Complete, structured output of the Brainy Intent Understanding System."""
    primary_intent: str
    secondary_intents: List[str] = field(default_factory=list)
    ordered_tasks: List[TaskIntentItem] = field(default_factory=list)
    topic: Optional[str] = None
    domain: Optional[str] = None
    difficulty: Optional[str] = None
    desired_output: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    context_required: bool = False
    context_reference_target: Optional[str] = None
    confidence: float = 0.95
    confidence_level: str = IntentConfidenceLevel.HIGH.value
    reason_codes: List[str] = field(default_factory=list)
    target_language: str = "en"
    workflow: str = "educational"
    prompt_id: str = "brainy_comprehensive"
    prompt_file: str = "brainy_prompt.txt"
    search_required: bool = False
    search_providers: List[str] = field(default_factory=list)
    is_fast_path: bool = False
    clarification_prompt: Optional[str] = None
    resolver_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["ordered_tasks"] = [t.to_dict() if isinstance(t, TaskIntentItem) else t for t in self.ordered_tasks]
        return res

    def to_telemetry(self) -> Dict[str, Any]:
        """Privacy-preserving telemetry summary (no raw user message)."""
        return {
            "primary_intent": self.primary_intent,
            "secondary_intents": self.secondary_intents,
            "topic": self.topic,
            "domain": self.domain,
            "difficulty": self.difficulty,
            "constraints": self.constraints,
            "required_tools": self.required_tools,
            "confidence": round(self.confidence, 4),
            "confidence_level": self.confidence_level,
            "reason_codes": self.reason_codes,
            "target_language": self.target_language,
            "workflow": self.workflow,
            "prompt_id": self.prompt_id,
            "search_required": self.search_required,
            "is_fast_path": self.is_fast_path,
            "context_required": self.context_required,
            "context_reference_target": self.context_reference_target,
            "resolver_latency_ms": round(self.resolver_latency_ms, 3)
        }
