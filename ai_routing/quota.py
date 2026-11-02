"""
Shared 5-Image Quota & Telegram-Web Account Linking Engine.
Unified between Brainy Web App (Flask backend) and Brainy Telegram Bot.

Architecture:
- Two-Phase Reservation Pattern: reserve -> commit / release
- Idempotency support for Telegram update_id and Web request IDs
- Automatic expiration of stale uncommitted reservations (TTL: 120s)
- Unified identity resolution: maps Telegram ID -> Web ID seamlessly
"""

import time
import secrets
import logging
import threading
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

IMAGE_FREE_LIMIT = 5

_quota_lock = threading.RLock()

# Fast atomic in-memory stores with zero cross-user collisions
_in_memory_quotas: Dict[str, Dict[str, Any]] = {}
_in_memory_reservations: Dict[str, Dict[str, Any]] = {} # res_id -> {effective_id, idempotency_key, created_at, expires_at, status}
_in_memory_link_codes: Dict[str, Dict[str, Any]] = {}   # code -> {web_user_id, expires_at}
_in_memory_user_links: Dict[str, str] = {}              # telegram_id_str -> web_user_id


def resolve_effective_identity(user_id: Any) -> str:
    """Resolves Telegram user ID to linked Web user ID if account link exists."""
    str_id = str(user_id).strip()
    with _quota_lock:
        return _in_memory_user_links.get(str_id, str_id)


def _clean_stale_reservations_locked(now: float) -> None:
    """Purges expired uncommitted reservations."""
    for res_id, r in list(_in_memory_reservations.items()):
        if r.get("status") == "reserved" and now > r.get("expires_at", 0):
            r["status"] = "expired"


def _count_active_reservations_locked(effective_id: str, now: float) -> int:
    """Counts uncommitted reservations that are still active (not expired, not released)."""
    count = 0
    for r in _in_memory_reservations.values():
        if r.get("effective_id") == effective_id and r.get("status") == "reserved":
            if now <= r.get("expires_at", 0):
                count += 1
    return count


def get_user_image_quota(user_id: Any) -> Dict[str, Any]:
    """Returns current quota status for user (linked or standalone)."""
    now = time.time()
    effective_id = resolve_effective_identity(user_id)
    str_id = str(user_id).strip()

    with _quota_lock:
        _clean_stale_reservations_locked(now)
        entry = _in_memory_quotas.get(effective_id)
        if not entry:
            entry = {"used": 0, "limit": IMAGE_FREE_LIMIT, "updated_at": now}
            _in_memory_quotas[effective_id] = entry

        committed_used = entry.get("used", 0)
        active_res = _count_active_reservations_locked(effective_id, now)
        total_used = committed_used + active_res
        remaining = max(0, IMAGE_FREE_LIMIT - total_used)
        is_linked = str_id in _in_memory_user_links or effective_id != str_id

        return {
            "used": committed_used,
            "reserved": active_res,
            "total_consumed": total_used,
            "limit": IMAGE_FREE_LIMIT,
            "remaining": remaining,
            "allowed": remaining > 0,
            "is_linked": is_linked,
            "effective_id": effective_id,
        }


def reserve_image_quota(
    user_id: Any,
    idempotency_key: Optional[str] = None,
    ttl_seconds: int = 120
) -> Tuple[Optional[str], int, str]:
    """
    Two-Phase Reservation: Atomically reserves 1 image credit.
    Returns: (reservation_id: str | None, remaining_after_reservation: int, effective_id: str)
    If remaining is 0, returns (None, 0, effective_id).
    """
    now = time.time()
    effective_id = resolve_effective_identity(user_id)

    with _quota_lock:
        _clean_stale_reservations_locked(now)

        # Idempotency check: if key already reserved/committed, return existing
        if idempotency_key:
            clean_key = str(idempotency_key).strip()
            for res_id, r in _in_memory_reservations.items():
                if r.get("idempotency_key") == clean_key and r.get("effective_id") == effective_id:
                    if r.get("status") in ("reserved", "committed"):
                        quota = get_user_image_quota(user_id)
                        return res_id, quota["remaining"], effective_id

        entry = _in_memory_quotas.setdefault(
            effective_id,
            {"used": 0, "limit": IMAGE_FREE_LIMIT, "updated_at": now}
        )

        committed_used = entry.get("used", 0)
        active_res = _count_active_reservations_locked(effective_id, now)
        total_used = committed_used + active_res

        if total_used >= IMAGE_FREE_LIMIT:
            return None, 0, effective_id

        reservation_id = f"res_{secrets.token_hex(8)}"
        _in_memory_reservations[reservation_id] = {
            "effective_id": effective_id,
            "idempotency_key": str(idempotency_key).strip() if idempotency_key else None,
            "created_at": now,
            "expires_at": now + ttl_seconds,
            "status": "reserved"
        }

        remaining_after = max(0, IMAGE_FREE_LIMIT - (total_used + 1))
        return reservation_id, remaining_after, effective_id


def commit_image_quota(reservation_id: str) -> bool:
    """Commits a previously granted reservation, incrementing committed usage."""
    if not reservation_id:
        return False

    now = time.time()
    with _quota_lock:
        r = _in_memory_reservations.get(reservation_id)
        if not r or r.get("status") != "reserved":
            return False

        effective_id = r["effective_id"]
        entry = _in_memory_quotas.setdefault(
            effective_id,
            {"used": 0, "limit": IMAGE_FREE_LIMIT, "updated_at": now}
        )
        entry["used"] = min(IMAGE_FREE_LIMIT, entry["used"] + 1)
        entry["updated_at"] = now
        r["status"] = "committed"
        return True


def release_image_quota(reservation_id: str) -> bool:
    """Releases a reservation upon upstream failure, refunding the slot immediately."""
    if not reservation_id:
        return False

    with _quota_lock:
        r = _in_memory_reservations.get(reservation_id)
        if not r or r.get("status") != "reserved":
            return False

        r["status"] = "released"
        return True


def consume_user_image_quota(user_id: Any) -> Tuple[bool, int, str]:
    """
    Backwards-compatible atomic consumption wrapper.
    Reserves and immediately commits if available.
    Returns: (allowed: bool, remaining: int, effective_id: str)
    """
    res_id, remaining, effective_id = reserve_image_quota(user_id)
    if not res_id:
        return False, 0, effective_id

    commit_image_quota(res_id)
    return True, remaining, effective_id


def refund_user_image_quota(user_id_or_effective_id: Any) -> None:
    """Refunds 1 image credit if upstream model inference fails."""
    effective_id = resolve_effective_identity(user_id_or_effective_id)
    now = time.time()
    with _quota_lock:
        if effective_id in _in_memory_quotas:
            entry = _in_memory_quotas[effective_id]
            if entry["used"] > 0:
                entry["used"] -= 1
                entry["updated_at"] = now


def generate_telegram_link_code(web_user_id: Any, ttl_seconds: int = 600) -> str:
    """Generates an ephemeral, single-use 6-character link code for Web-Telegram sync."""
    code = secrets.token_hex(3).upper()  # 6 chars
    with _quota_lock:
        _in_memory_link_codes[code] = {
            "web_user_id": str(web_user_id).strip(),
            "expires_at": time.time() + ttl_seconds
        }
    return code


def link_telegram_to_web_account(telegram_id: Any, link_code: str) -> Tuple[bool, str]:
    """Links Telegram user to Web account via single-use code."""
    clean_code = link_code.strip().upper()
    now = time.time()

    with _quota_lock:
        record = _in_memory_link_codes.get(clean_code)
        if not record:
            return False, "Invalid link code."
        if now > record["expires_at"]:
            _in_memory_link_codes.pop(clean_code, None)
            return False, "Link code has expired."

        web_user_id = record["web_user_id"]
        tg_str = str(telegram_id).strip()

        # Link accounts
        _in_memory_user_links[tg_str] = web_user_id
        # Single use -> consume code immediately
        _in_memory_link_codes.pop(clean_code, None)

        # Sync quotas: merge any used counts (max of both)
        tg_used = _in_memory_quotas.get(tg_str, {}).get("used", 0)
        web_entry = _in_memory_quotas.setdefault(
            web_user_id,
            {"used": 0, "limit": IMAGE_FREE_LIMIT, "updated_at": now}
        )
        web_entry["used"] = max(web_entry["used"], tg_used)

        return True, web_user_id
