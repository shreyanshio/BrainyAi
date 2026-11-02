"""
Shared 5-Image Quota & Telegram-Web Account Linking Engine.
Unified between Brainy Web App (Flask backend) and Brainy Telegram Bot.
"""

import time
import secrets
import logging
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

IMAGE_FREE_LIMIT = 5

# Fast atomic in-memory stores with zero cross-user collisions
_in_memory_quotas: Dict[str, Dict[str, Any]] = {}
_in_memory_link_codes: Dict[str, Dict[str, Any]] = {}  # code -> {web_user_id, expires_at}
_in_memory_user_links: Dict[str, str] = {}  # telegram_id_str -> web_user_id


def resolve_effective_identity(user_id: Any) -> str:
    """Resolves Telegram user ID to linked Web user ID if account link exists."""
    str_id = str(user_id).strip()
    return _in_memory_user_links.get(str_id, str_id)


def get_user_image_quota(user_id: Any) -> Dict[str, Any]:
    """Returns current quota status for user (linked or standalone)."""
    effective_id = resolve_effective_identity(user_id)
    entry = _in_memory_quotas.get(effective_id)
    if not entry:
        entry = {"used": 0, "limit": IMAGE_FREE_LIMIT, "updated_at": time.time()}
        _in_memory_quotas[effective_id] = entry

    used = entry.get("used", 0)
    remaining = max(0, IMAGE_FREE_LIMIT - used)
    is_linked = str(user_id).strip() in _in_memory_user_links or effective_id != str(user_id).strip()

    return {
        "used": used,
        "limit": IMAGE_FREE_LIMIT,
        "remaining": remaining,
        "allowed": remaining > 0,
        "is_linked": is_linked,
        "effective_id": effective_id,
    }


def consume_user_image_quota(user_id: Any) -> Tuple[bool, int, str]:
    """
    Atomically attempts to consume 1 image reasoning credit.
    Returns: (allowed: bool, remaining: int, effective_id: str)
    """
    effective_id = resolve_effective_identity(user_id)
    entry = _in_memory_quotas.setdefault(
        effective_id,
        {"used": 0, "limit": IMAGE_FREE_LIMIT, "updated_at": time.time()}
    )

    if entry["used"] >= IMAGE_FREE_LIMIT:
        return False, 0, effective_id

    entry["used"] += 1
    entry["updated_at"] = time.time()
    remaining = max(0, IMAGE_FREE_LIMIT - entry["used"])
    return True, remaining, effective_id


def refund_user_image_quota(user_id_or_effective_id: Any) -> None:
    """Refunds 1 image credit if upstream model inference fails."""
    effective_id = resolve_effective_identity(user_id_or_effective_id)
    if effective_id in _in_memory_quotas:
        entry = _in_memory_quotas[effective_id]
        if entry["used"] > 0:
            entry["used"] -= 1
            entry["updated_at"] = time.time()


def generate_telegram_link_code(web_user_id: Any, ttl_seconds: int = 600) -> str:
    """Generates an ephemeral, single-use 6-character link code for Web-Telegram sync."""
    code = secrets.token_hex(3).upper()  # 6 chars
    _in_memory_link_codes[code] = {
        "web_user_id": str(web_user_id).strip(),
        "expires_at": time.time() + ttl_seconds
    }
    return code


def link_telegram_to_web_account(telegram_id: Any, link_code: str) -> Tuple[bool, str]:
    """Links Telegram user to Web account via single-use code."""
    clean_code = link_code.strip().upper()
    record = _in_memory_link_codes.get(clean_code)

    if not record:
        return False, "Invalid link code."
    if time.time() > record["expires_at"]:
        _in_memory_link_codes.pop(clean_code, None)
        return False, "Link code has expired."

    web_user_id = record["web_user_id"]
    tg_str = str(telegram_id).strip()

    # Link accounts
    _in_memory_user_links[tg_str] = web_user_id
    # Single use -> consume code
    _in_memory_link_codes.pop(clean_code, None)

    # Sync quotas: merge any used counts (max of both)
    tg_used = _in_memory_quotas.get(tg_str, {}).get("used", 0)
    web_entry = _in_memory_quotas.setdefault(
        web_user_id,
        {"used": 0, "limit": IMAGE_FREE_LIMIT, "updated_at": time.time()}
    )
    web_entry["used"] = max(web_entry["used"], tg_used)

    return True, web_user_id
