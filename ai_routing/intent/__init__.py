"""
BrainyAi Dedicated Intent Knowledge Base & User Request Understanding System
"""
from ai_routing.intent.intent_schema import (
    IntentResolutionResult,
    UserIntentRequest,
    TaskIntentItem,
    IntentConfidenceLevel
)
from ai_routing.intent.intent_resolver import intent_resolver, IntentResolver

__all__ = [
    "IntentResolutionResult",
    "UserIntentRequest",
    "TaskIntentItem",
    "IntentConfidenceLevel",
    "intent_resolver",
    "IntentResolver"
]
