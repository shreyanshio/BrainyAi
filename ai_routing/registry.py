"""
BrainyAi Central Provider & Model Registry
Manages verified model identifiers, key pools (with 8-15 keys rotation),
provider capabilities, live model discovery, zero-budget cost policies, timeouts, and token limits.
"""

import os
import time
import logging
import threading
import requests
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("model_registry")


class CostCategory(str, Enum):
    ZERO_PRICE = "ZERO_PRICE"  # Confirmed 0 USD (e.g. OpenRouter :free models)
    FREE_TIER  = "FREE_TIER"   # Covered by provider developer free tier (Groq, Gemini, SambaNova, Cerebras)
    PAID       = "PAID"        # Incurs billing / paid credits
    UNKNOWN    = "UNKNOWN"     # Unverified pricing


@dataclass
class ModelSpec:
    model_id: str
    provider: str
    display_name: str = ""
    cost_category: CostCategory = CostCategory.FREE_TIER
    input_price_per_m: float = 0.0
    output_price_per_m: float = 0.0
    supports_streaming: bool = True
    supports_structured_json: bool = True
    supports_tool_calling: bool = False
    supports_vision: bool = False
    supported_modalities: List[str] = field(default_factory=lambda: ["text"])
    supported_thinking_levels: List[str] = field(default_factory=list)
    lifecycle: str = "stable"  # "stable", "preview", "experimental", "legacy"
    is_paid_only: bool = False
    max_context_tokens: int = 128000
    max_output_tokens: int = 4096
    timeout_sec: float = 25.0
    fallback_priority: int = 1
    availability_status: str = "available"  # "available", "unavailable", "quarantined"
    last_verified_ts: float = field(default_factory=time.time)

    def __post_init__(self):
        if self.supports_vision and "image" not in self.supported_modalities:
            self.supported_modalities.append("image")
        elif "image" in self.supported_modalities and not self.supports_vision:
            self.supports_vision = True


def collect_key_pool(prefix: str, count: int = 15) -> List[str]:
    """Collects API keys from singular, plural, and numbered environment variables."""
    keys = []
    # 1. Singular
    single = os.getenv(prefix)
    if single and single.strip():
        for k in single.split(","):
            clean = k.strip()
            if clean and clean not in keys:
                keys.append(clean)
    # 2. Plural
    plural = os.getenv(f"{prefix}S")
    if plural and plural.strip():
        for k in plural.split(","):
            clean = k.strip()
            if clean and clean not in keys:
                keys.append(clean)
    # 3. Numbered (PREFIX_1 .. PREFIX_15)
    for i in range(1, count + 1):
        k = os.getenv(f"{prefix}_{i}")
        if k and k.strip():
            clean = k.strip()
            if clean not in keys:
                keys.append(clean)
    return keys


class ProviderKeyRotator:
    """Thread-safe round-robin key rotator with quarantine tracking."""
    def __init__(self, provider: str, keys: List[str]):
        self.provider = provider
        self.keys = list(keys)
        self._index = 0
        self._lock = threading.Lock()
        self._quarantined: Dict[str, float] = {}

    def get_key(self) -> str:
        with self._lock:
            now = time.time()
            active_keys = [k for k in self.keys if now > self._quarantined.get(k, 0)]
            if not active_keys:
                return ""
            key = active_keys[self._index % len(active_keys)]
            self._index = (self._index + 1) % len(active_keys)
            return key

    def get_next_key(self) -> Optional[str]:
        k = self.get_key()
        return k if k else None

    def quarantine_key(self, key: str, cooldown_seconds: float = 60.0):
        with self._lock:
            self._quarantined[key] = time.time() + cooldown_seconds

    @property
    def key_count(self) -> int:
        return len(self.keys)

    def reload(self, keys: List[str]):
        with self._lock:
            self.keys = list(keys)
            self._index = 0
            self._quarantined.clear()


class ProviderRegistry:
    def __init__(self):
        self._lock = threading.RLock()
        self._rotators: Dict[str, ProviderKeyRotator] = {}
        self._models: Dict[str, ModelSpec] = {}
        self._provider_switches: Dict[str, bool] = {}
        self._discovered_cache: Dict[str, Tuple[float, List[str]]] = {}  # provider -> (timestamp, model_ids)
        self.reload_configuration()

    def reload_configuration(self):
        with self._lock:
            # 1. Load keys for active supported providers
            self._rotators["groq"] = ProviderKeyRotator("groq", collect_key_pool("GROQ_API_KEY", 15))
            self._rotators["gemini"] = ProviderKeyRotator("gemini", collect_key_pool("GEMINI_API_KEY", 15))
            self._rotators["sambanova"] = ProviderKeyRotator("sambanova", collect_key_pool("SAMBANOVA_API_KEY", 15))
            self._rotators["cerebras"] = ProviderKeyRotator("cerebras", collect_key_pool("CEREBRAS_API_KEY", 15))
            self._rotators["openrouter"] = ProviderKeyRotator("openrouter", collect_key_pool("OPENROUTER_API_KEY", 15))
            self._rotators["tavily"] = ProviderKeyRotator("tavily", collect_key_pool("TAVILY_API_KEY", 15))

            # 2. Provider switches
            self._provider_switches = {
                "groq": os.getenv("ENABLE_GROQ", "true").lower() in ("true", "1", "yes"),
                "gemini": os.getenv("ENABLE_GEMINI", "true").lower() in ("true", "1", "yes"),
                "sambanova": os.getenv("ENABLE_SAMBANOVA", "true").lower() in ("true", "1", "yes"),
                "cerebras": os.getenv("ENABLE_CEREBRAS", "true").lower() in ("true", "1", "yes"),
                "openrouter": os.getenv("ENABLE_OPENROUTER", "true").lower() in ("true", "1", "yes"),
            }

            # 3. Cost policies
            self.strict_zero_budget = os.getenv("STRICT_ZERO_BUDGET", "true").lower() in ("true", "1", "yes")
            self.allow_paid_models = os.getenv("ALLOW_PAID_MODELS", "false").lower() in ("true", "1", "yes")

            # 4. Configurable model IDs
            self.groq_fast_model = (os.getenv("GROQ_MODEL_FAST") or "llama-3.1-8b-instant").strip()
            self.groq_balanced_model = (os.getenv("GROQ_MODEL_BALANCED") or "llama-3.3-70b-versatile").strip()
            self.gemini_primary_model = (os.getenv("GEMINI_PRIMARY_MODEL") or "gemini-3.8-flash").strip()
            self.gemini_code_model = (os.getenv("GEMINI_CODE_MODEL") or "gemini-3.8-flash").strip()
            self.gemini_vision_model = (os.getenv("GEMINI_VISION_MODEL") or "gemini-3.8-flash").strip()
            self.gemini_reasoning_model = (os.getenv("GEMINI_REASONING_MODEL") or "gemini-3.8-flash").strip()
            self.gemini_balanced_model = (os.getenv("GEMINI_BALANCED_MODEL") or "gemini-3.6-flash").strip()
            self.gemini_fast_model = (os.getenv("GEMINI_FAST_MODEL") or "gemini-3.5-flash-lite").strip()
            self.gemini_fallback_model = (os.getenv("GEMINI_FALLBACK_MODEL") or "gemini-3.6-flash").strip()
            self.gemini_flagship_model = (os.getenv("GEMINI_FLAGSHIP_MODEL") or "gemini-4-argon").strip()
            self.gemini_pdf_model = (os.getenv("GEMINI_PDF_MODEL") or "gemini-2.5-flash").strip()
            self.sambanova_reasoning_model = (os.getenv("SAMBANOVA_REASONING_MODEL") or "Meta-Llama-3.3-70B-Instruct").strip()
            self.sambanova_fast_model = (os.getenv("SAMBANOVA_FAST_MODEL") or "Meta-Llama-3.3-70B-Instruct").strip()
            self.openrouter_coding_model = (os.getenv("OPENROUTER_CODING_MODEL") or "cohere/north-mini-code:free").strip()
            self.openrouter_free_model = (os.getenv("OPENROUTER_FREE_MODEL") or "openrouter/free").strip()

            # 5. Populate verified Model Specifications
            self._models.clear()

            # Groq models
            self._register(ModelSpec("llama-3.1-8b-instant", "groq", "Llama 3.1 8B Instant", CostCategory.FREE_TIER, 0.05, 0.08, supports_streaming=True, supports_structured_json=True, max_output_tokens=4096, timeout_sec=15.0, lifecycle="stable"))
            self._register(ModelSpec("llama-3.3-70b-versatile", "groq", "Llama 3.3 70B Versatile", CostCategory.FREE_TIER, 0.59, 0.79, supports_streaming=True, supports_structured_json=True, max_output_tokens=8192, timeout_sec=25.0, lifecycle="stable"))
            self._register(ModelSpec("qwen/qwen3.8-27b", "groq", "Qwen 3.8 27B", CostCategory.FREE_TIER, 0.20, 0.60, supports_streaming=True, supports_structured_json=True, max_output_tokens=4096, timeout_sec=20.0, lifecycle="stable"))
            self._register(ModelSpec("openai/gpt-oss-120b", "groq", "GPT OSS 120B", CostCategory.FREE_TIER, 0.60, 1.20, supports_streaming=True, supports_structured_json=True, max_output_tokens=8192, timeout_sec=25.0, lifecycle="stable"))

            # Gemini models (Multimodal, Thinking & Reasoning Support)
            self._register(ModelSpec(
                "gemini-3.8-flash", "gemini", "Gemini 3.8 Flash", CostCategory.FREE_TIER, 0.75, 3.75,
                supports_streaming=True, supports_structured_json=True, supports_vision=True,
                supported_modalities=["text", "image", "audio", "video"],
                supported_thinking_levels=["low", "medium", "high"],
                lifecycle="stable", is_paid_only=False,
                max_context_tokens=1000000, max_output_tokens=8192, timeout_sec=35.0, fallback_priority=1
            ))
            self._register(ModelSpec(
                "gemini-3.6-flash", "gemini", "Gemini 3.6 Flash", CostCategory.FREE_TIER, 0.25, 1.00,
                supports_streaming=True, supports_structured_json=True, supports_vision=True,
                supported_modalities=["text", "image", "audio", "video"],
                supported_thinking_levels=["low", "medium", "high"],
                lifecycle="stable", is_paid_only=False,
                max_context_tokens=1000000, max_output_tokens=8192, timeout_sec=30.0, fallback_priority=2
            ))
            self._register(ModelSpec(
                "gemini-3.5-flash-lite", "gemini", "Gemini 3.5 Flash Lite", CostCategory.FREE_TIER, 0.075, 0.30,
                supports_streaming=True, supports_structured_json=True, supports_vision=True,
                supported_modalities=["text", "image", "audio", "video"],
                supported_thinking_levels=[],
                lifecycle="stable", is_paid_only=False,
                max_context_tokens=1000000, max_output_tokens=8192, timeout_sec=20.0, fallback_priority=3
            ))
            self._register(ModelSpec(
                "gemini-3.1-flash-lite", "gemini", "Gemini 3.1 Flash Lite", CostCategory.FREE_TIER, 0.075, 0.30,
                supports_streaming=True, supports_structured_json=True, supports_vision=True,
                supported_modalities=["text", "image", "audio", "video"],
                supported_thinking_levels=[],
                lifecycle="preview", is_paid_only=False,
                max_context_tokens=1000000, max_output_tokens=8192, timeout_sec=20.0, fallback_priority=4
            ))
            self._register(ModelSpec(
                "gemini-3.1-pro-preview", "gemini", "Gemini 3.1 Pro Preview", CostCategory.FREE_TIER, 1.25, 5.00,
                supports_streaming=True, supports_structured_json=True, supports_vision=True,
                supported_modalities=["text", "image", "audio", "video"],
                supported_thinking_levels=["low", "medium", "high"],
                lifecycle="preview", is_paid_only=False,
                max_context_tokens=1000000, max_output_tokens=8192, timeout_sec=45.0, fallback_priority=5
            ))
            self._register(ModelSpec(
                "gemini-4-argon", "gemini", "Gemini 4 Argon (Paid Flagship)", CostCategory.PAID, 2.50, 10.00,
                supports_streaming=True, supports_structured_json=True, supports_vision=True,
                supported_modalities=["text", "image", "audio", "video"],
                supported_thinking_levels=["low", "medium", "high"],
                lifecycle="preview", is_paid_only=True,
                max_context_tokens=1000000, max_output_tokens=8192, timeout_sec=60.0, fallback_priority=10
            ))
            self._register(ModelSpec(
                "gemini-2.5-flash", "gemini", "Gemini 2.5 Flash", CostCategory.FREE_TIER, 0.15, 0.60,
                supports_streaming=True, supports_structured_json=True, supports_vision=True,
                supported_modalities=["text", "image", "audio", "video"],
                supported_thinking_levels=[],
                lifecycle="legacy", is_paid_only=False,
                max_context_tokens=1000000, max_output_tokens=8192, timeout_sec=30.0, fallback_priority=6
            ))
            self._register(ModelSpec(
                "gemini-2.5-pro", "gemini", "Gemini 2.5 Pro", CostCategory.FREE_TIER, 1.25, 5.00,
                supports_streaming=True, supports_structured_json=True, supports_vision=True,
                supported_modalities=["text", "image", "audio", "video"],
                supported_thinking_levels=[],
                lifecycle="legacy", is_paid_only=False,
                max_context_tokens=1000000, max_output_tokens=8192, timeout_sec=45.0, fallback_priority=7
            ))
            self._register(ModelSpec(
                "gemini-2.0-flash", "gemini", "Gemini 2.0 Flash", CostCategory.FREE_TIER, 0.10, 0.40,
                supports_streaming=True, supports_structured_json=True, supports_vision=True,
                supported_modalities=["text", "image", "audio", "video"],
                supported_thinking_levels=[],
                lifecycle="legacy", is_paid_only=False,
                max_context_tokens=1000000, max_output_tokens=8192, timeout_sec=25.0, fallback_priority=8
            ))
            self._register(ModelSpec(
                "gemini-2.5-flash-lite", "gemini", "Gemini 2.5 Flash Lite", CostCategory.FREE_TIER, 0.075, 0.30,
                supports_streaming=True, supports_structured_json=True, supports_vision=True,
                supported_modalities=["text", "image", "audio", "video"],
                supported_thinking_levels=[],
                lifecycle="legacy", is_paid_only=False,
                max_context_tokens=1000000, max_output_tokens=8192, timeout_sec=20.0, fallback_priority=9
            ))
            self._register(ModelSpec(
                "gemini-3.5-flash", "gemini", "Gemini 3.5 Flash", CostCategory.FREE_TIER, 0.15, 0.60,
                supports_streaming=True, supports_structured_json=True, supports_vision=True,
                supported_modalities=["text", "image", "audio", "video"],
                supported_thinking_levels=[],
                lifecycle="stable", is_paid_only=False,
                max_context_tokens=1000000, max_output_tokens=8192, timeout_sec=30.0, fallback_priority=5
            ))

            # SambaNova models
            self._register(ModelSpec("Meta-Llama-3.3-70B-Instruct", "sambanova", "SambaNova Llama 3.3 70B", CostCategory.FREE_TIER, 0.60, 0.80, supports_streaming=True, supports_structured_json=True, max_output_tokens=4096, timeout_sec=30.0))
            self._register(ModelSpec("Qwen2.5-72B-Instruct", "sambanova", "SambaNova Qwen 2.5 72B", CostCategory.FREE_TIER, 0.60, 0.80, supports_streaming=True, supports_structured_json=True, max_output_tokens=4096, timeout_sec=30.0))

            # Cerebras models (Hardware limit 2048 per call)
            self._register(ModelSpec("llama3.1-8b", "cerebras", "Cerebras Llama 3.1 8B", CostCategory.FREE_TIER, 0.10, 0.10, supports_streaming=True, supports_structured_json=True, max_output_tokens=2048, timeout_sec=20.0))
            self._register(ModelSpec("qwen-3.8-27b", "cerebras", "Cerebras Qwen 3.8 27B", CostCategory.FREE_TIER, 0.20, 0.60, supports_streaming=True, supports_structured_json=True, max_output_tokens=2048, timeout_sec=20.0))
            self._register(ModelSpec("gpt-oss-120b", "cerebras", "Cerebras GPT OSS 120B", CostCategory.FREE_TIER, 0.60, 1.20, supports_streaming=True, supports_structured_json=True, max_output_tokens=2048, timeout_sec=20.0))

            # OpenRouter free models
            self._register(ModelSpec("cohere/north-mini-code:free", "openrouter", "North Mini Code (Free)", CostCategory.ZERO_PRICE, 0.0, 0.0, supports_streaming=True, supports_structured_json=True, max_output_tokens=8192, timeout_sec=30.0))
            self._register(ModelSpec("nvidia/nemotron-3.5-lightning:free", "openrouter", "Nemotron 3.5 Lightning (Free)", CostCategory.ZERO_PRICE, 0.0, 0.0, supports_streaming=True, supports_structured_json=True, max_output_tokens=4096, timeout_sec=30.0))
            self._register(ModelSpec("nvidia/nemotron-3-ultra-550b-a55b:free", "openrouter", "Nemotron 3 Ultra 550B (Free)", CostCategory.ZERO_PRICE, 0.0, 0.0, supports_streaming=True, supports_structured_json=True, max_output_tokens=4096, timeout_sec=30.0))
            self._register(ModelSpec("nvidia/nemotron-3.5-super-vl:free", "openrouter", "Nemotron 3.5 Super VL (Free)", CostCategory.ZERO_PRICE, 0.0, 0.0, supports_streaming=True, supports_structured_json=True, supports_vision=True, max_output_tokens=4096, timeout_sec=30.0))
            self._register(ModelSpec("openrouter/free", "openrouter", "OpenRouter Free Dynamic Router", CostCategory.ZERO_PRICE, 0.0, 0.0, supports_streaming=True, supports_structured_json=True, max_output_tokens=4096, timeout_sec=30.0))
            self._register(ModelSpec("google/gemma-4-31b-it:free", "openrouter", "Gemma 4 31B (Free)", CostCategory.ZERO_PRICE, 0.0, 0.0, supports_streaming=True, supports_structured_json=True, max_output_tokens=4096, timeout_sec=30.0))

    def _register(self, spec: ModelSpec):
        self._models[spec.model_id] = spec

    def get_rotator(self, provider: str) -> Optional[ProviderKeyRotator]:
        with self._lock:
            return self._rotators.get(provider.lower())

    def get_key(self, provider: str) -> str:
        rot = self.get_rotator(provider)
        return rot.get_key() if rot else ""

    def get_key_count(self, provider: str) -> int:
        rot = self.get_rotator(provider)
        return rot.key_count if rot else 0

    def register_model(self, spec: ModelSpec):
        """Registers or updates a ModelSpec in the registry."""
        with self._lock:
            self._models[spec.model_id] = spec

    def get_model_spec(self, model_id: str) -> Optional[ModelSpec]:
        with self._lock:
            spec = self._models.get(model_id)
            if spec:
                return spec
            # Fallback search by model suffix / name
            m_lower = model_id.lower()
            for k, v in self._models.items():
                if k.lower() == m_lower or k.lower().endswith(m_lower):
                    return v
            return None

    def is_provider_enabled(self, provider: str) -> bool:
        with self._lock:
            return self._provider_switches.get(provider.lower(), True)

    def set_provider_enabled(self, provider: str, enabled: bool):
        with self._lock:
            self._provider_switches[provider.lower()] = enabled

    def is_provider_available(self, provider: str) -> bool:
        if not self.is_provider_enabled(provider):
            return False
        return self.get_key_count(provider) > 0

    def is_model_eligible(self, provider: str, model_id: str) -> bool:
        """
        Enforces zero-budget policy and provider availability checks.
        Under STRICT_ZERO_BUDGET=True:
          Only ZERO_PRICE and FREE_TIER models are permitted.
          PAID or UNKNOWN pricing models are skipped.
        """
        if not self.is_provider_available(provider):
            return False

        spec = self.get_model_spec(model_id)
        if not spec:
            # If model is not explicitly registered and paid models not allowed, reject
            return not self.strict_zero_budget or self.allow_paid_models

        if spec.availability_status == "unavailable":
            return False

        if spec.is_paid_only and not self.allow_paid_models:
            return False

        if self.strict_zero_budget and not self.allow_paid_models:
            if spec.cost_category not in (CostCategory.ZERO_PRICE, CostCategory.FREE_TIER):
                return False

        return True

    def get_model_thinking_level(self, model_id: str, complexity: Optional[Any] = None) -> Optional[str]:
        """Resolves optimal thinking level (low, medium, high) based on model capabilities and task complexity."""
        with self._lock:
            spec = self.get_model_spec(model_id)
            if not spec or not spec.supported_thinking_levels:
                return None
            comp_str = str(getattr(complexity, "value", complexity) or "").upper()
            if comp_str in ("FAST", "LIGHT"):
                return "low" if "low" in spec.supported_thinking_levels else None
            elif comp_str == "STANDARD":
                return "medium" if "medium" in spec.supported_thinking_levels else "low"
            elif comp_str in ("COMPLEX", "DEEP"):
                return "high" if "high" in spec.supported_thinking_levels else "medium"
            return "medium" if "medium" in spec.supported_thinking_levels else spec.supported_thinking_levels[0]

    def get_model_capabilities(self, model_id: str) -> Dict[str, Any]:
        """Returns verified capabilities, lifecycle, modalities, and limits for a given model."""
        with self._lock:
            spec = self.get_model_spec(model_id)
            if not spec:
                return {}
            return {
                "model_id": spec.model_id,
                "provider": spec.provider,
                "lifecycle": spec.lifecycle,
                "supported_modalities": list(spec.supported_modalities),
                "supported_thinking_levels": list(spec.supported_thinking_levels),
                "cost_category": spec.cost_category.value,
                "is_paid_only": spec.is_paid_only,
                "supports_vision": spec.supports_vision,
                "supports_streaming": spec.supports_streaming,
                "supports_structured_json": spec.supports_structured_json,
                "max_context_tokens": spec.max_context_tokens,
                "max_output_tokens": spec.max_output_tokens,
                "timeout_sec": spec.timeout_sec
            }

    def set_model_enabled(self, model_id: str, enabled: bool):
        """Allows enabling or disabling a specific model at runtime."""
        with self._lock:
            spec = self.get_model_spec(model_id)
            if spec:
                spec.availability_status = "available" if enabled else "unavailable"

    def set_strict_zero_budget(self, enabled: bool):
        """Allows toggling strict zero-budget mode at runtime without restarts."""
        with self._lock:
            self.strict_zero_budget = enabled

    def set_allow_paid_models(self, enabled: bool):
        """Allows toggling paid model allowance at runtime."""
        with self._lock:
            self.allow_paid_models = enabled

    def get_model_catalog(self) -> List[Dict[str, Any]]:
        """Returns all registered models and their operational metadata."""
        with self._lock:
            catalog = []
            for m_id, spec in self._models.items():
                catalog.append({
                    "model_id": spec.model_id,
                    "provider": spec.provider,
                    "display_name": spec.display_name or spec.model_id,
                    "cost_category": spec.cost_category.value,
                    "lifecycle": spec.lifecycle,
                    "supported_modalities": spec.supported_modalities,
                    "supported_thinking_levels": spec.supported_thinking_levels,
                    "is_paid_only": spec.is_paid_only,
                    "supports_vision": spec.supports_vision,
                    "supports_streaming": spec.supports_streaming,
                    "supports_structured_json": spec.supports_structured_json,
                    "availability_status": spec.availability_status,
                    "fallback_priority": spec.fallback_priority
                })
            return catalog

    def get_provider_summary(self) -> Dict[str, Any]:
        """Returns status of all 5 providers, key counts, and active enablement."""
        with self._lock:
            providers = ["groq", "gemini", "sambanova", "cerebras", "openrouter"]
            summary = {}
            for p in providers:
                summary[p] = {
                    "enabled": self.is_provider_enabled(p),
                    "key_count": self.get_key_count(p),
                    "available": self.is_provider_available(p)
                }
            return summary

    def mark_model_unavailable(self, model_id: str, cooldown_seconds: float = 300.0):
        with self._lock:
            spec = self._models.get(model_id)
            if spec:
                spec.availability_status = "unavailable"
                spec.last_verified_ts = time.time() + cooldown_seconds

    def discover_models(self, provider: str, force_refresh: bool = False, timeout: float = 3.0) -> List[str]:
        """
        Live model discovery from official provider /models endpoints.
        Cached with 1-hour TTL to prevent repeated network overhead.
        Safely falls back to registered models if discovery fails or times out.
        """
        p = provider.lower()
        now = time.time()

        with self._lock:
            cached = self._discovered_cache.get(p)
            if cached and not force_refresh and (now - cached[0] < 3600.0):
                return cached[1]

        key = self.get_key(p)
        if not key:
            # Return currently known model IDs for this provider
            known = [m for m, spec in self._models.items() if spec.provider == p]
            return known

        discovered: List[str] = []
        try:
            if p == "groq":
                resp = requests.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=timeout
                )
                if resp.status_code == 200:
                    data = resp.json()
                    discovered = [item["id"] for item in data.get("data", []) if "id" in item]

            elif p == "sambanova":
                resp = requests.get(
                    "https://api.sambanova.ai/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=timeout
                )
                if resp.status_code == 200:
                    data = resp.json()
                    discovered = [item["id"] for item in data.get("data", []) if "id" in item]

            elif p == "cerebras":
                resp = requests.get(
                    "https://api.cerebras.ai/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=timeout
                )
                if resp.status_code == 200:
                    data = resp.json()
                    discovered = [item["id"] for item in data.get("data", []) if "id" in item]

            elif p == "openrouter":
                resp = requests.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=timeout
                )
                if resp.status_code == 200:
                    data = resp.json()
                    discovered = [item["id"] for item in data.get("data", []) if "id" in item]

            elif p == "gemini":
                resp = requests.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
                    timeout=timeout
                )
                if resp.status_code == 200:
                    data = resp.json()
                    discovered = [item["name"].replace("models/", "") for item in data.get("models", []) if "name" in item]
        except Exception as e:
            logger.debug("Live discovery skipped for %s (%s)", p, e)

        with self._lock:
            if discovered:
                self._discovered_cache[p] = (now, discovered)
                return discovered
            # Fall back to known static specifications
            fallback_models = [m for m, spec in self._models.items() if spec.provider == p]
            return fallback_models


# Global singleton registry
registry = ProviderRegistry()
