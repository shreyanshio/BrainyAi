import time
"""
BrainyAi Central Provider & Model Registry
Manages verified model identifiers, key pools (with 8-15 keys rotation),
provider capabilities, timeouts, and token limits.
"""

import os
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class ModelSpec:
    model_id: str
    provider: str
    supports_streaming: bool = True
    supports_structured_json: bool = True
    supports_vision_pdf: bool = False
    max_context_tokens: int = 128000
    max_output_tokens: int = 4096
    timeout_sec: float = 25.0
    fallback_priority: int = 1

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
    """Thread-safe round-robin key rotator with state tracking."""
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
        self._lock = threading.Lock()
        self._rotators: Dict[str, ProviderKeyRotator] = {}
        self._models: Dict[str, ModelSpec] = {}
        self.reload_configuration()

    def reload_configuration(self):
        with self._lock:
            # 1. Load keys for all supported providers
            self._rotators["groq"] = ProviderKeyRotator("groq", collect_key_pool("GROQ_API_KEY", 15))
            self._rotators["gemini"] = ProviderKeyRotator("gemini", collect_key_pool("GEMINI_API_KEY", 15))
            self._rotators["sambanova"] = ProviderKeyRotator("sambanova", collect_key_pool("SAMBANOVA_API_KEY", 15))
            self._rotators["cerebras"] = ProviderKeyRotator("cerebras", collect_key_pool("CEREBRAS_API_KEY", 15))
            self._rotators["openrouter"] = ProviderKeyRotator("openrouter", collect_key_pool("OPENROUTER_API_KEY", 15))
            self._rotators["tavily"] = ProviderKeyRotator("tavily", collect_key_pool("TAVILY_API_KEY", 15))
            self._rotators["mistral"] = ProviderKeyRotator("mistral", collect_key_pool("MISTRAL_API_KEY", 15))
            self._rotators["deepseek"] = ProviderKeyRotator("deepseek", collect_key_pool("DEEPSEEK_API_KEY", 15))
            self._rotators["nvidia"] = ProviderKeyRotator("nvidia", collect_key_pool("NVIDIA_API_KEY", 15))
            self._rotators["together"] = ProviderKeyRotator("together", collect_key_pool("TOGETHER_API_KEY", 15))
            self._rotators["openai"] = ProviderKeyRotator("openai", collect_key_pool("OPENAI_API_KEY", 15))

            # 2. Configurable model IDs with live defaults
            self.groq_fast_model = (os.getenv("GROQ_MODEL_FAST") or "qwen/qwen3.8-27b").strip()
            self.groq_balanced_model = (os.getenv("GROQ_MODEL_BALANCED") or "openai/gpt-oss-120b").strip()
            self.gemini_reasoning_model = (os.getenv("GEMINI_REASONING_MODEL") or "gemini-2.5-flash").strip()
            self.gemini_pdf_model = (os.getenv("GEMINI_PDF_MODEL") or "gemini-2.5-flash").strip()
            self.sambanova_reasoning_model = (os.getenv("SAMBANOVA_REASONING_MODEL") or "Meta-Llama-3.3-70B-Instruct").strip()
            self.sambanova_fast_model = (os.getenv("SAMBANOVA_FAST_MODEL") or "Meta-Llama-3.1-8B-Instruct").strip()
            self.openrouter_coding_model = (os.getenv("OPENROUTER_CODING_MODEL") or "google/gemma-4-31b-it:free").strip()
            self.openrouter_free_model = (os.getenv("OPENROUTER_FREE_MODEL") or "google/gemma-4-31b-it:free").strip()

            # 3. Model specifications & capabilities
            self._models.clear()
            # Groq
            self._models[self.groq_fast_model] = ModelSpec(self.groq_fast_model, "groq", supports_streaming=True, supports_structured_json=True, max_output_tokens=2048, timeout_sec=20.0)
            self._models[self.groq_balanced_model] = ModelSpec(self.groq_balanced_model, "groq", supports_streaming=True, supports_structured_json=True, max_output_tokens=4096, timeout_sec=25.0)
            self._models["llama-3.1-8b-instant"] = ModelSpec("llama-3.1-8b-instant", "groq", supports_streaming=True, supports_structured_json=True, max_output_tokens=2048, timeout_sec=15.0)

            # Gemini (Multimodal PDF native support)
            self._models[self.gemini_reasoning_model] = ModelSpec(self.gemini_reasoning_model, "gemini", supports_streaming=True, supports_structured_json=True, supports_vision_pdf=True, max_context_tokens=1000000, max_output_tokens=8192, timeout_sec=30.0)
            self._models["gemini-2.0-flash"] = ModelSpec("gemini-2.0-flash", "gemini", supports_streaming=True, supports_structured_json=True, supports_vision_pdf=True, max_context_tokens=1000000, max_output_tokens=8192, timeout_sec=25.0)
            self._models["gemini-2.5-flash-lite"] = ModelSpec("gemini-2.5-flash-lite", "gemini", supports_streaming=True, supports_structured_json=True, supports_vision_pdf=True, max_context_tokens=1000000, max_output_tokens=4096, timeout_sec=20.0)

            # SambaNova (SN40L high-speed 70B & 72B inference)
            self._models[self.sambanova_reasoning_model] = ModelSpec(self.sambanova_reasoning_model, "sambanova", supports_streaming=True, supports_structured_json=True, max_output_tokens=4096, timeout_sec=30.0)
            self._models["Qwen2.5-72B-Instruct"] = ModelSpec("Qwen2.5-72B-Instruct", "sambanova", supports_streaming=True, supports_structured_json=True, max_output_tokens=4096, timeout_sec=30.0)
            self._models[self.sambanova_fast_model] = ModelSpec(self.sambanova_fast_model, "sambanova", supports_streaming=True, supports_structured_json=True, max_output_tokens=2048, timeout_sec=20.0)

            # Cerebras
            self._models["llama3.1-8b"] = ModelSpec("llama3.1-8b", "cerebras", supports_streaming=True, supports_structured_json=True, max_output_tokens=2048, timeout_sec=20.0)
            self._models["qwen-3.8-27b"] = ModelSpec("qwen-3.8-27b", "cerebras", supports_streaming=True, supports_structured_json=True, max_output_tokens=2048, timeout_sec=20.0)
            self._models["gpt-oss-120b"] = ModelSpec("gpt-oss-120b", "cerebras", supports_streaming=True, supports_structured_json=True, max_output_tokens=2048, timeout_sec=20.0)

            # OpenRouter
            self._models[self.openrouter_coding_model] = ModelSpec(self.openrouter_coding_model, "openrouter", supports_streaming=True, supports_structured_json=True, max_output_tokens=4096, timeout_sec=30.0)
            self._models["nvidia/nemotron-3.5-lightning:free"] = ModelSpec("nvidia/nemotron-3.5-lightning:free", "openrouter", supports_streaming=True, max_output_tokens=2048, timeout_sec=25.0)

    def get_rotator(self, provider: str) -> Optional[ProviderKeyRotator]:
        with self._lock:
            return self._rotators.get(provider.lower())

    def get_key(self, provider: str) -> str:
        rot = self.get_rotator(provider)
        return rot.get_key() if rot else ""

    def get_key_count(self, provider: str) -> int:
        rot = self.get_rotator(provider)
        return rot.key_count if rot else 0

    def get_model_spec(self, model_id: str) -> Optional[ModelSpec]:
        with self._lock:
            return self._models.get(model_id)

    def is_provider_available(self, provider: str) -> bool:
        return self.get_key_count(provider) > 0

# Global singleton
registry = ProviderRegistry()
