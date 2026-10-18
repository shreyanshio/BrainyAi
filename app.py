"""Brainy-AI REST API & Web Sanctuary Gateway.
Provides session authorization, cross-origin security headers, and AI proxy routing.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import os
import re
import uuid
import hmac
import hashlib
import json
import urllib.parse
import random
import logging
import time
import threading
import requests
from datetime import datetime, timezone, timedelta
from html import escape
from functools import wraps
from flask import Flask, request, jsonify, session, send_from_directory, redirect, Response, stream_with_context, g, has_request_context
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import AI + Supabase helpers from study_bot (same Supabase project the Telegram bot uses)
import study_bot

# Security module — input sanitization, rate limiting, blacklist, headers, token auth
from security import (
    security_guard, login_required, sanitize_input,
    is_blacklisted, check_rate_limit, rate_limit_retry_after, log_security_event, security_headers,
    create_auth_token, verify_auth_token, _get_auth_secret_key, RateLimitStoreUnavailable
)
from security import _is_production

app = Flask(__name__)

DEFAULT_ALLOWED_ORIGINS = [
    "https://brainyai.cenai.workers.dev",
    "https://brainy.cenai.workers.dev",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
]

_custom_origins = os.getenv("ALLOWED_ORIGINS")
if _custom_origins:
    for o in _custom_origins.split(","):
        clean_o = o.strip()
        if clean_o and clean_o not in DEFAULT_ALLOWED_ORIGINS:
            DEFAULT_ALLOWED_ORIGINS.append(clean_o)

CORS(
    app,
    supports_credentials=True,
    origins=DEFAULT_ALLOWED_ORIGINS,
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
    expose_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
)

# Persistent, synchronized secret key for sessions and tokens
app.secret_key = _get_auth_secret_key()
_secret_key = app.secret_key
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "None")
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "True").lower() == "true"
app.config["PERMANENT_SESSION_LIFETIME"] = 86400  # 24 hours


# ── ADMIN ACCESS CONTROL ──
# Admins are whoever is already logged in AND matches one of these
# allowlists: user_id, username, or (for Google logins) verified email.
# The email check is the strongest one — it's tied to the verified email
# Google Identity Services returns, not something a user can self-report.
# Override/extend via ADMIN_USER_IDS, ADMIN_USERNAMES, ADMIN_EMAILS env vars.
DEFAULT_ADMIN_EMAILS = {"shreyansh101008@gmail.com"}

def _parse_admin_allowlist():
    ids = set()
    for part in os.environ.get("ADMIN_USER_IDS", "").split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    names = set()
    for part in os.environ.get("ADMIN_USERNAMES", "").split(","):
        part = part.strip().lstrip("@").lower()
        if part:
            names.add(part)
    emails = set(DEFAULT_ADMIN_EMAILS)
    for part in os.environ.get("ADMIN_EMAILS", "").split(","):
        part = part.strip().lower()
        if part:
            emails.add(part)
    return ids, names, emails

ADMIN_USER_IDS, ADMIN_USERNAMES, ADMIN_EMAILS = _parse_admin_allowlist()


def is_admin_session() -> bool:
    uid = session.get("user_id")
    uname = (session.get("username") or "").lstrip("@").lower()
    email = (session.get("email") or "").strip().lower()
    if uid is not None and uid in ADMIN_USER_IDS:
        return True
    if uname and uname in ADMIN_USERNAMES:
        return True
    if email and email in ADMIN_EMAILS:
        return True
    return False


def admin_required(f):
    """Decorator: strictly enforce authenticated administrator access.
    Supports both Authorization: Bearer <token> and verified Flask session cookies.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 1. Check Bearer token from Authorization header if session not yet set
        if "user_id" not in session:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
                payload = verify_auth_token(token)
                if payload and payload.get("sub"):
                    session["user_id"] = payload["sub"]
                    session["username"] = payload.get("username", "")
                    session["first_name"] = payload.get("name", "Admin")
                    session["email"] = payload.get("email", "")
                    session["role"] = payload.get("role", "")

        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        if not is_admin_session():
            return jsonify({"error": "Forbidden - Administrator access required"}), 403
        return f(*args, **kwargs)
    return decorated

@app.after_request
def apply_security_headers(response):
    return security_headers(response)


# ── GLOBAL ERROR HANDLERS ──
# Flask's default error pages are HTML. The frontend always does
# `response.json()` on API calls — an HTML error page makes that throw a
# JSON-parse error instead of the actual message, and shows up as a
# confusing "Network error" toast. These force every error path to return
# JSON so the frontend's existing apiRequest/error handling works correctly.

@app.errorhandler(404)
def handle_404(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return e  # let static/frontend routes fall through normally

@app.errorhandler(500)
def handle_500(e):
    log_security_event("server_error", request.remote_addr or "unknown", session.get("user_id"), str(e)[:200])
    return jsonify({"error": "Something went wrong on our end. Please try again."}), 500

@app.errorhandler(Exception)
def handle_uncaught(e):
   
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    log_security_event("uncaught_exception", request.remote_addr or "unknown", session.get("user_id"), type(e).__name__)
    return jsonify({"error": "Unexpected error. Please try again."}), 500

SUPABASE_URL = (os.getenv("SUPABASE_URL") or study_bot.SUPABASE_URL or "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY") or study_bot.SUPABASE_KEY


def _supabase_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


_CHAT_SUMMARY_SCHEMA_AVAILABLE: bool | None = None


def _require_supabase_in_production() -> None:
    if _is_production() and not _supabase_configured():
        raise SupabaseOperationError("Supabase credentials are not configured")


@app.route("/api/health", methods=["GET"])
def api_health():
    """Public liveness check with a credential-free Supabase connectivity status."""
    database_status = "unconfigured"
    latency_ms = None
    if _supabase_configured():
        started = time.perf_counter()
        try:
            _sb_request("GET", "chat_sessions", params="?select=id&limit=1", timeout=5)
            database_status = "connected"
        except SupabaseOperationError:
            database_status = "unavailable"
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
    healthy = database_status == "connected"
    return jsonify({
        "status": "healthy" if healthy else "degraded",
        "database": {"status": database_status, "latency_ms": latency_ms},
    }), 200


def _memory_storage_error(exc: Exception):
    """Return a safe retryable response when per-user memory persistence fails."""
    logger.error("User memory operation failed request_id=%s category=%s",
        getattr(g, "request_id", ""), type(exc).__name__)
    return jsonify({
        "error": "Your saved profile is temporarily unavailable. Please retry.",
        "code": "MEMORY_STORAGE_UNAVAILABLE",
        "retryable": True,
        "request_id": getattr(g, "request_id", None),
    }), 503

# ── SECURE HASH ENCRYPTION FOR CHAT TITLES & USER QUESTIONS ──
# Prevents sensitive user questions and chat titles from leaking if the Supabase database is dumped
import base64

def mask_secure_hash(text: str) -> str:
    """Encrypt and format plain text into a secure hash-encoded representation for Supabase storage."""
    if not text:
        return text
    salt = os.urandom(16)
    secret = _get_auth_secret_key()
    key = hashlib.pbkdf2_hmac('sha256', secret.encode('utf-8'), salt, 50000, dklen=32)
    text_bytes = text.encode('utf-8')
    keystream = bytearray()
    counter = 0
    while len(keystream) < len(text_bytes):
        keystream.extend(hmac.new(key, counter.to_bytes(4, 'big'), hashlib.sha256).digest())
        counter += 1
    ciphertext = bytes(a ^ b for a, b in zip(text_bytes, keystream[:len(text_bytes)]))
    mac = hmac.new(key, ciphertext, hashlib.sha256).digest()[:16]
    encoded = base64.urlsafe_b64encode(salt + mac + ciphertext).decode('ascii')
    return f"hsh_v1_{encoded}"

def unmask_secure_hash(stored_val: str) -> str:
    """Decrypt a masked hash string from Supabase back to readable text for authorized sessions."""
    if not stored_val or not isinstance(stored_val, str) or not stored_val.startswith("hsh_v1_"):
        return stored_val
    try:
        raw = base64.b64decode(stored_val[7:].encode('ascii'), altchars=b'-_', validate=True)
        if len(raw) < 32:
            raise ValueError("invalid encrypted content length")
        salt = raw[:16]
        mac = raw[16:32]
        ciphertext = raw[32:]
        # Keep the active key first. A previous key is optional and exists only
        # to support a deliberate Railway key rotation without losing old chats.
        candidate_secrets = [_get_auth_secret_key()]
        previous_secrets = [value.strip() for value in os.getenv("CHAT_ENCRYPTION_PREVIOUS_KEYS", "").split(",") if value.strip()]
        previous_secret = os.getenv("CHAT_ENCRYPTION_PREVIOUS_KEY", "").strip()
        if previous_secret:
            previous_secrets.append(previous_secret)
        candidate_secrets.extend(secret for secret in previous_secrets if secret not in candidate_secrets)
        for secret in candidate_secrets:
            key = hashlib.pbkdf2_hmac('sha256', secret.encode('utf-8'), salt, 50000, dklen=32)
            expected_mac = hmac.new(key, ciphertext, hashlib.sha256).digest()[:16]
            if not hmac.compare_digest(mac, expected_mac):
                continue
            keystream = bytearray()
            counter = 0
            while len(keystream) < len(ciphertext):
                keystream.extend(hmac.new(key, counter.to_bytes(4, 'big'), hashlib.sha256).digest())
                counter += 1
            plain_bytes = bytes(a ^ b for a, b in zip(ciphertext, keystream[:len(ciphertext)]))
            return plain_bytes.decode('utf-8')
        raise StoredChatContentUnavailable("Stored chat content could not be decrypted")
    except StoredChatContentUnavailable:
        raise
    except Exception as exc:
        # Never return the encrypted payload to the user or send it to a model.
        logger.warning("Stored chat content could not be decoded category=%s", type(exc).__name__)
        raise StoredChatContentUnavailable("Stored chat content could not be decrypted") from exc

# ── GLOBAL USER MESSAGE QUOTA: 30 MESSAGES PER 5 HOURS ──
GLOBAL_MESSAGE_LIMIT = 30
QUOTA_WINDOW_HOURS = 5

_dev_user_quotas: dict = {}
_dev_quota_lock = threading.RLock()

def _dev_get_quota(user_id: int | str) -> dict:
    with _dev_quota_lock:
        uid = str(user_id)
        now = datetime.now(timezone.utc)
        record = _dev_user_quotas.get(uid)
        if record:
            try:
                reset_at = datetime.fromisoformat(record["reset_at"])
                if reset_at.tzinfo is None:
                    reset_at = reset_at.replace(tzinfo=timezone.utc)
                if now >= reset_at:
                    record = {
                        "used": 0,
                        "reset_at": (now + timedelta(hours=QUOTA_WINDOW_HOURS)).isoformat(),
                        "window_start": now.isoformat()
                    }
                    _dev_user_quotas[uid] = record
            except Exception:
                record = {
                    "used": 0,
                    "reset_at": (now + timedelta(hours=QUOTA_WINDOW_HOURS)).isoformat(),
                    "window_start": now.isoformat()
                }
                _dev_user_quotas[uid] = record
        else:
            record = {
                "used": 0,
                "reset_at": (now + timedelta(hours=QUOTA_WINDOW_HOURS)).isoformat(),
                "window_start": now.isoformat()
            }
            _dev_user_quotas[uid] = record
        used = record["used"]
        return {
            "used": used,
            "remaining": max(0, GLOBAL_MESSAGE_LIMIT - used),
            "reset_at": record["reset_at"],
            "window_hours": QUOTA_WINDOW_HOURS,
            "limit": GLOBAL_MESSAGE_LIMIT
        }

def _dev_consume_quota(user_id: int | str) -> tuple[bool, dict]:
    with _dev_quota_lock:
        status = _dev_get_quota(user_id)
        if status["used"] >= GLOBAL_MESSAGE_LIMIT:
            return False, status
        _dev_user_quotas[str(user_id)]["used"] += 1
        return True, _dev_get_quota(user_id)

def _dev_refund_quota(user_id: int | str) -> dict:
    with _dev_quota_lock:
        uid = str(user_id)
        if uid in _dev_user_quotas and _dev_user_quotas[uid]["used"] > 0:
            _dev_user_quotas[uid]["used"] -= 1
        return _dev_get_quota(user_id)

def _quota_rpc(name: str, body: dict) -> dict:
    response = _sb_request("POST", f"rpc/{name}", json_body=body, timeout=5)
    try:
        value = response.json()
    except ValueError as exc:
        raise SupabaseOperationError(f"Quota RPC {name} returned malformed JSON") from exc
    if not isinstance(value, dict):
        raise SupabaseOperationError(f"Quota RPC {name} returned an unexpected response")
    return value

def get_user_quota(user_id: int | str) -> dict:
    """Read or initialize quota state using the shared atomic Supabase store."""
    if not (SUPABASE_URL and SUPABASE_KEY):
        _require_supabase_in_production()
        logger.warning("Supabase unconfigured; using local development quota fallback")
        return _dev_get_quota(user_id)
    try:
        status = _quota_rpc("brainy_get_user_quota", {"p_user_id": int(user_id),
            "p_limit": GLOBAL_MESSAGE_LIMIT, "p_window_hours": QUOTA_WINDOW_HOURS})
        return {**status, "limit": GLOBAL_MESSAGE_LIMIT, "window_hours": QUOTA_WINDOW_HOURS}
    except SupabaseOperationError:
        try:
            now = datetime.now(timezone.utc)
            rows = _sb_json(_sb_request("GET", "user_quotas", params=f"?user_id=eq.{user_id}"), "user_quotas")
            if rows:
                row = rows[0]
                reset_at = datetime.fromisoformat(row["reset_at"].replace("Z", "+00:00"))
                if reset_at.tzinfo is None:
                    reset_at = reset_at.replace(tzinfo=timezone.utc)
                if now >= reset_at:
                    new_reset = (now + timedelta(hours=QUOTA_WINDOW_HOURS)).isoformat()
                    _sb_request("PATCH", "user_quotas", params=f"?user_id=eq.{user_id}",
                                json_body={"used": 0, "window_start": now.isoformat(), "reset_at": new_reset, "updated_at": now.isoformat()})
                    return {"used": 0, "remaining": GLOBAL_MESSAGE_LIMIT, "reset_at": new_reset, "limit": GLOBAL_MESSAGE_LIMIT, "window_hours": QUOTA_WINDOW_HOURS}
                used = row.get("used", 0)
                return {"used": used, "remaining": max(0, GLOBAL_MESSAGE_LIMIT - used), "reset_at": row["reset_at"], "limit": GLOBAL_MESSAGE_LIMIT, "window_hours": QUOTA_WINDOW_HOURS}
            else:
                new_reset = (now + timedelta(hours=QUOTA_WINDOW_HOURS)).isoformat()
                _sb_request("POST", "user_quotas", json_body={"user_id": int(user_id), "used": 0, "window_start": now.isoformat(), "reset_at": new_reset, "updated_at": now.isoformat()})
                return {"used": 0, "remaining": GLOBAL_MESSAGE_LIMIT, "reset_at": new_reset, "limit": GLOBAL_MESSAGE_LIMIT, "window_hours": QUOTA_WINDOW_HOURS}
        except Exception:
            raise

def consume_user_quota(user_id: int | str) -> tuple[bool, dict]:
    """Atomically consume a credit across workers and return current usage."""
    if not (SUPABASE_URL and SUPABASE_KEY):
        _require_supabase_in_production()
        logger.warning("Supabase unconfigured; using local development quota fallback")
        return _dev_consume_quota(user_id)
    try:
        status = _quota_rpc("brainy_consume_user_quota", {
            "p_user_id": int(user_id), "p_limit": GLOBAL_MESSAGE_LIMIT,
            "p_window_hours": QUOTA_WINDOW_HOURS,
        })
        status.update({"limit": GLOBAL_MESSAGE_LIMIT, "window_hours": QUOTA_WINDOW_HOURS})
        return bool(status.pop("allowed", False)), status
    except SupabaseOperationError:
        # A read/modify/write fallback is not atomic across application workers.
        # Fail closed instead of allowing concurrent requests to exceed quota.
        logger.exception("Atomic quota store unavailable user_id=%s", user_id)
        raise

def refund_user_quota(user_id: int | str) -> dict:
    """Refund one previously consumed credit after a pre-generation failure."""
    if not (SUPABASE_URL and SUPABASE_KEY):
        _require_supabase_in_production()
        logger.warning("Supabase unconfigured; using local development quota fallback")
        return _dev_refund_quota(user_id)
    try:
        status = _quota_rpc("brainy_refund_user_quota", {"p_user_id": int(user_id),
            "p_limit": GLOBAL_MESSAGE_LIMIT, "p_window_hours": QUOTA_WINDOW_HOURS})
        return {**status, "limit": GLOBAL_MESSAGE_LIMIT, "window_hours": QUOTA_WINDOW_HOURS}
    except SupabaseOperationError:
        # Refunds must use the same atomic quota row operation as consumption.
        # A failed refund can conservatively leave a credit consumed; it must
        # never decrement another concurrent request's usage.
        logger.exception("Atomic quota refund unavailable user_id=%s", user_id)
        raise


# ── SUSPENDED USERS MANAGEMENT ──
SUSPENDED_USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "suspended_users.json")
_suspended_users = set()
_suspend_lock = threading.Lock()

def _load_suspended_users():
    global _suspended_users
    if os.path.exists(SUSPENDED_USERS_FILE):
        try:
            with open(SUSPENDED_USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                _suspended_users = set(int(uid) for uid in data)
        except Exception as e:
            logger.warning("Error loading suspended users: %s", e)

def _save_suspended_users():
    try:
        with open(SUSPENDED_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(_suspended_users), f)
    except Exception as e:
        logger.warning("Error saving suspended users: %s", e)

_load_suspended_users()

def is_user_suspended(user_id: int | str) -> bool:
    try:
        uid = int(user_id)
        with _suspend_lock:
            return uid in _suspended_users
    except Exception:
        return False

MODELS_CATALOG = [
    {
        "id": "brainy-balanced",
        "name": "Brainy Balanced",
        "tagline": "All-round concept learning",
        "description": "Balanced speed and depth for everyday study questions, explanations, and doubts.",
        "badge": "Default",
        "recommendedFor": "General study & concept clarity"
    },
    {
        "id": "brainy-fast",
        "name": "Brainy Fast",
        "tagline": "Speedrun & flash review",
        "description": "Instant, concise answers optimized for rapid memorization and quick formula checks.",
        "badge": "Fast",
        "recommendedFor": "Quick definitions & flashcard review"
    },
    {
        "id": "brainy-reasoning",
        "name": "Brainy Reasoning",
        "tagline": "Deep academic derivations",
        "description": "Step-by-step mathematical proofs, multi-stage logic, and rigorous scientific explanations.",
        "badge": "Deep",
        "recommendedFor": "Math, Physics & complex proofs"
    },
    {
        "id": "brainy-coding",
        "name": "Brainy Code",
        "tagline": "Programming & logic",
        "description": "Clean syntax, algorithmic decomposition, memory optimization, and line-by-line debugging.",
        "badge": "Technical",
        "recommendedFor": "Coding, data structures & debugging"
    },
    {
        "id": "brainy-exam",
        "name": "Brainy Exam Prep",
        "tagline": "Exam strategy & marking schemes",
        "description": "Focuses on high-yield exam traps, marking rubrics, structured answers, and practice questions.",
        "badge": "Exam",
        "recommendedFor": "Exam revision & high-yield practice"
    }
]


def format_for_web(text: str) -> str:
    """
    Light-touch formatting applied ONLY to what the web app displays (never
    touches what's stored in Supabase or sent to Telegram). clean_response()
    already handles code blocks / Unicode bold / italics fine on web thanks
    to the .message-bubble { white-space: pre-wrap } CSS rule — this just
    upgrades plain "- item" / "* item" markdown-style bullets into a real
    bullet character so lists don't look like stray dashes in the chat UI.
    """
    if not text:
        return text
    return re.sub(r'^[ \t]*[-*][ \t]+', '• ', text, flags=re.MULTILINE)


# In-memory browser auth handshake sessions (short-lived, just for the login flow):
auth_sessions = study_bot.AUTH_SESSIONS
share_links = {}


# ── IN-MEMORY FALLBACK CACHES ──
# Ensures the web app ALWAYS works seamlessly even if Supabase has network hiccups
MEM_SESSIONS = {}  # { user_id: [ { id, title, created_at } ] }
MEM_MESSAGES = {}  # { session_id: [ { role, content, created_at } ] }
MEM_LOGINS = []    # [ { user_id, username, first_name, login_type, ip_address, created_at } ]


# ── SUPABASE HELPERS (chat_sessions / chat_messages / user_logins) ──

def _sb_headers(prefer: str | None = None) -> dict:
    headers = {"apikey": SUPABASE_KEY, "Content-Type": "application/json"}
    # Supabase's newer sb_secret_* keys are API keys, not JWTs; sending one as
    # a Bearer token fails JWT validation. Legacy service_role JWTs need both.
    if not SUPABASE_KEY.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {SUPABASE_KEY}"
    if prefer:
        headers["Prefer"] = prefer
    return headers


class SupabaseOperationError(RuntimeError):
    """A configured Supabase operation failed; never treat it as empty data."""


class SupabaseSchemaUnavailable(SupabaseOperationError):
    """An additive optional database migration has not been applied yet."""


class StoredChatContentUnavailable(SupabaseOperationError):
    """Encrypted historical text needs its original key before it can be shown or used."""


@app.errorhandler(SupabaseOperationError)
def handle_supabase_operation_error(exc):
    """Return a safe, consistent response for a failed Supabase operation."""
    request_id = getattr(g, "request_id", None)
    logger.error("Supabase operation failed request_id=%s category=%s",
        request_id or "", type(exc).__name__)
    return jsonify({
        "error": "Database service is temporarily unavailable. Please retry.",
        "code": "SUPABASE_UNAVAILABLE",
        "retryable": True,
        "request_id": request_id,
    }), 503


def _sb_request(method: str, table: str, *, params: str = "", json_body=None,
                prefer: str | None = None, timeout: int = 8):
    if not (SUPABASE_URL and SUPABASE_KEY):
        raise SupabaseOperationError("Supabase is not configured")
    try:
        response = requests.request(method, f"{SUPABASE_URL}/rest/v1/{table}{params}",
            headers=_sb_headers(prefer), json=json_body, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        upstream = getattr(exc, "response", None)
        logger.error("Supabase failure operation=%s table=%s status=%s request_id=%s category=%s",
            method.lower(), table, getattr(upstream, "status_code", None) or "network",
            upstream.headers.get("sb-request-id", "") if upstream is not None else "",
            type(exc).__name__)
        if upstream is not None and upstream.status_code == 400:
            try:
                error_body = upstream.json()
            except (ValueError, AttributeError):
                error_body = {}
            code = str(error_body.get("code", "")) if isinstance(error_body, dict) else ""
            message = str(error_body.get("message", "")).lower() if isinstance(error_body, dict) else ""
            if code in {"42703", "PGRST204"} or ("column" in message and ("does not exist" in message or "could not find" in message)):
                raise SupabaseSchemaUnavailable("An optional chat summary migration is not installed") from exc
        raise SupabaseOperationError(f"Supabase {method.lower()} {table} failed") from exc


def _sb_json(response, table: str):
    try:
        rows = response.json()
    except ValueError as exc:
        raise SupabaseOperationError(f"Supabase returned malformed JSON for {table}") from exc
    if not isinstance(rows, list):
        raise SupabaseOperationError(f"Supabase returned an unexpected response for {table}")
    return rows


def sb_record_login(user_id: int, username: str, first_name: str, login_type: str = "web", ip: str = "", user_agent: str = "") -> None:
    """Record user login event in Supabase user_logins table and in-memory queue fallback."""
    login_entry = {
        "user_id": user_id,
        "username": username or "",
        "first_name": first_name or "",
        "login_type": login_type,
        "ip_address": ip or "",
        "user_agent": user_agent[:250] if user_agent else "",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    MEM_LOGINS.append(login_entry)
    if len(MEM_LOGINS) > 2000:
        del MEM_LOGINS[:-2000]

    if not (SUPABASE_URL and SUPABASE_KEY):
        return

    payload = {
        "user_id": user_id,
        "username": username or "",
        "first_name": first_name or "",
        "login_type": login_type,
        "ip_address": ip or "",
        "user_agent": user_agent[:250] if user_agent else ""
    }
    try:
        _sb_request("POST", "user_logins", json_body=payload, prefer="return=minimal", timeout=5)
    except Exception as exc:
        logger.warning("Supabase record login failed user_id=%s category=%s", user_id, type(exc).__name__)


def sb_list_sessions(user_id: int, view: str = "recent", limit: int = 100, offset: int = 0) -> list:
    if not isinstance(limit, int) or not 1 <= limit <= 101:
        raise ValueError("Conversation page size is invalid")
    if not isinstance(offset, int) or offset < 0:
        raise ValueError("Conversation page offset must be zero or greater")
    view_filters = {
        "all": "",
        "recent": "&is_archived=eq.false",
        "saved": "&is_saved=eq.true&is_archived=eq.false",
        "pinned": "&is_pinned=eq.true&is_archived=eq.false",
        "archived": "&is_archived=eq.true",
    }
    if view not in view_filters:
        raise ValueError("Unsupported conversation view")
    if not (SUPABASE_URL and SUPABASE_KEY):
        _require_supabase_in_production()
        logger.warning("Supabase unconfigured; using in-memory sessions for dev")
        rows = list(MEM_SESSIONS.get(user_id, []))
        if view == "all":
            pass
        elif view == "recent":
            rows = [r for r in rows if not r.get("is_archived", False)]
        elif view == "saved":
            rows = [r for r in rows if r.get("is_saved", False) and not r.get("is_archived", False)]
        elif view == "pinned":
            rows = [r for r in rows if r.get("is_pinned", False) and not r.get("is_archived", False)]
        else:
            rows = [r for r in rows if r.get("is_archived", False)]
        return rows[offset:offset + limit]
    try:
        rows = _sb_json(_sb_request("GET", "chat_sessions",
            params=(f"?user_id=eq.{user_id}&select=id,title,created_at,updated_at,last_message_at,is_saved,is_pinned,is_archived"
                    f"{view_filters[view]}&order=is_pinned.desc,last_message_at.desc.nullslast,created_at.desc"
                    f"&limit={limit}&offset={offset}")), "chat_sessions")
    except SupabaseSchemaUnavailable:
        logger.warning("Expanded session columns unavailable; falling back to legacy chat_sessions schema user_id=%s", user_id)
        rows = _sb_json(_sb_request("GET", "chat_sessions",
            params=f"?user_id=eq.{user_id}&select=id,title,created_at&order=created_at.desc&limit={limit}&offset={offset}"),
            "chat_sessions")
        for r in rows:
            r.setdefault("updated_at", r.get("created_at"))
            r.setdefault("last_message_at", r.get("created_at"))
            r.setdefault("is_saved", False)
            r.setdefault("is_pinned", False)
            r.setdefault("is_archived", False)
    for row in rows:
        if row.get("title"):
            try:
                row["title"] = unmask_secure_hash(row["title"])
            except StoredChatContentUnavailable:
                row["title"] = "Study Session"
    return rows


def sb_create_session(user_id: int, title: str, session_id: str | None = None) -> dict:
    if not session_id:
        session_id = str(uuid.uuid4())
    sess_obj = {"id": session_id, "user_id": user_id, "title": title, "created_at": datetime.now(timezone.utc).isoformat()}
    if not (SUPABASE_URL and SUPABASE_KEY):
        _require_supabase_in_production()
        logger.warning("Supabase unconfigured; using in-memory session for dev")
        MEM_SESSIONS.setdefault(user_id, []).insert(0, sess_obj)
        return sess_obj

    # Hash title before saving in Supabase so plain title never leaks
    payload = {"id": session_id, "user_id": user_id, "title": mask_secure_hash(title)}

    rows = _sb_json(_sb_request("POST", "chat_sessions", json_body=payload,
        prefer="return=representation"), "chat_sessions")
    if not rows or not rows[0].get("id"):
        raise SupabaseOperationError("Supabase did not confirm session creation")
    created = rows[0]
    try:
        created["title"] = unmask_secure_hash(created.get("title", title))
    except StoredChatContentUnavailable:
        created["title"] = title
    MEM_SESSIONS.setdefault(user_id, []).insert(0, created)
    return created


def sb_get_session(session_id: str, user_id: int) -> dict | None:
    global _CHAT_SUMMARY_SCHEMA_AVAILABLE
    if not (SUPABASE_URL and SUPABASE_KEY):
        _require_supabase_in_production()
        _CHAT_SUMMARY_SCHEMA_AVAILABLE = False
        for s in MEM_SESSIONS.get(user_id, []):
            if s.get("id") == session_id:
                return s
        return None
    summary_columns = "context_summary,summary_through_message_id,summary_updated_at"
    if _CHAT_SUMMARY_SCHEMA_AVAILABLE is not False:
        try:
            rows = _sb_json(_sb_request("GET", "chat_sessions",
                params=f"?id=eq.{session_id}&user_id=eq.{user_id}&select=id,title,user_id,{summary_columns}"), "chat_sessions")
            _CHAT_SUMMARY_SCHEMA_AVAILABLE = True
        except SupabaseSchemaUnavailable:
            _CHAT_SUMMARY_SCHEMA_AVAILABLE = False
            rows = _sb_json(_sb_request("GET", "chat_sessions",
                params=f"?id=eq.{session_id}&user_id=eq.{user_id}&select=id,title,user_id"), "chat_sessions")
    else:
        rows = _sb_json(_sb_request("GET", "chat_sessions",
            params=f"?id=eq.{session_id}&user_id=eq.{user_id}&select=id,title,user_id"), "chat_sessions")
    if not rows:
        return None
    row = rows[0]
    try:
        row["title"] = unmask_secure_hash(row.get("title", ""))
    except StoredChatContentUnavailable:
        row["title"] = "Study Session"
    if row.get("context_summary"):
        try:
            row["context_summary"] = unmask_secure_hash(row["context_summary"])
        except StoredChatContentUnavailable:
            row["context_summary"] = ""
    return row


def sb_get_messages_after(session_id: str, user_id: int, after_id: int = 0, limit: int = 65) -> list:
    """Read a bounded chronological slice after a persisted conversation summary."""
    if not (SUPABASE_URL and SUPABASE_KEY):
        _require_supabase_in_production()
        return []
    if after_id < 0 or not 1 <= limit <= 100:
        raise ValueError("Invalid summary message cursor")
    rows = _sb_json(_sb_request("GET", "chat_messages",
        params=(f"?session_id=eq.{session_id}&user_id=eq.{int(user_id)}&id=gt.{int(after_id)}"
                f"&select=id,role,content,created_at&order=id.asc&limit={int(limit)}")), "chat_messages")
    for row in rows:
        if row.get("content"):
            try:
                row["content"] = unmask_secure_hash(row["content"])
            except StoredChatContentUnavailable:
                row["content"] = "[Encrypted message from previous session]"
    return rows


def sb_update_session_summary(session_id: str, user_id: int, summary: str, through_message_id: int,
                              expected_previous_id: int | None = None) -> bool:
    """Persist an encrypted rolling summary without changing any existing chat rows."""
    global _CHAT_SUMMARY_SCHEMA_AVAILABLE
    if _CHAT_SUMMARY_SCHEMA_AVAILABLE is False:
        return False
    compare_cursor = "summary_through_message_id=is.null" if expected_previous_id is None else f"summary_through_message_id=eq.{int(expected_previous_id)}"
    rows = _sb_json(_sb_request("PATCH", "chat_sessions",
        params=f"?id=eq.{session_id}&user_id=eq.{int(user_id)}&{compare_cursor}",
        json_body={
            "context_summary": mask_secure_hash(summary),
            "summary_through_message_id": int(through_message_id),
            "summary_updated_at": datetime.now(timezone.utc).isoformat(),
        }, prefer="return=representation"), "chat_sessions")
    if not rows:
        # Another worker advanced the summary cursor, or the owner removed the
        # conversation. Leave the authoritative row untouched.
        return False
    _CHAT_SUMMARY_SCHEMA_AVAILABLE = True
    return True


_summary_workers_lock = threading.Lock()
_summary_worker_locks: dict[tuple[str, int], threading.Lock] = {}


def _refresh_chat_summary(session_id: str, user_id: int, worker_lock: threading.Lock) -> None:
    """Compress old turns in the background so summary work never delays a reply."""
    try:
        for _ in range(4):
            owner_session = sb_get_session(session_id, user_id)
            if not owner_session:
                return
            if not owner_session.get("context_summary") and _CHAT_SUMMARY_SCHEMA_AVAILABLE is not True:
                return
            summary = owner_session.get("context_summary") or ""
            previous_cursor = owner_session.get("summary_through_message_id")
            through_id = int(previous_cursor or 0)
            pending = sb_get_messages_after(session_id, user_id, through_id, limit=65)
            if len(pending) <= 40:
                return

            # Preserve the latest 24 unsummarized messages verbatim in each model
            # context. Summarize a bounded earlier batch and advance the cursor
            # only through messages included in full.
            batch_limit = min(len(pending) - 24, 40)
            selected = []
            source_chars = 0
            for message in pending[:batch_limit]:
                line_size = len(message.get("content") or "") + 20
                if source_chars + line_size > 30000:
                    break
                selected.append(message)
                source_chars += line_size
            if not selected:
                return

            prior = f"Existing summary of older turns:\n{summary[:12000]}\n\n" if summary else ""
            transcript = "\n".join(
                f"{message['role']}: {message.get('content', '')}" for message in selected
            )
            summary_prompt = (
                prior
                + "Summarize the following earlier turns from one private study chat for future continuity. "
                "Retain concrete facts, names, goals, chosen options, constraints, definitions, unresolved "
                "questions, and references such as 'the second feature'. Do not invent details. Keep it concise.\n\n"
                + transcript
            )
            updated_summary = study_bot.ai_call(
                [{"role": "user", "content": summary_prompt}],
                "You create accurate, compact conversation memory. Preserve important details and uncertainty.",
                1200,
            )
            updated_summary = study_bot.clean_response(updated_summary or "").strip()
            if not updated_summary:
                return
            if not sb_update_session_summary(
                session_id,
                user_id,
                updated_summary[:16000],
                int(selected[-1]["id"]),
                expected_previous_id=int(previous_cursor) if previous_cursor is not None else None,
            ):
                return
    except Exception as exc:
        logger.warning("Chat summary refresh failed category=%s", type(exc).__name__)
    finally:
        worker_lock.release()
        with _summary_workers_lock:
            if _summary_worker_locks.get((session_id, user_id)) is worker_lock:
                _summary_worker_locks.pop((session_id, user_id), None)


def _schedule_chat_summary(session_id: str, user_id: int) -> None:
    """Schedule at most one summary worker per owned conversation."""
    if not _supabase_configured() or _CHAT_SUMMARY_SCHEMA_AVAILABLE is not True:
        return
    key = (session_id, int(user_id))
    with _summary_workers_lock:
        worker_lock = _summary_worker_locks.setdefault(key, threading.Lock())
        if not worker_lock.acquire(blocking=False):
            return
    try:
        threading.Thread(
            target=_refresh_chat_summary,
            args=(session_id, int(user_id), worker_lock),
            name="chat-summary-refresh",
            daemon=True,
        ).start()
    except RuntimeError as exc:
        worker_lock.release()
        with _summary_workers_lock:
            if _summary_worker_locks.get(key) is worker_lock:
                _summary_worker_locks.pop(key, None)
        logger.warning("Chat summary worker could not start category=%s", type(exc).__name__)


def sb_rename_session(session_id: str, user_id: int, title: str) -> None:
    if not (SUPABASE_URL and SUPABASE_KEY):
        _require_supabase_in_production()
        for s in MEM_SESSIONS.get(user_id, []):
            if s["id"] == session_id:
                s["title"] = title
        return
    rows = _sb_json(_sb_request("PATCH", "chat_sessions",
        params=f"?id=eq.{session_id}&user_id=eq.{user_id}",
        json_body={"title": mask_secure_hash(title)}, prefer="return=representation"), "chat_sessions")
    if not rows:
        raise SupabaseOperationError("Session was not found or could not be renamed")
    for s in MEM_SESSIONS.get(user_id, []):
        if s["id"] == session_id:
            s["title"] = title


def sb_update_session_metadata(session_id: str, user_id: int, changes: dict) -> dict:
    allowed = {"is_saved", "is_pinned", "is_archived"}
    if not changes or set(changes) - allowed or any(not isinstance(v, bool) for v in changes.values()):
        raise ValueError("Invalid conversation metadata")
    if not (SUPABASE_URL and SUPABASE_KEY):
        _require_supabase_in_production()
        for row in MEM_SESSIONS.get(user_id, []):
            if row.get("id") == session_id:
                row.update(changes)
                return row
        raise SupabaseOperationError("Session was not found or could not be updated")
    rows = _sb_json(_sb_request("PATCH", "chat_sessions",
        params=f"?id=eq.{session_id}&user_id=eq.{int(user_id)}",
        json_body=changes, prefer="return=representation"), "chat_sessions")
    if not rows:
        raise SupabaseOperationError("Session was not found or could not be updated")
    return rows[0]


def sb_delete_session(session_id: str, user_id: int) -> None:
    if not (SUPABASE_URL and SUPABASE_KEY):
        _require_supabase_in_production()
        MEM_SESSIONS[user_id] = [s for s in MEM_SESSIONS.get(user_id, []) if s["id"] != session_id]
        MEM_MESSAGES.pop(session_id, None)
        return
    _sb_request("DELETE", "chat_sessions", params=f"?id=eq.{session_id}&user_id=eq.{user_id}")
    MEM_SESSIONS[user_id] = [s for s in MEM_SESSIONS.get(user_id, []) if s["id"] != session_id]
    MEM_MESSAGES.pop(session_id, None)


def sb_get_messages(session_id: str, user_id: int) -> list:
    if not (SUPABASE_URL and SUPABASE_KEY):
        _require_supabase_in_production()
        if not any(s.get("id") == session_id for s in MEM_SESSIONS.get(user_id, [])):
            return []
        return list(MEM_MESSAGES.get(session_id, []))
    page_size = 500
    msgs = []
    offset = 0
    try:
        while True:
            page = _sb_json(_sb_request("GET", "chat_messages",
                params=(f"?session_id=eq.{session_id}&user_id=eq.{int(user_id)}"
                        f"&select=id,role,content,created_at&order=id.asc&limit={page_size}&offset={offset}")), "chat_messages")
            msgs.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
    except SupabaseSchemaUnavailable:
        msgs = []
        offset = 0
        while True:
            page = _sb_json(_sb_request("GET", "chat_messages",
                params=(f"?session_id=eq.{session_id}"
                        f"&select=id,role,content,created_at&order=id.asc&limit={page_size}&offset={offset}")), "chat_messages")
            msgs.extend(page)
            if len(page) < page_size:
                break
            offset += page_size

    for m in msgs:
        if m.get("content"):
            try:
                m["content"] = unmask_secure_hash(m["content"])
            except StoredChatContentUnavailable:
                m["content"] = "[Encrypted message from previous session]"
    return msgs


def sb_get_recent_messages(session_id: str, limit: int | None = 15, user_id: int | None = None,
                           after_id: int | None = None) -> list:
    if not (SUPABASE_URL and SUPABASE_KEY):
        _require_supabase_in_production()
        if user_id is not None and not any(s.get("id") == session_id for s in MEM_SESSIONS.get(user_id, [])):
            return []
        all_msgs = MEM_MESSAGES.get(session_id, [])
        if after_id is not None:
            all_msgs = [message for message in all_msgs if int(message.get("id", 0)) > after_id]
        return list(all_msgs if limit is None else all_msgs[-limit:])
    if user_id is None:
        raise SupabaseOperationError("An authenticated owner is required to read chat messages")
    id_filter = f"&id=gt.{int(after_id)}" if after_id is not None else ""

    msgs = []
    try:
        if limit is None:
            page_size = 500
            offset = 0
            while True:
                page = _sb_json(_sb_request("GET", "chat_messages",
                    params=(f"?session_id=eq.{session_id}&user_id=eq.{int(user_id)}{id_filter}"
                            "&select=id,role,content,created_at"
                            f"&order=id.asc&limit={page_size}&offset={offset}")), "chat_messages")
                msgs.extend(page)
                if len(page) < page_size:
                    break
                offset += page_size
        else:
            raw_msgs = _sb_json(_sb_request("GET", "chat_messages",
                params=(f"?session_id=eq.{session_id}&user_id=eq.{int(user_id)}{id_filter}"
                        f"&select=id,role,content,created_at&order=id.desc&limit={limit}")), "chat_messages")
            msgs = list(reversed(raw_msgs))
    except SupabaseSchemaUnavailable:
        if limit is None:
            page_size = 500
            offset = 0
            while True:
                page = _sb_json(_sb_request("GET", "chat_messages",
                    params=(f"?session_id=eq.{session_id}{id_filter}"
                            "&select=id,role,content,created_at"
                            f"&order=id.asc&limit={page_size}&offset={offset}")), "chat_messages")
                msgs.extend(page)
                if len(page) < page_size:
                    break
                offset += page_size
        else:
            raw_msgs = _sb_json(_sb_request("GET", "chat_messages",
                params=(f"?session_id=eq.{session_id}{id_filter}"
                        f"&select=id,role,content,created_at&order=id.desc&limit={limit}")), "chat_messages")
            msgs = list(reversed(raw_msgs))

    for m in msgs:
        if m.get("content"):
            try:
                m["content"] = unmask_secure_hash(m["content"])
            except StoredChatContentUnavailable:
                m["content"] = "[Encrypted message from previous session]"
    return msgs


def sb_insert_message(session_id: str, role: str, content: str,
                      idempotency_key: str | None = None, user_id: int | None = None) -> None:
    msg_obj = {"role": role, "content": content, "created_at": datetime.now(timezone.utc).isoformat()}
    if idempotency_key:
        msg_obj["idempotency_key"] = idempotency_key
    if not (SUPABASE_URL and SUPABASE_KEY):
        _require_supabase_in_production()
        if user_id is not None and not any(s.get("id") == session_id for s in MEM_SESSIONS.get(user_id, [])):
            raise SupabaseOperationError("Session is not owned by the authenticated user")
        logger.warning("Supabase unconfigured; using in-memory message storage for dev")
        MEM_MESSAGES.setdefault(session_id, []).append(msg_obj)
        return
    if user_id is None:
        owner_rows = _sb_json(_sb_request("GET", "chat_sessions",
            params=f"?id=eq.{session_id}&select=user_id&limit=1"), "chat_sessions")
        if not owner_rows:
            raise SupabaseOperationError("Session was not found")
        user_id = owner_rows[0].get("user_id")
    if user_id is None:
        raise SupabaseOperationError("Session owner could not be determined")
    stored_content = mask_secure_hash(content) if role == "user" else content
    payload = {"session_id": session_id, "user_id": int(user_id), "role": role, "content": stored_content}
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key
    try:
        if idempotency_key:
            # Requires the matching session-scoped unique index in the migration.
            _sb_request("POST", "chat_messages?on_conflict=session_id,idempotency_key",
                        json_body=payload, prefer="resolution=ignore-duplicates,return=minimal")
        else:
            _sb_request("POST", "chat_messages", json_body=payload, prefer="return=minimal")
    except SupabaseSchemaUnavailable:
        fallback_payload = {"session_id": session_id, "role": role, "content": stored_content}
        _sb_request("POST", "chat_messages", json_body=fallback_payload, prefer="return=minimal")
    MEM_MESSAGES.setdefault(session_id, []).append(msg_obj)



def sb_count_user_messages(session_id: str) -> int:
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            headers = _sb_headers()
            headers["Prefer"] = "count=exact"
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/chat_messages"
                f"?session_id=eq.{session_id}&role=eq.user&select=id",
                headers=headers, timeout=8
            )
            content_range = r.headers.get("content-range", "")
            if "/" in content_range:
                return int(content_range.split("/")[-1])
        except Exception as e:
            logger.warning("Supabase count_user_messages error: %s", e)

    msgs = MEM_MESSAGES.get(session_id, [])
    return sum(1 for m in msgs if m.get("role") == "user")


# ── ADMIN USAGE DASHBOARD HELPERS ──
# These only ever read ids, roles, and timestamps — never message content —
# and are capped so the dashboard stays cheap even as the tables grow.

def sb_get_all_logins(limit: int = 2000) -> list:
    """Most recent login events, newest first."""
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/user_logins"
                f"?select=user_id,username,first_name,login_type,ip_address,created_at"
                f"&order=created_at.desc&limit={limit}",
                headers=_sb_headers(), timeout=10
            )
            if r.status_code == 200:
                rows = r.json()
                if rows:
                    return rows
        except Exception as e:
            logger.warning("Supabase get_all_logins error: %s", e)
    return list(reversed(MEM_LOGINS))[:limit]


def sb_get_all_sessions_light(limit: int = 5000) -> list:
    """Lightweight id -> user_id map of chat sessions, for usage aggregation."""
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/chat_sessions"
            f"?select=id,user_id&order=created_at.desc&limit={limit}",
            headers=_sb_headers(), timeout=10
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.warning("Supabase get_all_sessions_light error: %s", e)
    return []


def sb_get_all_messages_light(limit: int = 10000) -> list:
    """(session_id, role, created_at) for recent messages — counts only, no content."""
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/chat_messages"
            f"?select=session_id,role,created_at&order=created_at.desc&limit={limit}",
            headers=_sb_headers(), timeout=15
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.warning("Supabase get_all_messages_light error: %s", e)
    return []


def _parse_ts(ts: str | None):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def build_usage_report() -> dict:
    """Aggregate login/session/message data into an admin usage report."""
    logins = sb_get_all_logins()
    sessions = sb_get_all_sessions_light()
    messages = sb_get_all_messages_light()

    now = datetime.now(timezone.utc)
    today_cutoff = now - timedelta(hours=24)
    week_cutoff = now - timedelta(days=7)

    # session_id -> user_id, for attributing messages to a user
    session_owner = {s["id"]: s.get("user_id") for s in sessions if s.get("id")}

    # Per-user message counts (student-authored messages only)
    msg_counts: dict = {}
    for m in messages:
        if m.get("role") != "user":
            continue
        uid = session_owner.get(m.get("session_id"))
        if uid is None:
            continue
        msg_counts[uid] = msg_counts.get(uid, 0) + 1

    # Per-user login aggregation. Logins arrive newest-first, so the first
    # row seen for a user is their most recent login.
    users: dict = {}
    login_type_breakdown: dict = {}
    active_today, active_week = set(), set()

    for row in logins:
        uid = row.get("user_id")
        if uid is None:
            continue
        ts = _parse_ts(row.get("created_at"))
        ltype = row.get("login_type") or "unknown"
        login_type_breakdown[ltype] = login_type_breakdown.get(ltype, 0) + 1

        rec = users.get(uid)
        if rec is None:
            rec = {
                "user_id": uid,
                "first_name": row.get("first_name") or "",
                "username": row.get("username") or "",
                "login_types": set(),
                "login_count": 0,
                "first_seen": ts,
                "last_seen": ts,
            }
            users[uid] = rec

        rec["login_count"] += 1
        rec["login_types"].add(ltype)
        if ts and (rec["last_seen"] is None or ts > rec["last_seen"]):
            rec["last_seen"] = ts
        if ts and (rec["first_seen"] is None or ts < rec["first_seen"]):
            rec["first_seen"] = ts

        if ts and ts >= today_cutoff:
            active_today.add(uid)
        if ts and ts >= week_cutoff:
            active_week.add(uid)

    users_list = [{
        "user_id": uid,
        "first_name": rec["first_name"],
        "username": rec["username"],
        "login_types": sorted(rec["login_types"]),
        "login_count": rec["login_count"],
        "message_count": msg_counts.get(uid, 0),
        "first_seen": rec["first_seen"].isoformat() if rec["first_seen"] else None,
        "last_seen": rec["last_seen"].isoformat() if rec["last_seen"] else None,
    } for uid, rec in users.items()]
    users_list.sort(key=lambda u: u["last_seen"] or "", reverse=True)

    recent_logins = [{
        "user_id": row.get("user_id"),
        "first_name": row.get("first_name") or "",
        "username": row.get("username") or "",
        "login_type": row.get("login_type") or "unknown",
        "ip_address": row.get("ip_address") or "",
        "created_at": row.get("created_at"),
    } for row in logins[:50]]

    return {
        "summary": {
            "total_users": len(users_list),
            "total_logins": len(logins),
            "total_sessions": len(sessions),
            "total_messages": sum(1 for m in messages if m.get("role") == "user"),
            "active_today": len(active_today),
            "active_7d": len(active_week),
        },
        "login_type_breakdown": login_type_breakdown,
        "users": users_list,
        "recent_logins": recent_logins,
    }


def verify_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data))
        if "hash" not in parsed:
            return None
        hash_value = parsed.pop("hash")

        sorted_pairs = sorted([f"{k}={v}" for k, v in parsed.items()])
        data_check_string = "\n".join(sorted_pairs)

        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if computed_hash == hash_value:
            user_data = json.loads(parsed.get("user", "{}"))
            return user_data
    except Exception as e:
        print(f"Error verifying initData: {e}")
    return None


# Route / redirects directly to the primary Cloudflare frontend
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route("/")
def index():
    frontend_url = os.getenv("FRONTEND_URL", "https://brainyai.cenai.workers.dev").rstrip("/")
    code = request.args.get("code", "")
    error = request.args.get("error", "")

    # Bridge Google OAuth redirect fragments and parameters to the frontend
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Connecting to Brainy...</title>
</head>
<body style="background:#090a0f;color:#fff;font-family:system-ui,-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
    <div style="text-align:center;">
        <div style="width:36px;height:36px;border:3px solid #10b981;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 16px auto;"></div>
        <h2 style="font-weight:600;font-size:18px;margin:0 0 6px 0;">Signing in with Google...</h2>
        <p style="color:#888;font-size:13px;margin:0;">Connecting your secure study workspace</p>
    </div>
    <style>@keyframes spin {{ to {{ transform: rotate(360deg); }} }}</style>
    <script>
        try {{
            const hash = window.location.hash.substring(1);
            const params = new URLSearchParams(hash || window.location.search);
            const token = params.get('access_token') || params.get('id_token') || '{code}';
            const err = params.get('error') || '{error}';
            if (token) {{
                window.location.replace("{frontend_url}/?google_token=" + encodeURIComponent(token));
            }} else if (err) {{
                window.location.replace("{frontend_url}/?auth_error=" + encodeURIComponent(err));
            }} else {{
                window.location.replace("{frontend_url}");
            }}
        }} catch(e) {{
            window.location.replace("{frontend_url}");
        }}
    </script>
</body>
</html>"""
    return html


@app.route("/api/config", methods=["GET"])
def get_config():
    """Expose public environment configuration (e.g. Google OAuth Client ID)."""
    return jsonify({
        "google_client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
        "telegram_bot_username": os.environ.get("TELEGRAM_BOT_USERNAME", "AiChatExpert_Bot")
    })


# ── AUTHENTICATION APIS ──

@app.route("/api/auth/init", methods=["POST"])
def auth_init():
    session_id = str(uuid.uuid4())
    auth_sessions[session_id] = {"status": "pending", "user": None}
    bot_username = "AiChatExpert_Bot"
    return jsonify({
        "session_id": session_id,
        "bot_url": f"https://t.me/{bot_username}?start=sess_{session_id}"
    })


@app.route("/api/auth/status/<session_id>", methods=["GET"])
@app.route("/api/auth/poll/<session_id>", methods=["GET"])
def auth_status(session_id):
    sess = auth_sessions.get(session_id)
    if not sess:
        return jsonify({"status": "not_found"}), 404

    if sess["status"] == "authenticated":
        user = sess["user"]
        session["user_id"] = user["id"]
        session["first_name"] = user["first_name"]
        session["username"] = user.get("username", "")
        session["email"] = ""  # Telegram logins have no verified email
        if user.get("username"):
            user["photo_url"] = f"https://t.me/i/userpic/320/{user['username']}.jpg"
        session["photo_url"] = user.get("photo_url", "")
        role = "admin" if is_admin_session() else "student"
        token = create_auth_token(user["id"], user.get("username", ""), user["first_name"], "", role)
        auth_sessions.pop(session_id, None)
        return jsonify({"status": "authenticated", "user": user, "token": token})

    return jsonify({"status": "pending"})


# Telegram bot handshake verification endpoint
@app.route("/api/auth/verify", methods=["GET"])
def auth_verify():
    session_id = request.args.get("session_id")
    user_id = request.args.get("user_id")
    first_name = request.args.get("first_name", "")
    username = request.args.get("username", "")

    if not session_id or not user_id:
        return "❌ Missing session_id or user_id", 400

    if session_id in auth_sessions:
        photo_url = f"https://t.me/i/userpic/320/{username}.jpg" if username else ""
        auth_sessions[session_id] = {
            "status": "authenticated",
            "user": {
                "id": int(user_id),
                "first_name": first_name,
                "username": username,
                "photo_url": photo_url
            }
        }

        try:
            study_bot.load_user_into_memory(int(user_id), first_name, username)
            sb_record_login(
                user_id=int(user_id),
                username=username,
                first_name=first_name,
                login_type="telegram",
                ip=request.remote_addr or "",
                user_agent=request.headers.get("User-Agent", "")
            )
        except Exception as e:
            logger.warning("Error recording verified Telegram login: %s", e)

        frontend_url = os.getenv("FRONTEND_URL", "https://brainyai.cenai.workers.dev").rstrip("/")
        display_name = escape(first_name or username or "Scholar")

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Brainy-AI — Authorized</title>
    <meta http-equiv="refresh" content="2;url={frontend_url}">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: #09090B;
            color: #FFFFFF;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .card {{
            background: #121214;
            border: 1px solid rgba(245, 158, 11, 0.35);
            border-radius: 20px;
            padding: 36px 32px;
            text-align: center;
            max-width: 420px;
            width: 100%;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.8), 0 0 30px rgba(245, 158, 11, 0.1);
        }}
        .emblem {{
            width: 60px;
            height: 60px;
            border-radius: 16px;
            background: rgba(245, 158, 11, 0.15);
            border: 1px solid rgba(245, 158, 11, 0.4);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            margin: 0 auto 20px;
        }}
        h1 {{
            font-size: 22px;
            font-weight: 700;
            color: #FFFFFF;
            margin-bottom: 8px;
        }}
        p {{
            font-size: 14px;
            color: #A1A1AA;
            line-height: 1.6;
            margin-bottom: 24px;
        }}
        .btn {{
            display: inline-block;
            background: linear-gradient(135deg, #FBBF24, #D97706);
            color: #09090B;
            font-weight: 700;
            font-size: 14px;
            padding: 12px 24px;
            border-radius: 12px;
            text-decoration: none;
            transition: transform 0.2s;
        }}
        .btn:hover {{
            transform: scale(1.02);
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="emblem">🔓</div>
        <h1>Authentication Successful</h1>
        <p>Welcome, <strong>{display_name}</strong>! Your session is verified. Redirecting you to Brainy AI...</p>
        <a href="{frontend_url}" class="btn">Enter Sanctuary →</a>
    </div>
</body>
</html>"""
    return "❌ Invalid or expired session ID", 400


@app.route("/api/auth/initdata", methods=["POST"])
def auth_initdata():
    data = request.json or {}
    init_data = data.get("initData")
    if not init_data:
        return jsonify({"error": "initData missing"}), 400

    user_data = verify_telegram_init_data(init_data, study_bot.TELEGRAM_TOKEN)
    if user_data:
        session["user_id"] = user_data["id"]
        session["first_name"] = user_data["first_name"]
        session["username"] = user_data.get("username", "")
        session["email"] = ""  # Telegram logins have no verified email

        # Record login in Supabase
        sb_record_login(
            user_id=user_data["id"],
            username=user_data.get("username", ""),
            first_name=user_data.get("first_name", ""),
            login_type="telegram_webapp",
            ip=request.remote_addr or "",
            user_agent=request.headers.get("User-Agent", "")
        )

        role = "admin" if is_admin_session() else "student"
        token = create_auth_token(user_data["id"], user_data.get("username", ""), user_data.get("first_name", ""), "", role)
        return jsonify({"status": "authenticated", "user": user_data, "token": token})
    return jsonify({"error": "Invalid signature"}), 401


@app.route("/api/auth/web", methods=["POST"])
@security_guard
def auth_web():
    """Handle direct web login with Name and optional Username."""
    if _is_production():
        return jsonify({
            "error": "Name-only sign-in is not available in production. Use Google or Telegram login.",
            "code": "UNVERIFIED_LOGIN_DISABLED",
        }), 403
    data = request.json or {}
    name = (data.get("name") or "").strip()
    username = (data.get("username") or "").strip()

    if not name:
        return jsonify({"error": "Name is required"}), 400

    if not username:
        username = re.sub(r"[^a-zA-Z0-9_]", "", name.lower().replace(" ", "_")) or f"user_{int(time.time())}"

    # Deterministic integer user_id from username/name
    user_id = int(hashlib.md5(f"web_{username}".encode()).hexdigest(), 16) % (10**9)

    session["user_id"] = user_id
    session["first_name"] = name
    session["username"] = username
    session["email"] = ""

    try:
        study_bot.load_user_into_memory(user_id, name, username)
    except Exception as me:
        logger.warning("Could not sync user memory during web auth user_id=%s category=%s", user_id, type(me).__name__)

    # Record login in Supabase user_logins table
    sb_record_login(
        user_id=user_id,
        username=username,
        first_name=name,
        login_type="web",
        ip=request.remote_addr or "",
        user_agent=request.headers.get("User-Agent", "")
    )

    role = "admin" if is_admin_session() else "student"
    token = create_auth_token(user_id, username, name, "", role)

    return jsonify({
        "status": "authenticated",
        "authenticated": True,
        "user": {
            "id": user_id,
            "first_name": name,
            "username": username
        },
        "token": token
    })


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    """Check current authentication status. Supports Bearer token or session cookie."""
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        payload = verify_auth_token(auth_header[7:].strip())
        if payload and payload.get("sub"):
            session["user_id"] = payload["sub"]
            session["username"] = payload.get("username", "")
            session["first_name"] = payload.get("name", "Student")
            session["email"] = payload.get("email", "")
            session["role"] = payload.get("role", "student")

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False}), 401

    role = "admin" if is_admin_session() else "student"
    token = create_auth_token(
        user_id,
        session.get("username", ""),
        session.get("first_name", "Student"),
        session.get("email", ""),
        role
    )

    return jsonify({
        "authenticated": True,
        "user": {
            "id": user_id,
            "first_name": session.get("first_name", "Student"),
            "username": session.get("username", ""),
            "photo_url": session.get("photo_url", "")
        },
        "token": token
    })


@app.route("/api/auth/google", methods=["POST"])
def auth_google():
    """Verify a Google Identity Services ID token and create a Brainy app session."""
    data = request.json or {}
    token = data.get("credential")
    if not token:
        return jsonify({"error": "Missing Google credential token"}), 400

    id_info = None
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    if not google_client_id:
        return jsonify({
            "error": "Google sign-in is not configured on the server.",
            "code": "GOOGLE_AUTH_NOT_CONFIGURED",
        }), 503

    # 1. Attempt verification with client ID if configured
    if google_client_id:
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests
            id_info = id_token.verify_oauth2_token(
                token, google_requests.Request(), google_client_id
            )
        except Exception as e:
            logger.warning("Google ID token verification failed category=%s", type(e).__name__)

    # 2. Verify ID-token fallback with Google's tokeninfo endpoint.
    if not id_info:
        try:
            g_resp = requests.get("https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": token}, timeout=8)
            if g_resp.status_code == 200:
                id_info = g_resp.json()
            else:
                logger.info("Google ID-token verification fallback status=%s", g_resp.status_code)
        except Exception as ge:
            logger.warning("Google ID-token verification fallback failed category=%s", type(ge).__name__)

    # 3. Preserve the repository's legacy browser redirect flow, which returns
    # an OAuth access token when the GIS button cannot load. Accept it only if
    # Google's tokeninfo binds it to this exact client and its userinfo subject
    # matches Google's tokeninfo user ID. Never accept unverified userinfo alone.
    if not id_info:
        try:
            access_resp = requests.get("https://oauth2.googleapis.com/tokeninfo",
                params={"access_token": token}, timeout=8)
            if access_resp.status_code == 200:
                access_info = access_resp.json()
                audience = access_info.get("issued_to") or access_info.get("audience") or access_info.get("aud")
                try:
                    expires_in = int(access_info.get("expires_in", 0))
                except (TypeError, ValueError):
                    expires_in = 0
                token_user_id = access_info.get("user_id") or access_info.get("sub")
                if audience == google_client_id and expires_in > 0 and token_user_id:
                    profile_resp = requests.get("https://www.googleapis.com/oauth2/v3/userinfo",
                        headers={"Authorization": f"Bearer {token}"}, timeout=8)
                    if profile_resp.status_code == 200:
                        profile_info = profile_resp.json()
                        if (profile_info.get("sub") == token_user_id
                                and profile_info.get("email")
                                and profile_info.get("email_verified") in (True, "true", "True", 1, "1")):
                            id_info = {
                                "sub": profile_info["sub"],
                                "email": profile_info["email"],
                                "email_verified": profile_info["email_verified"],
                                "name": profile_info.get("name"),
                                "picture": profile_info.get("picture", ""),
                                "aud": google_client_id,
                                "iss": "https://accounts.google.com",
                                "exp": int(time.time()) + expires_in,
                            }
                        else:
                            logger.warning("Google access-token profile subject or email verification mismatch")
                    else:
                        logger.warning("Google userinfo returned status=%s", profile_resp.status_code)
                else:
                    logger.warning("Google access token rejected for client, expiry, or subject mismatch")
            else:
                logger.warning("Google access-token verification returned status=%s", access_resp.status_code)
        except Exception as ge:
            logger.warning("Google access-token verification failed category=%s", type(ge).__name__)

    if not id_info:
        return jsonify({"error": "Google token verification failed. Please try again or use Telegram login."}), 401

    issuer = id_info.get("iss")
    try:
        token_expiry = int(id_info.get("exp", 0))
    except (TypeError, ValueError):
        token_expiry = 0
    if (id_info.get("aud") != google_client_id
            or issuer not in ("accounts.google.com", "https://accounts.google.com")
            or token_expiry <= int(time.time())
            or not id_info.get("sub")):
        logger.warning("Google ID token rejected for invalid audience, issuer, expiry, or subject")
        return jsonify({"error": "Google token is invalid or intended for another application."}), 401

    email_verified = id_info.get("email_verified")
    if email_verified not in (True, "true", "True", 1, "1"):
        return jsonify({"error": "Google account email is not verified."}), 401

    email = (id_info.get("email") or "").strip().lower()
    name = id_info.get("name") or (email.split("@")[0] if email else "Google Student")
    google_sub = id_info["sub"]
    picture = id_info.get("picture", "")

    # Deterministic integer user_id
    user_id = int(hashlib.md5(f"google_{google_sub}".encode()).hexdigest(), 16) % (10**9)
    username = email.split("@")[0] if email else name.lower().replace(" ", "_")

    session["user_id"] = user_id
    session["first_name"] = name
    session["username"] = username
    session["email"] = email.strip().lower()
    session["photo_url"] = picture

    try:
        # Ensure user memory in study_bot (non-fatal if database is slow/warming up)
        try:
            study_bot.load_user_into_memory(user_id, name, username)
        except Exception as me:
            logger.warning("Could not sync user memory during Google auth user_id=%s category=%s", user_id, type(me).__name__)

        # Record login in Supabase (non-fatal)
        try:
            sb_record_login(
                user_id=user_id,
                username=username,
                first_name=name,
                login_type="google",
                ip=request.remote_addr or "",
                user_agent=request.headers.get("User-Agent", "")
            )
        except Exception as re:
            logger.warning("Could not record login event user_id=%s category=%s", user_id, type(re).__name__)

        role = "admin" if is_admin_session() else "student"
        token_str = create_auth_token(user_id, username, name, email, role)

        return jsonify({
            "status": "authenticated",
            "authenticated": True,
            "user": {
                "id": user_id,
                "first_name": name,
                "username": username,
                "email": email,
                "picture": picture,
                "photo_url": picture
            },
            "token": token_str
        })
    except Exception as exc:
        logger.error("Unhandled error finalizing Google login category=%s", type(exc).__name__)
        return jsonify({"error": "Failed to finalize Google login. Please try again or use Student Pass."}), 500


@app.route("/api/auth/student_pass", methods=["POST"])
def auth_student_pass():
    """1-click cryptographic student pass. Zero passwords or manual typing required."""
    import secrets
    raw_token = secrets.token_hex(12)
    user_id = int(hashlib.md5(f"pass_{raw_token}".encode()).hexdigest(), 16) % (10**9)
    name = f"Student {str(user_id)[-4:]}"
    username = f"student_{str(user_id)[-4:]}"

    session["user_id"] = user_id
    session["first_name"] = name
    session["username"] = username
    session["email"] = ""
    session["photo_url"] = ""

    try:
        study_bot.load_user_into_memory(user_id, name, username)
    except Exception as me:
        logger.warning("Could not sync user memory for user_id=%s during student pass auth (non-fatal): %s", user_id, me)

    # Record login event in Supabase user_logins table
    sb_record_login(
        user_id=user_id,
        username=username,
        first_name=name,
        login_type="student_pass",
        ip=request.remote_addr or "",
        user_agent=request.headers.get("User-Agent", "")
    )

    role = "admin" if is_admin_session() else "student"
    token = create_auth_token(user_id, username, name, "", role)

    return jsonify({
        "status": "authenticated",
        "user": {
            "id": user_id,
            "first_name": name,
            "username": username
        },
        "token": token
    })



@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"status": "logged_out"})


# ── ADMIN DASHBOARD APIS ──

@app.route("/api/admin/check", methods=["GET"])
@login_required
def admin_check():
    """Lets the frontend know whether to show the Admin Dashboard button."""
    return jsonify({"is_admin": is_admin_session()})


@app.route("/api/admin/overview", methods=["GET"])
@app.route("/api/admin/usage", methods=["GET"])
@admin_required
def admin_overview():
    """Admin-only: registered users, login activity, session and message counts from Supabase."""
    try:
        return jsonify(build_usage_report())
    except Exception as e:
        logger.error("admin_overview error: %s", e)
        return jsonify({"error": "Failed to build usage report"}), 500


@app.route("/api/admin/users", methods=["GET"])
@admin_required
def admin_users():
    """Admin-only: list registered users with optional search query (?q=), pagination, and suspension state."""
    try:
        q = (request.args.get("q") or "").strip().lower()
        report = build_usage_report()
        users = report.get("users", [])

        for u in users:
            uid = u.get("user_id")
            u["is_suspended"] = is_user_suspended(uid)
            u["is_admin"] = uid in ADMIN_USER_IDS or (u.get("username") or "").lower() in ADMIN_USERNAMES

        if q:
            users = [
                u for u in users
                if q in str(u.get("user_id", "")).lower()
                or q in (u.get("username") or "").lower()
                or q in (u.get("first_name") or "").lower()
                or any(q in lt.lower() for lt in u.get("login_types", []))
            ]

        try:
            page = max(1, int(request.args.get("page", 1)))
        except (ValueError, TypeError):
            page = 1
        try:
            limit = min(100, max(1, int(request.args.get("limit", 25))))
        except (ValueError, TypeError):
            limit = 25

        total = len(users)
        start = (page - 1) * limit
        paged_users = users[start : start + limit]

        return jsonify({
            "total": total,
            "page": page,
            "limit": limit,
            "users": paged_users
        })
    except Exception as e:
        logger.error("admin_users error: %s", e)
        return jsonify({"error": "Failed to fetch users"}), 500


@app.route("/api/admin/users/<int:target_user_id>/suspend", methods=["POST"])
@admin_required
def admin_toggle_suspend(target_user_id: int):
    """Admin-only: toggle suspension status for a user."""
    current_admin_id = session.get("user_id")
    if target_user_id == current_admin_id:
        return jsonify({"error": "Cannot suspend your own admin account"}), 400

    with _suspend_lock:
        if target_user_id in _suspended_users:
            _suspended_users.remove(target_user_id)
            state = False
        else:
            _suspended_users.add(target_user_id)
            state = True
        _save_suspended_users()

    logger.info("Admin %s toggled suspension for user %s -> %s", current_admin_id, target_user_id, state)
    return jsonify({
        "status": "ok",
        "user_id": target_user_id,
        "is_suspended": state
    })


@app.route("/api/admin/users/<int:target_user_id>", methods=["DELETE"])
@admin_required
def admin_delete_user(target_user_id: int):
    """Admin-only: permanently delete a user and their sessions/messages across Supabase & memory."""
    current_admin_id = session.get("user_id")
    if target_user_id == current_admin_id:
        return jsonify({"error": "Cannot delete your own admin account"}), 400

    MEM_SESSIONS.pop(target_user_id, None)
    with _suspend_lock:
        _suspended_users.discard(target_user_id)
        _save_suspended_users()

    try:
        requests.delete(f"{SUPABASE_URL}/rest/v1/chat_sessions?user_id=eq.{target_user_id}", headers=_sb_headers(), timeout=8)
        requests.delete(f"{SUPABASE_URL}/rest/v1/user_logins?user_id=eq.{target_user_id}", headers=_sb_headers(), timeout=8)
        requests.delete(f"{SUPABASE_URL}/rest/v1/user_memory?user_id=eq.{target_user_id}", headers=_sb_headers(), timeout=8)
    except Exception as e:
        logger.warning("Supabase cleanup on delete user %s error: %s", target_user_id, e)

    logger.info("Admin %s deleted user %s", current_admin_id, target_user_id)
    return jsonify({"status": "ok", "deleted_user_id": target_user_id})


@app.route("/api/admin/health", methods=["GET"])
@admin_required
def admin_health():
    """Real system health telemetry: Supabase status, latency, AI provider configuration, and server metrics."""
    now = datetime.now(timezone.utc).isoformat()
    sb_status = "unconfigured"
    sb_latency_ms = None
    if SUPABASE_URL and SUPABASE_KEY:
        t0 = time.time()
        try:
            r = requests.get(f"{SUPABASE_URL}/rest/v1/user_logins?limit=1", headers=_sb_headers(), timeout=5)
            sb_latency_ms = round((time.time() - t0) * 1000, 2)
            sb_status = "healthy" if r.status_code in (200, 206) else f"status_{r.status_code}"
        except Exception as e:
            sb_status = "unreachable"
            sb_latency_ms = round((time.time() - t0) * 1000, 2)

    groq_configured = bool(os.getenv("GROQ_API_KEY") or getattr(study_bot, "GROQ_API_KEY", None))
    openrouter_configured = bool(os.getenv("OPENROUTER_API_KEY") or getattr(study_bot, "OPENROUTER_API_KEY", None))
    gemini_configured = bool(os.getenv("GEMINI_API_KEY") or getattr(study_bot, "GEMINI_API_KEY", None))

    return jsonify({
        "status": "healthy" if sb_status == "healthy" else "degraded",
        "timestamp": now,
        "supabase": {
            "configured": bool(SUPABASE_URL and SUPABASE_KEY),
            "status": sb_status,
            "latency_ms": sb_latency_ms
        },
        "providers": {
            "groq": {"configured": groq_configured, "status": "active" if groq_configured else "missing_key"},
            "openrouter": {"configured": openrouter_configured, "status": "active" if openrouter_configured else "missing_key"},
            "gemini": {"configured": gemini_configured, "status": "active" if gemini_configured else "missing_key"}
        },
        "server": {
            "quota_window_hours": QUOTA_WINDOW_HOURS,
            "global_message_limit": GLOBAL_MESSAGE_LIMIT,
            "sessions_cached": len(MEM_SESSIONS),
            "messages_cached": len(MEM_MESSAGES),
            "suspended_users_count": len(_suspended_users)
        }
    })


# login_required and security_guard are imported from security.py


# ── CHAT SESSION APIS ──

@app.route("/api/sessions", methods=["GET"])
@login_required
def get_sessions():
    user_id = session["user_id"]
    view = request.args.get("view", "all")
    paginated = "limit" in request.args or "offset" in request.args
    try:
        limit = int(request.args.get("limit", "50")) if paginated else 100
        offset = int(request.args.get("offset", "0")) if paginated else 0
        if paginated and not 1 <= limit <= 100:
            raise ValueError("Page size is invalid")
        rows = sb_list_sessions(user_id, view=view, limit=limit + 1 if paginated else limit, offset=offset)
        if not paginated:
            return jsonify(rows)
        page_rows = rows[:limit]
        return jsonify({
            "sessions": page_rows,
            "has_more": len(rows) > limit,
            "next_offset": offset + len(page_rows),
        })
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid conversation view or page parameters"}), 400


@app.route("/api/sessions", methods=["POST"])
@login_required
def create_session():
    user_id = session["user_id"]
    data = request.json or {}
    title = data.get("title", "New Chat")
    row = sb_create_session(user_id, title)
    return jsonify({"id": row["id"], "title": row["title"]})


@app.route("/api/sessions/<session_id>", methods=["PATCH"])
@login_required
def rename_session(session_id):
    user_id = session["user_id"]
    data = request.json or {}
    title = data.get("title")
    metadata = {k: data[k] for k in ("is_saved", "is_pinned", "is_archived") if k in data}
    if title is None and not metadata:
        return jsonify({"error": "Title or workspace setting required"}), 400
    if not sb_get_session(session_id, user_id):
        return jsonify({"error": "Session not found"}), 404
    if title is not None:
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 160:
            return jsonify({"error": "Title must be between 1 and 160 characters"}), 400
        sb_rename_session(session_id, user_id, title.strip())
    if metadata:
        try:
            sb_update_session_metadata(session_id, user_id, metadata)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    return jsonify({"status": "ok", **metadata, **({"title": title.strip()} if title is not None else {})})


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
@login_required
def delete_session(session_id):
    user_id = session["user_id"]
    if not sb_get_session(session_id, user_id):
        return jsonify({"error": "Session not found"}), 404
    sb_delete_session(session_id, user_id)
    return jsonify({"status": "ok"})


@app.route("/api/usage", methods=["GET"])
@login_required
def get_usage():
    """Returns the user's global 5-hour window quota status."""
    user_id = session["user_id"]
    return jsonify(get_user_quota(user_id))


@app.route("/api/models", methods=["GET"])
def get_models():
    """Public catalogue of capability-based models."""
    return jsonify(MODELS_CATALOG)


@app.route("/api/chat/<session_id>", methods=["GET"])
@login_required
def get_chat_history(session_id):
    user_id = session["user_id"]
    sess = sb_get_session(session_id, user_id)
    if not sess:
        return jsonify({"error": "Session not found"}), 404

    messages = sb_get_messages(session_id, user_id)
    for m in messages:
        if m.get("role") == "assistant":
            m["content"] = format_for_web(m["content"])

    quota_status = get_user_quota(user_id)

    return jsonify({
        "session_id": session_id,
        "title": sess.get("title", "Study Session"),
        "messages": messages,
        "usage": quota_status,
        "user_message_count": quota_status["used"],
        "message_limit": GLOBAL_MESSAGE_LIMIT
    })


@app.route("/api/share", methods=["POST"])
@login_required
def create_share_link():
    user_id = session["user_id"]
    data = request.json or {}
    session_id = data.get("session_id")
    content = (data.get("content") or "").strip()

    if not session_id or not content:
        return jsonify({"error": "Missing session_id or content"}), 400
    if not sb_get_session(session_id, user_id):
        return jsonify({"error": "Session not found"}), 404

    share_id = uuid.uuid4().hex[:12]
    share_links[share_id] = {
        "content": content[:12000],
        "title": data.get("title") or "BRAINY Answer",
    }
    return jsonify({"id": share_id, "url": urllib.parse.urljoin(request.url_root, f"share/{share_id}")})


@app.route("/share/<share_id>", methods=["GET"])
def view_shared_answer(share_id):
    item = share_links.get(share_id)
    if not item:
        return "Shared answer not found or expired.", 404

    title = escape(item.get("title") or "BRAINY Answer")
    content = escape(item.get("content") or "")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ margin:0; font-family: 'Lora', Georgia, serif; background:#0b0a14; color:#ede7f6; }}
    main {{ max-width: 780px; margin: 0 auto; padding: 48px 20px; }}
    h1 {{ font-size: 20px; margin: 0 0 18px; }}
    article {{ white-space: pre-wrap; line-height: 1.65; background:#14111f; border:1px solid #322a4d; border-radius:14px; padding:22px; }}
  </style>
</head>
<body><main><h1>{title}</h1><article>{content}</article></main></body>
</html>"""


def _prepare_chat_request(data: dict, user_id: int, first_name: str, username: str, ip: str):
    """
    Shared pre-generation pipeline for both /api/chat/send and /api/chat/stream.
    Ensures identical sanitization, quota consumption, intent detection,
    and prompt construction without any code divergence.
    """
    pipeline_started = time.perf_counter()
    session_id = data.get("session_id")
    # Unified contract: accept both 'message' and 'content'
    raw_content = data.get("message") or data.get("content") or ""
    if not isinstance(raw_content, str):
        return None, jsonify({"error": "Message must be text", "code": "INVALID_MESSAGE"}), 400
    content = raw_content.strip()
    if len(content) > 12000:
        return None, jsonify({"error": "Message is too long (maximum 12,000 characters).", "code": "MESSAGE_TOO_LONG"}), 413
    model_id = (data.get("model") or "brainy-balanced").strip().lower()
    answer_length = (data.get("answer_length") or "medium").strip().lower()

    if not content:
        return None, jsonify({"error": "Message content cannot be empty"}), 400
    if session_id:
        try:
            uuid.UUID(str(session_id))
        except (ValueError, TypeError, AttributeError):
            return None, jsonify({"error": "Invalid session identifier", "code": "INVALID_SESSION_ID"}), 400

    # Check if user account is suspended
    if is_user_suspended(user_id):
        return None, jsonify({
            "error": "account_suspended",
            "message": "Your account has been suspended by an administrator."
        }), 403

    # Validate an existing session against the durable store before charging quota.
    session_check_started = time.perf_counter()
    try:
        sess = sb_get_session(session_id, user_id) if session_id else None
    except SupabaseOperationError:
        return None, jsonify({"error": "Chat storage is temporarily unavailable. Please retry.", "code": "STORAGE_UNAVAILABLE", "retryable": True}), 503
    session_validation_ms = round((time.perf_counter() - session_check_started) * 1000, 2)
    if session_id and not sess:
        return None, jsonify({"error": "Session not found", "code": "SESSION_NOT_FOUND"}), 404

    # Sanitize user input
    content = sanitize_input(content)

    intent, payload = study_bot.detect_intent(content)

    # Search is a separate expensive operation with its own burst ceiling.
    if intent == "search":
        try:
            search_allowed = check_rate_limit(f"search_user_{user_id}", limit=5, window=60)
        except RateLimitStoreUnavailable:
            return None, jsonify({"error": "Request protection is temporarily unavailable. Please retry shortly.",
                "code": "RATE_LIMIT_STORE_UNAVAILABLE", "request_id": getattr(g, "request_id", None), "retryable": True}), 503
        if not search_allowed:
            retry_after = rate_limit_retry_after(f"search_user_{user_id}", window=60)
            response = jsonify({"error": "Search limit reached. Please wait a moment before searching again.",
                "code": "SEARCH_RATE_LIMITED", "retry_after": retry_after, "limit": 5})
            response.headers["Retry-After"] = str(retry_after)
            return None, response, 429

    # Per-user rate limit: 10 messages per minute
    try:
        user_rate_allowed = check_rate_limit("user_{}".format(user_id), limit=10, window=60)
    except RateLimitStoreUnavailable:
        return None, jsonify({"error": "Request protection is temporarily unavailable. Please retry shortly.",
            "code": "RATE_LIMIT_STORE_UNAVAILABLE", "request_id": getattr(g, "request_id", None), "retryable": True}), 503
    if not user_rate_allowed:
        log_security_event("user_rate_limit", ip, user_id, "")
        retry_after = rate_limit_retry_after("user_{}".format(user_id), window=60)
        response = jsonify({"error": "Message rate limit reached. Please wait a moment.",
            "code": "CHAT_RATE_LIMITED", "retry_after": retry_after, "limit": 10})
        response.headers["Retry-After"] = str(retry_after)
        return None, response, 429

    # Enforce quota before storing the accepted message or spending AI tokens.
    try:
        allowed, quota_status = consume_user_quota(user_id)
    except SupabaseOperationError:
        return None, jsonify({"error": "Usage tracking is temporarily unavailable. Please retry.", "code": "QUOTA_STORAGE_UNAVAILABLE", "retryable": True}), 503
    if not allowed:
        return None, jsonify({
            "error": "quota_exceeded",
            "code": "QUOTA_EXCEEDED",
            "message": f"You have reached your {QUOTA_WINDOW_HOURS}-hour limit of {GLOBAL_MESSAGE_LIMIT} messages. Quota resets at {quota_status['reset_at']}.",
            "usage": quota_status,
            "user_message_count": quota_status["used"],
            "message_limit": GLOBAL_MESSAGE_LIMIT
        }), 429

    # Durable history is best effort for answer delivery. A database outage must
    # not discard the user's question or prevent an otherwise valid AI answer.
    persistence_warning = False
    if not session_id:
        try:
            sess = sb_create_session(user_id, "New Study Session")
            session_id = sess["id"]
        except SupabaseOperationError as exc:
            logger.warning("Session creation failed request_id=%s category=%s", getattr(g, "request_id", ""), type(exc).__name__)
            sess = {"title": None}
            persistence_warning = True

    if session_id:
        try:
            sb_insert_message(session_id, "user", content,
                idempotency_key=data.get("idempotency_key"), user_id=user_id)
        except SupabaseOperationError as exc:
            logger.warning("User message persistence failed request_id=%s category=%s", getattr(g, "request_id", ""), type(exc).__name__)
            persistence_warning = True

    # Include the current question even if its insert or the history read fails.
    messages_context = []
    history_started = time.perf_counter()
    if session_id:
        try:
            summary_available = bool(sess and sess.get("context_summary"))
            if summary_available:
                summary_through_id = int(sess.get("summary_through_message_id") or 0)
                history_rows = sb_get_recent_messages(
                    session_id,
                    41,
                    user_id=user_id,
                    after_id=summary_through_id,
                )
                # If summary refresh fell behind, temporarily load the entire
                # unsummarized tail so no middle turns disappear from context.
                if len(history_rows) == 41:
                    history_rows = sb_get_recent_messages(
                        session_id, None, user_id=user_id, after_id=summary_through_id
                    )
            else:
                history_rows = sb_get_recent_messages(session_id, 30, user_id=user_id)
            messages_context = [{"role": m["role"], "content": m["content"]} for m in history_rows]
        except SupabaseOperationError as exc:
            logger.warning("Chat history read failed request_id=%s category=%s", getattr(g, "request_id", ""), type(exc).__name__)
            try:
                refund_user_quota(user_id)
            except SupabaseOperationError:
                logger.error("Quota refund failed after history read error request_id=%s", getattr(g, "request_id", ""))
            return None, jsonify({
                "error": "This chat's history is temporarily unavailable. Retry after the database reconnects.",
                "code": "CHAT_HISTORY_UNAVAILABLE",
                "retryable": True,
            }), 503
    history_fetch_ms = round((time.perf_counter() - history_started) * 1000, 2)
    context_started = time.perf_counter()
    current_turn_is_loaded = bool(
        messages_context
        and messages_context[-1].get("role") == "user"
        and messages_context[-1].get("content") == content
    )
    if not current_turn_is_loaded:
        messages_context.append({"role": "user", "content": content})

    # Durable personal profile is loaded before model context is assembled.
    try:
        study_bot.load_user_into_memory(user_id, first_name, username, refresh=True)
    except Exception:
        refund_user_quota(user_id)
        return None, jsonify({"error": "Your study profile is temporarily unavailable. Please retry.", "code": "MEMORY_LOAD_FAILED", "retryable": True}), 503

    system_prompt = study_bot.SYSTEM_PROMPT
    max_tok = None

    # Model capability overrides
    if model_id == "brainy-fast":
        system_prompt += (
            "\n\nCAPABILITY OVERRIDE — BRAINY FAST:\n"
            "Deliver rapid, highly distilled answers with zero fluff. Use crisp bullet points, direct equations, and one-line summaries."
        )
    elif model_id == "brainy-reasoning":
        system_prompt += (
            "\n\nCAPABILITY OVERRIDE — BRAINY REASONING:\n"
            "Provide deep academic reasoning. Break problems down from first principles, write explicit mathematical "
            "or logical steps, and verify edge cases before stating conclusions."
        )
    elif model_id == "brainy-coding":
        system_prompt += (
            "\n\nCAPABILITY OVERRIDE — BRAINY CODE:\n"
            "Focus on clean code architecture, optimal time/space complexity, type safety, and edge-case handling. "
            "Annotate key lines with concise comments."
        )
    elif model_id == "brainy-exam":
        system_prompt += (
            "\n\nCAPABILITY OVERRIDE — BRAINY EXAM PREP:\n"
            "Structure the response according to high-yield exam standards. Highlight key marks distribution, "
            "common student mistakes, and provide 2 quick self-test questions at the end."
        )

    # Answer length constraint handling
    if answer_length == "short":
        system_prompt += (
            "\n\nANSWER LENGTH CONSTRAINT — SHORT MODE:\n"
            "Keep your response concise, direct, and under 250 words. Focus strictly on "
            "core definitions, key bullet points, and essential formulas. Avoid conversational filler."
        )
        max_tok = 350
    elif answer_length == "long":
        system_prompt += (
            "\n\nANSWER LENGTH CONSTRAINT — LONG MODE:\n"
            "Provide an exhaustive, in-depth explanation (~800-1200 words). Include background context, "
            "detailed step-by-step breakdown or derivations, real-world examples, common pitfalls, and review questions."
        )
        max_tok = 1400
    else:
        answer_length = "medium"
        system_prompt += (
            "\n\nANSWER LENGTH CONSTRAINT — MEDIUM MODE:\n"
            "Provide a balanced, well-structured explanation (~400-600 words) with clear headings, "
            "bullet points, and relevant examples."
        )
        max_tok = 800

    # Ground the model in real facts about this user's quota
    system_prompt += (
        f"\n\nFACTS ABOUT THIS USER (answer accurately if asked, don't guess):\n"
        f"- The user has a {QUOTA_WINDOW_HOURS}-hour quota of {GLOBAL_MESSAGE_LIMIT} messages total across Brainy.\n"
        f"- {quota_status['used']} messages used so far in this window, {quota_status['remaining']} remaining.\n"
        f"- The window resets at {quota_status['reset_at']}.\n"
        f"- The complete message history of the active chat is provided as context."
    )

    user_profile = study_bot.get_user_data(user_id)

    if intent == "joke":
        system_prompt = study_bot.JOKE_SYSTEM_PROMPT
        max_tok = 150
    elif intent == "fact":
        system_prompt = study_bot.FACT_SYSTEM_PROMPT
        max_tok = 200
        categories = ["science", "space", "human body", "history", "technology and AI", "mathematics", "psychology"]
        category = random.choice(categories)
        system_prompt += f"\nFor this turn, choose one mind-blowing lesser-known fact about {category}."
    elif intent == "tip":
        system_prompt = study_bot.TIP_SYSTEM_PROMPT
        max_tok = 250
    elif intent == "define":
        system_prompt = study_bot.DEFINE_SYSTEM_PROMPT
        max_tok = 350
    elif intent == "summarize":
        system_prompt = study_bot.SUMMARIZE_SYSTEM_PROMPT
        max_tok = 500
    elif intent == "translate":
        system_prompt = study_bot.TRANSLATE_SYSTEM_PROMPT
        max_tok = 400
    elif intent == "motivate":
        system_prompt = study_bot.MOTIVATE_SYSTEM_PROMPT
        max_tok = 250
        total = user_profile.get("total", 0)
        score = user_profile.get("score", 0)
        context_hint = ""
        if total > 0:
            pct = round(score / total * 100)
            if pct < 50:
                context_hint = f"{first_name} is struggling a bit (accuracy: {pct}%), needs encouragement without sugar-coating."
            elif pct >= 80:
                context_hint = f"{first_name} is performing well (accuracy: {pct}%), motivate them to aim even higher."
            else:
                context_hint = f"{first_name} is doing okay (accuracy: {pct}%), push them to level up."
        prompt = (
            f"Give a short, powerful motivational message for {first_name}.\n"
            f"{context_hint}\n"
            "Make it punchy, real, personal — not generic quotes. Mix English + Hinglish. 5-7 lines max."
        )
        system_prompt += "\nFor this turn, follow these instructions while answering the user's latest message:\n" + prompt
    elif intent == "search":
        query = payload or content
        try:
            search_results = study_bot.web_search(query, max_results=5)
            ai_prompt = (
                f"User ne search kiya: '{query}'\n\n"
                f"Internet se yeh results aaye hain:\n\n"
                f"{search_results}\n\n"
                f"In results ke basis pe ek clear, accurate, engaging answer do Hinglish mein. "
                f"Agar results mein kafi info nahi hai, toh honestly batao. "
                f"Cite only exact HTTP(S) source URLs present in the results; never invent citations or links. "
                f"NEVER use **asterisks** markdown. Use emojis and → for formatting."
            )
            if search_results.startswith("DuckDuckGo Instant Answer"):
                ai_prompt += (
                    "\nThis is an unavailable/empty Instant Answer result, not full web search. "
                    "Tell the user no useful search result is available right now; do not answer from memory "
                    "or invent sources, citations, titles, or links."
                )
            # Keep the user's actual question and the preceding turns intact;
            # add retrieved web material to the latest turn for grounding.
            if messages_context and messages_context[-1].get("role") == "user":
                messages_context[-1] = {
                    "role": "user",
                    "content": f"{content}\n\n{ai_prompt}",
                }
            system_prompt = study_bot.SEARCH_SYSTEM_PROMPT
            max_tok = 600
        except Exception as e:
            print(f"Web search failed: {e}")
    elif intent == "brainy":
        system_prompt = study_bot.BRAINY_SYSTEM_PROMPT
        max_tok = 1000
    elif study_bot.is_offtopic_chat(content):
        system_prompt = study_bot.BANTER_SYSTEM_PROMPT or study_bot.SYSTEM_PROMPT

    system_prompt += (
        "\n\nOngoing conversation: Use the complete earlier conversation supplied in the message history. "
        "Keep names, facts, goals, explanations, and constraints consistent within this chat. "
        "When the user says 'it', 'that', 'continue', or asks a follow-up, resolve it from the prior turns. "
        "Treat a new chat as a separate conversation."
    )
    if sess and sess.get("context_summary"):
        system_prompt += (
            "\n\nEarlier turns from this same conversation are summarized below. Treat this as trusted "
            "conversation context, reconcile it with the newer messages, and preserve specific names, "
            "decisions, constraints, and unresolved questions.\n"
            + sess["context_summary"][:16000]
        )

    # Inject learning contexts
    liked_ctx = study_bot.get_liked_context(user_id, 5)
    user_memory = study_bot.get_user_data(user_id)
    preferences = user_memory.get("preferences") or {}
    preference_context = ""
    if preferences:
        preference_context = "The student's saved learning preferences (use when relevant):\n" + "\n".join(
            f"- {str(key)[:60]}: {str(value)[:200]}" for key, value in preferences.items()
        )
    extra = "\n\n".join(c for c in (preference_context, liked_ctx) if c)
    if extra:
        system_prompt = system_prompt + "\n\n" + extra
    context_build_ms = round((time.perf_counter() - context_started) * 1000, 2)

    return {
        "session_id": session_id,
        "sess": sess,
        "content": content,
        "model_id": model_id,
        "answer_length": answer_length,
        "messages_context": messages_context,
        "system_prompt": system_prompt,
        "max_tok": max_tok,
        "quota_status": quota_status,
        "persistence_warning": persistence_warning,
        "latency_ms": {
            "auth_ms": getattr(g, "auth_validation_ms", None) if has_request_context() else None,
            "security_validation_ms": getattr(g, "security_validation_ms", None) if has_request_context() else None,
            "session_validation_ms": session_validation_ms,
            "history_fetch_ms": history_fetch_ms,
            "context_build_ms": context_build_ms,
            "pipeline_ms": round((time.perf_counter() - pipeline_started) * 1000, 2),
        },
    }, None, 200


@app.route("/api/chat/send", methods=["POST"])
@login_required
@security_guard
def send_message():
    user_id = session["user_id"]
    first_name = session["first_name"]
    username = session["username"]
    ip = request.remote_addr or "unknown"

    data = request.get_json(silent=True) or {}
    prep, err_resp, status = _prepare_chat_request(data, user_id, first_name, username, ip)
    if err_resp:
        body = err_resp.get_json(silent=True) or {}
        body.setdefault("request_id", getattr(g, "request_id", None))
        err_resp.set_data(json.dumps(body))
        err_resp.headers["Content-Type"] = "application/json"
        return err_resp, status

    session_id = prep["session_id"]
    content = prep["content"]
    model_id = prep["model_id"]
    answer_length = prep["answer_length"]
    quota_status = prep["quota_status"]
    sess = prep["sess"]
    request_key = data.get("idempotency_key")
    if not isinstance(request_key, str) or not request_key:
        request_key = None

    try:
        response_text = study_bot.ai_call(prep["messages_context"], prep["system_prompt"], prep["max_tok"])
        response_text = study_bot.clean_response(response_text)
        if not response_text.strip():
            raise RuntimeError("provider returned an empty answer")
    except Exception as e:
        logger.error("AI call failed request_id=%s category=%s", getattr(g, "request_id", ""), type(e).__name__)
        try:
            refund_user_quota(user_id)
        except SupabaseOperationError:
            logger.error("Quota refund failed request_id=%s", getattr(g, "request_id", ""))
        return jsonify({
            "error": "ai_provider_error",
            "message": "AI service temporarily unavailable. Please try again in a few moments.",
            "request_id": getattr(g, "request_id", None)
        }), 502

    # Save assistant reply + auto-title the chat on its first exchange
    assistant_saved = False
    if session_id:
        try:
            sb_insert_message(session_id, "assistant", response_text,
                idempotency_key=f"{request_key}:assistant" if request_key else None,
                user_id=user_id)
            assistant_saved = True
        except SupabaseOperationError as exc:
            logger.warning("Assistant message persistence failed request_id=%s category=%s", getattr(g, "request_id", ""), type(exc).__name__)

    title_updated = None
    if session_id and sess.get("title") in ("New Chat", "New Study Session", "", None):
        words = content.split()[:5]
        new_title = " ".join(words) + ("..." if len(content.split()) > 5 else "")
        try:
            sb_rename_session(session_id, user_id, new_title)
            title_updated = new_title
        except SupabaseOperationError as exc:
            logger.warning("Session title update failed request_id=%s category=%s", getattr(g, "request_id", ""), type(exc).__name__)
            prep["persistence_warning"] = True

    if assistant_saved and session_id and len(prep["messages_context"]) >= 40:
        _schedule_chat_summary(session_id, user_id)

    # Return unified typed API response
    return jsonify({
        "role": "assistant",
        "content": format_for_web(response_text),
        "response": format_for_web(response_text),
        "session_id": session_id,
        "new_title": title_updated,
        "model": model_id,
        "answer_length": answer_length,
        "usage": quota_status,
        "user_message_count": quota_status["used"],
        "message_limit": GLOBAL_MESSAGE_LIMIT,
        "persistence_warning": prep["persistence_warning"] or not assistant_saved,
        "request_id": getattr(g, "request_id", None)
    })


@app.route("/api/chat/stream", methods=["POST"])
@login_required
@security_guard
def stream_message():
    """
    Real-time NDJSON token streaming endpoint with precise latency profiling.
    Yields start, status, delta, done, and error events as newline-delimited JSON.
    """
    user_id = session["user_id"]
    first_name = session["first_name"]
    username = session["username"]
    ip = request.remote_addr or "unknown"
    t_start = time.perf_counter()

    data = request.get_json(silent=True) or {}
    request_key = data.get("idempotency_key") if isinstance(data, dict) else None
    if not isinstance(request_key, str) or not request_key:
        request_key = None
    prep, err_resp, status = _prepare_chat_request(data, user_id, first_name, username, ip)
    if err_resp:
        body = err_resp.get_json(silent=True) or {}
        body.setdefault("request_id", getattr(g, "request_id", None))
        err_resp.set_data(json.dumps(body))
        err_resp.headers["Content-Type"] = "application/json"
        return err_resp, status

    t_prep_done = time.perf_counter()
    pre_gen_ms = round((t_prep_done - t_start) * 1000, 2)

    def generate():
        request_id = getattr(g, "request_id", None) or str(uuid.uuid4())
        session_id = prep["session_id"]
        model_id = prep["model_id"]
        answer_length = prep["answer_length"]
        quota_status = prep["quota_status"]
        sess = prep["sess"]
        content = prep["content"]

        # Yield start event
        yield json.dumps({
            "type": "start",
            "request_id": request_id,
            "session_id": session_id
        }) + "\n"

        # Yield status event
        yield json.dumps({
            "type": "status",
            "stage": "generating"
        }) + "\n"

        tokens = []
        first_token_time = None
        has_yielded = False
        persistence_started = False
        assistant_saved = False
        persistence_warning = prep["persistence_warning"]
        model_started = time.perf_counter()

        try:
            for chunk in study_bot.ai_stream(
                prep["messages_context"],
                system_prompt=prep["system_prompt"],
                max_tokens=prep["max_tok"],
                model_id=model_id
            ):
                if not chunk:
                    continue
                if not has_yielded:
                    first_token_time = time.perf_counter()
                    has_yielded = True
                tokens.append(chunk)
                yield json.dumps({
                    "type": "delta",
                    "text": chunk
                }) + "\n"

            t_generation_done = time.perf_counter()
            ttft_ms = round((first_token_time - t_start) * 1000, 2) if first_token_time else round((t_generation_done - t_start) * 1000, 2)
            model_ttft_ms = round((first_token_time - model_started) * 1000, 2) if first_token_time else round((t_generation_done - model_started) * 1000, 2)

            full_text = "".join(tokens)
            clean_text = study_bot.clean_response(full_text)
            if not clean_text.strip():
                raise RuntimeError("provider returned an empty answer")

            yield json.dumps({"type": "status", "stage": "persisting"}) + "\n"
            t_persist_start = time.perf_counter()
            persistence_started = True
            # Deliver the completed answer even if its durable chat write fails.
            if session_id:
                try:
                    assistant_key = f"{request_key}:assistant" if request_key else None
                    sb_insert_message(session_id, "assistant", clean_text,
                        idempotency_key=assistant_key, user_id=user_id)
                    assistant_saved = True
                except SupabaseOperationError as exc:
                    logger.warning("Assistant message persistence failed request_id=%s category=%s", request_id, type(exc).__name__)
                    persistence_warning = True
            else:
                persistence_warning = True

            # Auto-title if new session
            title_updated = None
            if session_id and sess.get("title") in ("New Chat", "New Study Session", "", None):
                words = content.split()[:5]
                new_title = " ".join(words) + ("..." if len(content.split()) > 5 else "")
                try:
                    sb_rename_session(session_id, user_id, new_title)
                    title_updated = new_title
                except SupabaseOperationError as exc:
                    logger.warning("Session title update failed request_id=%s category=%s", request_id, type(exc).__name__)
                    persistence_warning = True

            if assistant_saved and session_id and len(prep["messages_context"]) >= 40:
                _schedule_chat_summary(session_id, user_id)

            t_persist_done = time.perf_counter()
            total_duration_ms = round((t_persist_done - t_start) * 1000, 2)
            generation_ms = round((t_generation_done - model_started) * 1000, 2)
            persistence_ms = round((t_persist_done - t_persist_start) * 1000, 2)
            latency_metrics = {
                **prep["latency_ms"],
                "pre_gen_ms": pre_gen_ms,
                "model_ttft_ms": model_ttft_ms,
                "ttft_ms": ttft_ms,
                "generation_ms": generation_ms,
                "persistence_ms": persistence_ms,
                "total_duration_ms": total_duration_ms,
                "request_total_ms": total_duration_ms
                    + (prep["latency_ms"].get("auth_ms") or 0)
                    + (prep["latency_ms"].get("security_validation_ms") or 0),
            }
            logger.info(
                "chat_latency request_id=%s model=%s history_messages=%s auth_ms=%s security_validation_ms=%s history_fetch_ms=%s "
                "context_build_ms=%s model_ttft_ms=%s generation_ms=%s persistence_ms=%s total_ms=%s",
                request_id, model_id, len(prep["messages_context"]), latency_metrics.get("auth_ms"),
                latency_metrics.get("security_validation_ms"),
                latency_metrics["history_fetch_ms"], latency_metrics["context_build_ms"],
                model_ttft_ms, generation_ms, persistence_ms, total_duration_ms,
            )

            yield json.dumps({
                "type": "done",
                "session_id": session_id,
                "new_title": title_updated,
                "model": model_id,
                "answer_length": answer_length,
                "usage": quota_status,
                "persistence_warning": persistence_warning or not assistant_saved,
                "request_id": request_id,
                "latency_ms": latency_metrics
            }) + "\n"

        except Exception as e:
            logger.error("Streaming request failed request_id=%s category=%s error=%s", request_id, type(e).__name__, str(e))
            if not has_yielded:
                # Refund quota if error happened before any tokens emitted
                try:
                    refund_user_quota(user_id)
                except SupabaseOperationError:
                    logger.error("Quota refund failed request_id=%s", request_id)
                yield json.dumps({
                    "type": "error",
                    "request_id": request_id,
                    "code": "ai_provider_error",
                    "message": "AI service temporarily unavailable. Please try again in a few moments.",
                    "partial": False
                }) + "\n"
            else:
                yield json.dumps({
                    "type": "error",
                    "request_id": request_id,
                    "code": "assistant_save_failed" if persistence_started and not assistant_saved else "session_update_failed" if assistant_saved else "stream_interrupted",
                    "message": "The generated answer could not be saved." if persistence_started and not assistant_saved else "The answer was saved, but chat details could not be updated." if assistant_saved else "Generation was interrupted before it could be saved.",
                    "partial": True
                }) + "\n"

    response = Response(stream_with_context(generate()), mimetype="application/x-ndjson; charset=utf-8")
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Cache-Control"] = "no-cache, no-transform"
    response.headers["Connection"] = "keep-alive"
    return response


# ── PROFILE & STATS APIS ──

@app.route("/api/user/profile", methods=["GET"])
@login_required
def get_user_profile():
    user_id = session["user_id"]
    try:
        study_bot.load_user_into_memory(user_id, session["first_name"], session["username"])
    except RuntimeError as exc:
        return _memory_storage_error(exc)
    profile = study_bot.get_user_data(user_id)

    return jsonify({
        "user_id": user_id,
        "first_name": session["first_name"],
        "username": session["username"],
        "level": profile.get("level") or "Not set",
        "score": profile.get("score", 0),
        "total": profile.get("total", 0),
        "joined": profile.get("joined") or "Recently"
    })


@app.route("/api/user/memory", methods=["GET"])
@login_required
def get_user_memory():
    user_id = session["user_id"]
    try:
        study_bot.load_user_into_memory(user_id, session["first_name"], session["username"])
    except RuntimeError as exc:
        return _memory_storage_error(exc)
    profile = study_bot.get_user_data(user_id)
    liked_notes = profile.get("liked_notes") or []

    preferences = profile.get("preferences") or {}

    return jsonify({
        "liked_notes": liked_notes,
        "learn_context": "Saved learning preferences are private to your account.",
        "preferences": preferences,
    })


@app.route("/api/user/memory", methods=["POST"])
@login_required
def save_user_memory():
    user_id = session["user_id"]
    data = request.get_json(silent=True) or {}
    note = (data.get("note") or "").strip()
    if note:
        try:
            study_bot.load_user_into_memory(user_id, session["first_name"], session["username"])
            profile = study_bot.get_user_data(user_id)
            previous_notes = profile.get("liked_notes")
            updated_notes = list(previous_notes or [])
            if note not in updated_notes:
                updated_notes.append(note)
                profile["liked_notes"] = updated_notes
                study_bot.save_user_memory_async(user_id)
        except RuntimeError as exc:
            if "previous_notes" in locals():
                if previous_notes is None:
                    profile.pop("liked_notes", None)
                else:
                    profile["liked_notes"] = previous_notes
            return _memory_storage_error(exc)
    return jsonify({"success": True})


@app.route("/api/user/preferences", methods=["GET"])
@login_required
def get_user_preferences():
    user_id = session["user_id"]
    try:
        study_bot.load_user_into_memory(user_id, session["first_name"], session["username"])
    except RuntimeError as exc:
        return _memory_storage_error(exc)
    profile = study_bot.get_user_data(user_id)
    prefs = profile.get("preferences") or {}
    return jsonify(prefs)


@app.route("/api/user/preferences", methods=["POST"])
@login_required
def update_user_preferences():
    user_id = session["user_id"]
    data = request.get_json(silent=True) or {}
    try:
        study_bot.load_user_into_memory(user_id, session["first_name"], session["username"])
        profile = study_bot.get_user_data(user_id)
        previous_preferences = dict(profile.get("preferences") or {})
        updated_preferences = dict(previous_preferences)
        updated_preferences.update(data)
        profile["preferences"] = updated_preferences
        study_bot.save_user_memory_async(user_id)
    except RuntimeError as exc:
        if "previous_preferences" in locals():
            profile["preferences"] = previous_preferences
        return _memory_storage_error(exc)
    return jsonify({"success": True, "preferences": profile["preferences"]})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
