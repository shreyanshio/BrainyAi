"""
Brainy Intelligent Rate Limiter & Abuse Prevention Engine
Provides layered protection:
  1. User-level concurrency limits (prevent runaway parallel generation).
  2. Daily token consumption budgets per user.
  3. Rapid request burst detection (anti-bot / anti-DDoS).
  4. Idempotency & double-submission deduplication (prevent double-clicks).
"""

import time
import hashlib
import threading
from typing import Dict, Tuple, Optional, Any
from dataclasses import dataclass, field


@dataclass
class UserUsageState:
    user_id: str
    active_requests: int = 0
    daily_tokens_consumed: int = 0
    last_reset_day: int = field(default_factory=lambda: int(time.time() // 86400))
    request_timestamps: list = field(default_factory=list)
    recent_fingerprints: Dict[str, float] = field(default_factory=dict)  # fingerprint -> timestamp


class IntelligentRateLimiter:
    """Thread-safe rate limiter, concurrency controller, and abuse detection guard."""

    def __init__(
        self,
        max_concurrent_per_user: int = 2,
        max_requests_per_minute: int = 15,
        daily_token_budget_per_user: int = 300000,
        duplicate_window_sec: float = 8.0,
    ):
        self.max_concurrent = max_concurrent_per_user
        self.max_rpm = max_requests_per_minute
        self.daily_token_budget = daily_token_budget_per_user
        self.duplicate_window = duplicate_window_sec
        self._lock = threading.Lock()
        self._user_states: Dict[str, UserUsageState] = {}

    def _get_user_state(self, user_id: str | int) -> UserUsageState:
        uid = str(user_id)
        current_day = int(time.time() // 86400)
        state = self._user_states.get(uid)
        if not state:
            state = UserUsageState(user_id=uid, last_reset_day=current_day)
            self._user_states[uid] = state
        elif state.last_reset_day != current_day:
            state.daily_tokens_consumed = 0
            state.last_reset_day = current_day
        return state

    def check_and_acquire(
        self,
        user_id: str | int,
        content: str,
        idempotency_key: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Validates request against rate limit, concurrency, daily token budget, and deduplication.
        Returns: (allowed: bool, rejection_code: Optional[str], retry_after_sec: Optional[int])
        """
        now = time.time()
        uid = str(user_id)

        with self._lock:
            state = self._get_user_state(uid)

            # 1. Clean expired timestamps from rolling window (60s)
            state.request_timestamps = [t for t in state.request_timestamps if t > now - 60.0]

            # 2. Concurrency limit check
            if state.active_requests >= self.max_concurrent:
                return False, "CONCURRENCY_LIMIT_EXCEEDED", 2

            # 3. Requests per minute check
            if len(state.request_timestamps) >= self.max_rpm:
                oldest = state.request_timestamps[0]
                retry_after = max(1, int(oldest + 60.0 - now + 1.0))
                return False, "RATE_LIMIT_EXCEEDED", retry_after

            # 4. Daily token budget check
            if state.daily_tokens_consumed >= self.daily_token_budget:
                return False, "DAILY_TOKEN_BUDGET_EXCEEDED", 3600

            # 5. Deduplication check (accidental double-click / rapid resubmission)
            fingerprint = idempotency_key or hashlib.sha256(content.strip().encode("utf-8")).hexdigest()
            # Clean old fingerprints
            state.recent_fingerprints = {
                fp: ts for fp, ts in state.recent_fingerprints.items() if ts > now - self.duplicate_window
            }
            if fingerprint in state.recent_fingerprints:
                return False, "DUPLICATE_SUBMISSION_DETECTED", int(self.duplicate_window)

            # Accept request & acquire concurrency slot
            state.active_requests += 1
            state.request_timestamps.append(now)
            state.recent_fingerprints[fingerprint] = now
            return True, None, None

    def release(self, user_id: str | int, tokens_consumed: int = 0):
        """Releases the concurrency slot and records consumed tokens."""
        uid = str(user_id)
        with self._lock:
            state = self._user_states.get(uid)
            if state:
                state.active_requests = max(0, state.active_requests - 1)
                state.daily_tokens_consumed += max(0, tokens_consumed)

    def get_user_status(self, user_id: str | int) -> Dict[str, Any]:
        """Returns rate-limit and token budget status for telemetry and admin reporting."""
        with self._lock:
            state = self._get_user_state(str(user_id))
            return {
                "user_id": state.user_id,
                "active_requests": state.active_requests,
                "daily_tokens_consumed": state.daily_tokens_consumed,
                "daily_tokens_limit": self.daily_token_budget,
                "rpm_current": len(state.request_timestamps),
                "rpm_limit": self.max_rpm,
            }


# Singleton limiter instance
intelligent_rate_limiter = IntelligentRateLimiter()
