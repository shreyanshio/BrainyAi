"""
BrainyAi Intelligent Multi-Provider Routing System
"""

from ai_routing.tasks import TaskType, ResponseDepth, classify_task
from ai_routing.registry import registry, ModelSpec
from ai_routing.policy import get_routing_candidates
from ai_routing.telemetry import global_telemetry, TelemetryRecord
from ai_routing.router import router, AIRouter, RouterResponse

__all__ = [
    "TaskType",
    "ResponseDepth",
    "classify_task",
    "registry",
    "ModelSpec",
    "get_routing_candidates",
    "global_telemetry",
    "TelemetryRecord",
    "router",
    "AIRouter",
    "RouterResponse",
]
