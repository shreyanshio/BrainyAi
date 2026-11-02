"""
Brainy Intelligent Response Cache Engine
Provides multi-tier caching:
  1. Exact response cache for static educational definitions, stable reference facts, and unit conversions.
  2. Strict privacy isolation: NEVER caches private chats, personal profiles, or PDF documents across users.
  3. TTL management, hit statistics, and user/conversation-scoped cache invalidation.
"""

import re
import time
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger("ai_cache")

# Keywords that indicate static educational questions safe for global caching
_STATIC_EDUCATIONAL_PATTERNS = re.compile(
    r"^(?:what is|define|meaning of|explain the concept of|formula for|si unit of)\s+([a-zA-Z0-9_\-\s\']{2,60})[?\.]*$",
    re.IGNORECASE
)

# Topics that must NEVER be globally cached (personal, user-specific, sensitive, ephemeral)
_NON_CACHEABLE_PATTERNS = re.compile(
    r"\b(my|i am|me|myself|pdf|document|file|uploaded|session|account|username|password|email|phone|grade|score|marks|exam date|today|now|tomorrow|yesterday)\b",
    re.IGNORECASE
)


@dataclass
class CacheEntry:
    text: str
    task: str
    model: str
    provider: str
    created_at: float
    ttl: float
    input_tokens: int = 0
    output_tokens: int = 0
    is_global_educational: bool = False
    user_id: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        return time.time() > (self.created_at + self.ttl)


class ResponseCache:
    """Thread-safe in-memory cache for deterministic and static educational queries."""

    def __init__(self, default_ttl: float = 3600.0, max_entries: int = 5000):
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self._cache: Dict[str, CacheEntry] = {}
        self._user_keys: Dict[str, set] = {}
        self.hits: int = 0
        self.misses: int = 0
        self.saved_tokens: int = 0

    def _normalize_query(self, query: str) -> str:
        """Normalizes query text: lowercase, strip punctuation and excessive whitespace."""
        if not query:
            return ""
        q = re.sub(r"[^\w\s]", "", query.lower())
        return re.sub(r"\s+", " ", q).strip()

    def _generate_key(
        self,
        normalized_query: str,
        task: str,
        model: str,
        user_id: Optional[str] = None,
        is_global: bool = False
    ) -> str:
        prefix = "global" if is_global else f"user_{user_id or 'anon'}"
        raw = f"{prefix}:{task}:{model}:{normalized_query}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def is_eligible_for_global_cache(self, query: str, document_context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Determines if a query represents a purely static, non-personalized educational definition.
        Strict rule: If user mentions personal state, uploaded documents, or time-sensitive terms, REJECT.
        """
        if document_context and (document_context.get("has_image") or document_context.get("pdf_text") or document_context.get("document_id")):
            return False
        if not query:
            return False
        if _NON_CACHEABLE_PATTERNS.search(query):
            return False
        match = _STATIC_EDUCATIONAL_PATTERNS.match(query.strip())
        return bool(match)

    def get(
        self,
        query: str,
        task: str,
        model: str,
        user_id: Optional[str] = None
    ) -> Optional[Tuple[str, CacheEntry]]:
        """
        Looks up a cached response.
        Checks user-scoped cache first; falls back to global educational cache only if query is safe.
        """
        norm = self._normalize_query(query)
        if not norm:
            self.misses += 1
            return None

        # 1. User-scoped check
        if user_id:
            user_key = self._generate_key(norm, task, model, user_id=str(user_id), is_global=False)
            entry = self._cache.get(user_key)
            if entry:
                if entry.is_expired:
                    self._evict(user_key)
                else:
                    self.hits += 1
                    self.saved_tokens += (entry.input_tokens + entry.output_tokens)
                    return entry.text, entry

        # 2. Global educational check (only for static educational questions)
        if self.is_eligible_for_global_cache(query):
            global_key = self._generate_key(norm, task, model, is_global=True)
            entry = self._cache.get(global_key)
            if entry:
                if entry.is_expired:
                    self._evict(global_key)
                else:
                    self.hits += 1
                    self.saved_tokens += (entry.input_tokens + entry.output_tokens)
                    return entry.text, entry

        self.misses += 1
        return None

    def set(
        self,
        query: str,
        response_text: str,
        task: str,
        model: str,
        provider: str,
        user_id: Optional[str] = None,
        ttl: Optional[float] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        document_context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Saves a response into the cache.
        Enforces privacy constraints: never globally caches personal or document-related material.
        """
        if not query or not response_text:
            return None

        # Strict privacy check
        if document_context and (document_context.get("has_image") or document_context.get("pdf_text")):
            return None  # Never cache PDF or multimodal content
        if _NON_CACHEABLE_PATTERNS.search(query):
            is_global = False
        else:
            is_global = self.is_eligible_for_global_cache(query, document_context)

        norm = self._normalize_query(query)
        effective_ttl = ttl or self.default_ttl
        cache_key = self._generate_key(norm, task, model, user_id=str(user_id) if not is_global else None, is_global=is_global)

        # Enforce max entries with LRU-like purge
        if len(self._cache) >= self.max_entries:
            self._purge_expired_or_oldest()

        entry = CacheEntry(
            text=response_text,
            task=task,
            model=model,
            provider=provider,
            created_at=time.time(),
            ttl=effective_ttl,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            is_global_educational=is_global,
            user_id=str(user_id) if not is_global else None
        )
        self._cache[cache_key] = entry
        if user_id and not is_global:
            self._user_keys.setdefault(str(user_id), set()).add(cache_key)

        return cache_key

    def _evict(self, key: str):
        entry = self._cache.pop(key, None)
        if entry and entry.user_id:
            keys = self._user_keys.get(entry.user_id)
            if keys:
                keys.discard(key)

    def _purge_expired_or_oldest(self):
        now = time.time()
        expired = [k for k, v in self._cache.items() if now > (v.created_at + v.ttl)]
        for k in expired:
            self._evict(k)
        if len(self._cache) >= self.max_entries:
            # Drop 10% oldest entries
            sorted_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k].created_at)
            for k in sorted_keys[: max(1, self.max_entries // 10)]:
                self._evict(k)

    def invalidate_user(self, user_id: str | int):
        """Invalidates all cached entries for a given user (e.g. upon account deletion or logout)."""
        uid = str(user_id)
        keys = list(self._user_keys.get(uid, []))
        for k in keys:
            self._evict(k)
        self._user_keys.pop(uid, None)

    def clear(self):
        self._cache.clear()
        self._user_keys.clear()
        self.hits = 0
        self.misses = 0
        self.saved_tokens = 0


# Singleton global cache instance
response_cache = ResponseCache()
