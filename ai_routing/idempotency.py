"""
Idempotency Engine for Brainy AI Systems
Provides atomic, thread-safe, sliding-window deduplication for:
- Telegram update_ids (prevents duplicate processing on Telegram redelivery/network retries)
- Web API request tokens (prevents double charging or duplicate conversation turns)
"""

import time
import threading
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class IdempotencyState(Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IdempotencyRecord:
    key: str
    state: IdempotencyState
    created_at: float
    expires_at: float
    result: Optional[Any] = None


class IdempotencyEngine:
    """Thread-safe in-memory idempotency tracker with automatic TTL eviction."""

    def __init__(self, max_entries: int = 10000, default_ttl_seconds: int = 300):
        self._records: Dict[str, IdempotencyRecord] = {}
        self._lock = threading.RLock()
        self._max_entries = max_entries
        self._default_ttl_seconds = default_ttl_seconds

    def _purge_expired(self, now: float) -> None:
        """Removes expired records if cache exceeds max size or during routine checks."""
        if len(self._records) < self._max_entries:
            return
        expired = [k for k, r in self._records.items() if now > r.expires_at]
        for k in expired:
            self._records.pop(k, None)

    def claim(self, key: str, ttl_seconds: Optional[int] = None) -> Tuple[bool, Optional[IdempotencyRecord]]:
        """
        Attempts to claim an idempotency key.
        Returns:
            (True, record) if the claim was granted (first time seen or previous failed/expired).
            (False, record) if key is currently PROCESSING or already COMPLETED.
        """
        if not key:
            return True, None

        clean_key = str(key).strip()
        now = time.time()
        ttl = ttl_seconds or self._default_ttl_seconds

        with self._lock:
            self._purge_expired(now)
            existing = self._records.get(clean_key)

            if existing:
                # If expired, allow re-claim
                if now > existing.expires_at:
                    self._records.pop(clean_key, None)
                elif existing.state in (IdempotencyState.PROCESSING, IdempotencyState.COMPLETED):
                    return False, existing
                elif existing.state == IdempotencyState.FAILED:
                    # Previous failed, allow retry
                    self._records.pop(clean_key, None)

            # Claim key in PROCESSING state
            rec = IdempotencyRecord(
                key=clean_key,
                state=IdempotencyState.PROCESSING,
                created_at=now,
                expires_at=now + ttl
            )
            self._records[clean_key] = rec
            return True, rec

    def complete(self, key: str, result: Optional[Any] = None, ttl_seconds: Optional[int] = None) -> None:
        """Marks the key as successfully COMPLETED with optional cached result."""
        if not key:
            return
        clean_key = str(key).strip()
        now = time.time()
        ttl = ttl_seconds or self._default_ttl_seconds

        with self._lock:
            if clean_key in self._records:
                rec = self._records[clean_key]
                rec.state = IdempotencyState.COMPLETED
                rec.result = result
                rec.expires_at = now + ttl

    def release_or_fail(self, key: str) -> None:
        """Marks the key as FAILED, allowing immediate retry if needed."""
        if not key:
            return
        clean_key = str(key).strip()
        with self._lock:
            if clean_key in self._records:
                self._records[clean_key].state = IdempotencyState.FAILED

    def clear(self) -> None:
        """Clears all records (used for test teardown)."""
        with self._lock:
            self._records.clear()


# Global shared instance
idempotency_engine = IdempotencyEngine()
