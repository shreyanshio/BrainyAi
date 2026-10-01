"""Brainy-AI REST API & Web Sanctuary Gateway.
Provides session authorization, cross-origin security headers, and AI proxy routing.
"""
import os
import re
import uuid
import hmac
import hashlib
import json
import urllib.parse
import random
import logging
import requests
from datetime import datetime, timezone, timedelta
from html import escape
from functools import wraps
from flask import Flask, request, jsonify, session, send_from_directory, redirect
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import AI + Supabase helpers from study_bot (same Supabase project the Telegram bot uses)
import study_bot

# Security module — input sanitization, rate limiting, blacklist, headers
from security import (
    security_guard, login_required, sanitize_input,
    is_blacklisted, check_rate_limit, log_security_event, security_headers
)

app = Flask(__name__)

_allowed_origins = os.getenv("ALLOWED_ORIGINS")
if _allowed_origins:
    CORS(app, supports_credentials=True, origins=[o.strip() for o in _allowed_origins.split(",")])
else:
    CORS(app, supports_credentials=True)  # Enable cross-origin session authentication

import secrets as _secrets
_secret_key = os.getenv("FLASK_SECRET_KEY")
if not _secret_key:
    _secret_key = _secrets.token_hex(32)
    print("[WARNING] FLASK_SECRET_KEY is not set! Using a random one-off key for this "
          "process — all users will be logged out on every restart/deploy. Set "
          "FLASK_SECRET_KEY in Railway's environment variables to fix this.")
app.secret_key = _secret_key
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
    """Decorator: only allow logged-in users on the admin allowlist."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        if not is_admin_session():
            return jsonify({"error": "Admin access required"}), 403
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
    log_security_event("uncaught_exception", request.remote_addr or "unknown", session.get("user_id"), str(e)[:200])
    return jsonify({"error": "Unexpected error. Please try again."}), 500

SUPABASE_URL = os.getenv("SUPABASE_URL") or study_bot.SUPABASE_URL
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY") or study_bot.SUPABASE_KEY

# ── SECURE HASH ENCRYPTION FOR CHAT TITLES & USER QUESTIONS ──
# Prevents sensitive user questions and chat titles from leaking if the Supabase database is dumped
import base64

def mask_secure_hash(text: str) -> str:
    """Encrypt and format plain text into a secure hash-encoded representation for Supabase storage."""
    if not text:
        return text
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', _secret_key.encode('utf-8'), salt, 50000, dklen=32)
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
        raw = base64.urlsafe_b64decode(stored_val[7:].encode('ascii'))
        if len(raw) < 32:
            return stored_val
        salt = raw[:16]
        mac = raw[16:32]
        ciphertext = raw[32:]
        key = hashlib.pbkdf2_hmac('sha256', _secret_key.encode('utf-8'), salt, 50000, dklen=32)
        expected_mac = hmac.new(key, ciphertext, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(mac, expected_mac):
            return stored_val
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(ciphertext):
            keystream.extend(hmac.new(key, counter.to_bytes(4, 'big'), hashlib.sha256).digest())
            counter += 1
        plain_bytes = bytes(a ^ b for a, b in zip(ciphertext, keystream[:len(ciphertext)]))
        return plain_bytes.decode('utf-8', errors='replace')
    except Exception as e:
        logger.warning("Decryption of masked hash failed: %s", e)
        return stored_val

# ── GLOBAL USER MESSAGE QUOTA: 30 MESSAGES PER 8 HOURS ──
GLOBAL_MESSAGE_LIMIT = 30
QUOTA_WINDOW_HOURS = 8
QUOTA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_quotas.json")

import threading
_quota_lock = threading.Lock()
_user_quotas: dict = {}

def _load_user_quotas():
    global _user_quotas
    if os.path.exists(QUOTA_FILE):
        try:
            with open(QUOTA_FILE, "r", encoding="utf-8") as f:
                _user_quotas = json.load(f)
        except Exception as e:
            logger.warning("Could not load user_quotas.json: %s", e)
            _user_quotas = {}

def _save_user_quotas():
    try:
        with open(QUOTA_FILE, "w", encoding="utf-8") as f:
            json.dump(_user_quotas, f, indent=2)
    except Exception as e:
        logger.warning("Could not save user_quotas.json: %s", e)

_load_user_quotas()

def get_user_quota(user_id: int | str) -> dict:
    """Return current quota status, automatically rolling over expired 8-hour windows."""
    with _quota_lock:
        uid_str = str(user_id)
        now = datetime.now(timezone.utc)
        record = _user_quotas.get(uid_str)
        if record:
            try:
                reset_at = datetime.fromisoformat(record["reset_at"])
            except Exception:
                reset_at = now
            if now >= reset_at:
                record = {
                    "count": 0,
                    "reset_at": (now + timedelta(hours=QUOTA_WINDOW_HOURS)).isoformat(),
                    "window_start": now.isoformat()
                }
                _user_quotas[uid_str] = record
                _save_user_quotas()
        else:
            record = {
                "count": 0,
                "reset_at": (now + timedelta(hours=QUOTA_WINDOW_HOURS)).isoformat(),
                "window_start": now.isoformat()
            }
            _user_quotas[uid_str] = record
            _save_user_quotas()

        used = record["count"]
        remaining = max(0, GLOBAL_MESSAGE_LIMIT - used)
        return {
            "used": used,
            "limit": GLOBAL_MESSAGE_LIMIT,
            "remaining": remaining,
            "reset_at": record["reset_at"],
            "window_hours": QUOTA_WINDOW_HOURS
        }

def consume_user_quota(user_id: int | str) -> tuple[bool, dict]:
    """Atomically check and consume 1 message credit from the user's 8h quota."""
    with _quota_lock:
        status = get_user_quota(user_id)
        if status["used"] >= GLOBAL_MESSAGE_LIMIT:
            return False, status

        uid_str = str(user_id)
        _user_quotas[uid_str]["count"] += 1
        _save_user_quotas()
        return True, get_user_quota(user_id)

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


# ── SUPABASE HELPERS (chat_sessions / chat_messages / user_logins) ──

def _sb_headers(prefer: str | None = None) -> dict:
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def sb_record_login(user_id: int, username: str, first_name: str, login_type: str = "web", ip: str = "", user_agent: str = "") -> None:
    """Record user login event in Supabase user_logins table."""
    try:
        payload = {
            "user_id": user_id,
            "username": username or "",
            "first_name": first_name or "",
            "login_type": login_type,
            "ip_address": ip or "",
            "user_agent": user_agent[:250] if user_agent else ""
        }
        requests.post(
            f"{SUPABASE_URL}/rest/v1/user_logins",
            headers=_sb_headers("return=minimal"), json=payload, timeout=5
        )
    except Exception as e:
        logger.warning("Supabase record login error (non-fatal): %s", e)


def sb_list_sessions(user_id: int) -> list:
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/chat_sessions"
            f"?user_id=eq.{user_id}&select=id,title,created_at&order=created_at.desc",
            headers=_sb_headers(), timeout=8
        )
        if r.status_code == 200:
            rows = r.json()
            for row in rows:
                if row.get("title"):
                    row["title"] = unmask_secure_hash(row["title"])
            return rows
    except Exception as e:
        logger.warning("Supabase list_sessions error: %s", e)

    return MEM_SESSIONS.get(user_id, [])


def sb_create_session(user_id: int, title: str, session_id: str | None = None) -> dict:
    if not session_id:
        session_id = str(uuid.uuid4())
    # Hash title before saving in Supabase so plain title never leaks
    payload = {"id": session_id, "user_id": user_id, "title": mask_secure_hash(title)}

    # Save in memory cache with plain title
    sess_obj = {"id": session_id, "user_id": user_id, "title": title, "created_at": datetime.now(timezone.utc).isoformat()}
    if user_id not in MEM_SESSIONS:
        MEM_SESSIONS[user_id] = []
    if not any(s["id"] == session_id for s in MEM_SESSIONS[user_id]):
        MEM_SESSIONS[user_id].insert(0, sess_obj)

    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/chat_sessions",
            headers=_sb_headers("return=representation"), json=payload, timeout=8
        )
        if r.status_code in (200, 201):
            created = r.json()[0]
            created["title"] = unmask_secure_hash(created.get("title", title))
            return created
    except Exception as e:
        logger.warning("Supabase create_session error (using memory cache): %s", e)

    return sess_obj


def sb_get_session(session_id: str, user_id: int) -> dict | None:
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/chat_sessions"
            f"?id=eq.{session_id}&user_id=eq.{user_id}&select=id,title",
            headers=_sb_headers(), timeout=8
        )
        if r.status_code == 200:
            rows = r.json()
            if rows:
                row = rows[0]
                row["title"] = unmask_secure_hash(row.get("title", ""))
                return row
    except Exception as e:
        logger.warning("Supabase get_session error: %s", e)

    # Check memory cache
    user_sessions = MEM_SESSIONS.get(user_id, [])
    for s in user_sessions:
        if s["id"] == session_id:
            return s

    return sb_create_session(user_id, "New Study Session", session_id=session_id)


def sb_rename_session(session_id: str, user_id: int, title: str) -> None:
    for s in MEM_SESSIONS.get(user_id, []):
        if s["id"] == session_id:
            s["title"] = title
    try:
        # Hash title before patching Supabase
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/chat_sessions?id=eq.{session_id}&user_id=eq.{user_id}",
            headers=_sb_headers(), json={"title": mask_secure_hash(title)}, timeout=8
        )
    except Exception as e:
        logger.warning("Supabase rename_session error: %s", e)


def sb_delete_session(session_id: str, user_id: int) -> None:
    if user_id in MEM_SESSIONS:
        MEM_SESSIONS[user_id] = [s for s in MEM_SESSIONS[user_id] if s["id"] != session_id]
    MEM_MESSAGES.pop(session_id, None)

    try:
        requests.delete(
            f"{SUPABASE_URL}/rest/v1/chat_sessions?id=eq.{session_id}&user_id=eq.{user_id}",
            headers=_sb_headers(), timeout=8
        )
    except Exception as e:
        logger.warning("Supabase delete_session error: %s", e)


def sb_get_messages(session_id: str) -> list:
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/chat_messages"
            f"?session_id=eq.{session_id}&select=role,content,created_at&order=id.asc",
            headers=_sb_headers(), timeout=8
        )
        if r.status_code == 200:
            msgs = r.json()
            for m in msgs:
                if m.get("content"):
                    m["content"] = unmask_secure_hash(m["content"])
            return msgs
    except Exception as e:
        logger.warning("Supabase get_messages error: %s", e)

    return MEM_MESSAGES.get(session_id, [])


def sb_get_recent_messages(session_id: str, limit: int = 15) -> list:
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/chat_messages"
            f"?session_id=eq.{session_id}&select=role,content,created_at&order=id.desc&limit={limit}",
            headers=_sb_headers(), timeout=8
        )
        if r.status_code == 200:
            msgs = list(reversed(r.json()))
            for m in msgs:
                if m.get("content"):
                    m["content"] = unmask_secure_hash(m["content"])
            return msgs
    except Exception as e:
        logger.warning("Supabase get_recent_messages error: %s", e)

    msgs = MEM_MESSAGES.get(session_id, [])
    return msgs[-limit:]


def sb_insert_message(session_id: str, role: str, content: str) -> None:
    msg_obj = {"role": role, "content": content, "created_at": datetime.now(timezone.utc).isoformat()}
    if session_id not in MEM_MESSAGES:
        MEM_MESSAGES[session_id] = []
    MEM_MESSAGES[session_id].append(msg_obj)

    try:
        # Questions asked by the user are stored as secure hash values so they cannot leak from Supabase
        stored_content = mask_secure_hash(content) if role == "user" else content
        payload = {"session_id": session_id, "role": role, "content": stored_content}
        requests.post(
            f"{SUPABASE_URL}/rest/v1/chat_messages",
            headers=_sb_headers("return=minimal"), json=payload, timeout=8
        )
    except Exception as e:
        logger.warning("Supabase insert_message error (stored in memory): %s", e)



def sb_count_user_messages(session_id: str) -> int:
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
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/user_logins"
            f"?select=user_id,username,first_name,login_type,ip_address,created_at"
            f"&order=created_at.desc&limit={limit}",
            headers=_sb_headers(), timeout=10
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.warning("Supabase get_all_logins error: %s", e)
    return []


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
    frontend_url = os.getenv("FRONTEND_URL", "https://brainyai.cenai.workers.dev")
    return redirect(frontend_url, code=302)


@app.route("/api/config", methods=["GET"])
def get_config():
    """Expose public environment configuration (e.g. Google OAuth Client ID)."""
    return jsonify({
        "google_client_id": os.environ.get("GOOGLE_CLIENT_ID", "")
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
        auth_sessions.pop(session_id, None)
        return jsonify({"status": "authenticated", "user": user})

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

        return jsonify({"status": "authenticated", "user": user_data})
    return jsonify({"error": "Invalid signature"}), 401


@app.route("/api/auth/web", methods=["POST"])
@security_guard
def auth_web():
    """Handle direct web login with Name and optional Username."""
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

    # Ensure user memory in study_bot / Supabase
    study_bot.load_user_into_memory(user_id, name, username)

    # Record login in Supabase user_logins table
    sb_record_login(
        user_id=user_id,
        username=username,
        first_name=name,
        login_type="web",
        ip=request.remote_addr or "",
        user_agent=request.headers.get("User-Agent", "")
    )

    return jsonify({
        "status": "authenticated",
        "user": {
            "id": user_id,
            "first_name": name,
            "username": username
        }
    })


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    """Check current authentication status."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False}), 401
    return jsonify({
        "authenticated": True,
        "user": {
            "id": user_id,
            "first_name": session.get("first_name", "Student"),
            "username": session.get("username", ""),
            "photo_url": session.get("photo_url", "")
        }
    })


@app.route("/api/auth/google", methods=["POST"])
def auth_google():
    """Handle Google Identity Services login credential token.
    Supports both local google.oauth2 verification and Google public tokeninfo API fallback.
    """
    data = request.json or {}
    token = data.get("credential")
    if not token:
        return jsonify({"error": "Missing Google credential token"}), 400

    id_info = None
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "")

    # 1. Attempt verification with client ID if configured
    if google_client_id:
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests
            id_info = id_token.verify_oauth2_token(
                token, google_requests.Request(), google_client_id
            )
        except Exception as e:
            logger.warning("Google token verification with client ID failed: %s", e)

    # 2. Resilient fallback: verify signature and payload directly with Google's public tokeninfo endpoint
    if not id_info:
        try:
            g_resp = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={token}", timeout=8)
            if g_resp.status_code == 200:
                id_info = g_resp.json()
            else:
                logger.warning("Google tokeninfo returned status %s: %s", g_resp.status_code, g_resp.text[:150])
        except Exception as ge:
            logger.warning("Call to Google tokeninfo failed: %s", ge)

    if not id_info:
        return jsonify({"error": "Google token verification failed. Please try again or use Telegram login."}), 401

    email_verified = id_info.get("email_verified")
    if email_verified not in (True, "true"):
        return jsonify({"error": "Google account email is not verified."}), 401

    email = id_info.get("email", "")
    name = id_info.get("name") or (email.split("@")[0] if email else "Google Student")
    google_sub = id_info.get("sub") or email or name
    picture = id_info.get("picture", "")

    # Deterministic integer user_id
    user_id = int(hashlib.md5(f"google_{google_sub}".encode()).hexdigest(), 16) % (10**9)
    username = email.split("@")[0] if email else name.lower().replace(" ", "_")

    session["user_id"] = user_id
    session["first_name"] = name
    session["username"] = username
    session["email"] = email.strip().lower()
    session["photo_url"] = picture

    # Ensure user memory in study_bot
    study_bot.load_user_into_memory(user_id, name, username)

    # Record login in Supabase
    sb_record_login(
        user_id=user_id,
        username=username,
        first_name=name,
        login_type="google",
        ip=request.remote_addr or "",
        user_agent=request.headers.get("User-Agent", "")
    )

    return jsonify({
        "status": "authenticated",
        "user": {
            "id": user_id,
            "first_name": name,
            "username": username,
            "email": email,
            "picture": picture,
            "photo_url": picture
        }
    })


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

    # Ensure user memory in study_bot and Supabase
    study_bot.load_user_into_memory(user_id, name, username)

    # Record login event in Supabase user_logins table
    sb_record_login(
        user_id=user_id,
        username=username,
        first_name=name,
        login_type="student_pass",
        ip=request.remote_addr or "",
        user_agent=request.headers.get("User-Agent", "")
    )

    return jsonify({
        "status": "authenticated",
        "user": {
            "id": user_id,
            "first_name": name,
            "username": username
        }
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


@app.route("/api/admin/usage", methods=["GET"])
@admin_required
def admin_usage():
    """Admin-only: registered users, login activity, and message counts."""
    try:
        return jsonify(build_usage_report())
    except Exception as e:
        logger.error("admin_usage error: %s", e)
        return jsonify({"error": "Failed to build usage report"}), 500


# login_required and security_guard are imported from security.py


# ── CHAT SESSION APIS ──

@app.route("/api/sessions", methods=["GET"])
@login_required
def get_sessions():
    user_id = session["user_id"]
    try:
        return jsonify(sb_list_sessions(user_id))
    except Exception as e:
        print(f"get_sessions failed: {e}")
        return jsonify({"error": "Could not load sessions"}), 500


@app.route("/api/sessions", methods=["POST"])
@login_required
def create_session():
    user_id = session["user_id"]
    data = request.json or {}
    title = data.get("title", "New Chat")
    try:
        row = sb_create_session(user_id, title)
        return jsonify({"id": row["id"], "title": row["title"]})
    except Exception as e:
        print(f"create_session failed: {e}")
        return jsonify({"error": "Could not create session"}), 500


@app.route("/api/sessions/<session_id>", methods=["PATCH"])
@login_required
def rename_session(session_id):
    user_id = session["user_id"]
    data = request.json or {}
    title = data.get("title")
    if not title:
        return jsonify({"error": "Title required"}), 400
    sb_rename_session(session_id, user_id, title)
    return jsonify({"status": "ok"})


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
@login_required
def delete_session(session_id):
    user_id = session["user_id"]
    sb_delete_session(session_id, user_id)
    return jsonify({"status": "ok"})


@app.route("/api/usage", methods=["GET"])
@login_required
def get_usage():
    """Returns the user's global 8-hour window quota status."""
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

    messages = sb_get_messages(session_id)
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
    body {{ margin:0; font-family: Inter, system-ui, -apple-system, Segoe UI, sans-serif; background:#0b0a14; color:#ede7f6; }}
    main {{ max-width: 780px; margin: 0 auto; padding: 48px 20px; }}
    h1 {{ font-size: 20px; margin: 0 0 18px; }}
    article {{ white-space: pre-wrap; line-height: 1.65; background:#14111f; border:1px solid #322a4d; border-radius:14px; padding:22px; }}
  </style>
</head>
<body><main><h1>{title}</h1><article>{content}</article></main></body>
</html>"""


@app.route("/api/chat/send", methods=["POST"])
@login_required
@security_guard
def send_message():
    user_id = session["user_id"]
    first_name = session["first_name"]
    username = session["username"]
    ip = request.remote_addr or "unknown"

    data = request.json or {}
    session_id = data.get("session_id")
    # Unified contract: accept both 'message' and 'content'
    content = (data.get("message") or data.get("content") or "").strip()
    model_id = (data.get("model") or "brainy-balanced").strip().lower()
    answer_length = (data.get("answer_length") or "medium").strip().lower()

    if not content:
        return jsonify({"error": "Message content cannot be empty"}), 400

    # Ensure session exists or auto-create it
    if not session_id:
        new_sess = sb_create_session(user_id, "New Study Session")
        session_id = new_sess["id"]
        sess = new_sess
    else:
        sess = sb_get_session(session_id, user_id)
        if not sess:
            sess = sb_create_session(user_id, "New Study Session", session_id=session_id)

    # Sanitize user input
    content = sanitize_input(content)

    # Blacklist check
    if is_blacklisted(content):
        log_security_event("blacklist_blocked", ip, user_id, content[:100])
        return jsonify({"error": "Invalid input detected."}), 403

    # Per-user rate limit: 10 messages per minute
    if not check_rate_limit("user_{}".format(user_id), limit=10, window=60):
        log_security_event("user_rate_limit", ip, user_id, "")
        return jsonify({"error": "Message rate limit reached. Please wait a moment."}), 429

    # Enforce atomic 30 messages / 8 hours user quota BEFORE spending AI tokens
    allowed, quota_status = consume_user_quota(user_id)
    if not allowed:
        return jsonify({
            "error": "quota_exceeded",
            "message": f"You have reached your 8-hour limit of {GLOBAL_MESSAGE_LIMIT} messages. Quota resets at {quota_status['reset_at']}.",
            "usage": quota_status,
            "user_message_count": quota_status["used"],
            "message_limit": GLOBAL_MESSAGE_LIMIT
        }), 429

    # Save user message
    sb_insert_message(session_id, "user", content)

    # Fetch last 15 messages (now including the one we just saved) for context
    messages_context = [{"role": m["role"], "content": m["content"]} for m in sb_get_recent_messages(session_id, 15)]

    # Run intent detection
    intent, payload = study_bot.detect_intent(content)

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
        f"- The user has an 8-hour quota of {GLOBAL_MESSAGE_LIMIT} messages total across Brainy.\n"
        f"- {quota_status['used']} messages used so far in this window, {quota_status['remaining']} remaining.\n"
        f"- The window resets at {quota_status['reset_at']}.\n"
        f"- The last 15 messages of a session are kept as context."
    )

    user_profile = study_bot.get_user_data(user_id)

    if intent == "joke":
        system_prompt = study_bot.JOKE_SYSTEM_PROMPT
        max_tok = 150
        messages_context = [{"role": "user", "content": "Tell one genuinely funny joke — preferably a science, programming, or Hinglish wordplay joke."}]
    elif intent == "fact":
        system_prompt = study_bot.FACT_SYSTEM_PROMPT
        max_tok = 200
        categories = ["science", "space", "human body", "history", "technology and AI", "mathematics", "psychology"]
        category = random.choice(categories)
        messages_context = [{"role": "user", "content": f"Give one mind-blowing lesser-known fact about {category}."}]
    elif intent == "tip":
        system_prompt = study_bot.TIP_SYSTEM_PROMPT
        max_tok = 250
        messages_context = [{"role": "user", "content": "Give one powerful productivity tip. Make it practical and actionable."}]
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
        messages_context = [{"role": "user", "content": prompt}]
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
                f"NEVER use **asterisks** markdown. Use emojis and → for formatting."
            )
            messages_context = [{"role": "user", "content": ai_prompt}]
            system_prompt = study_bot.SEARCH_SYSTEM_PROMPT
            max_tok = 600
        except Exception as e:
            print(f"Web search failed: {e}")
    elif intent == "brainy":
        system_prompt = study_bot.BRAINY_SYSTEM_PROMPT
        max_tok = 1000
    elif study_bot.is_offtopic_chat(content):
        system_prompt = study_bot.BANTER_SYSTEM_PROMPT or study_bot.SYSTEM_PROMPT

    # Inject learning contexts
    learn_ctx = study_bot.get_learning_context(5)
    liked_ctx = study_bot.get_liked_context(user_id, 5)
    extra = "\n\n".join(c for c in (learn_ctx, liked_ctx) if c)
    if extra:
        system_prompt = system_prompt + "\n\n" + extra

    try:
        response_text = study_bot.ai_call(messages_context, system_prompt, max_tok)
        response_text = study_bot.clean_response(response_text)
    except Exception as e:
        print(f"AI Call failed in Web App: {e}")
        response_text = f"❌ Error communicating with AI: {str(e)[:100]}"

    # Save assistant reply + auto-title the chat on its first exchange
    sb_insert_message(session_id, "assistant", response_text)

    title_updated = None
    if sess.get("title") in ("New Chat", "New Study Session", "", None):
        words = content.split()[:5]
        new_title = " ".join(words) + ("..." if len(content.split()) > 5 else "")
        sb_rename_session(session_id, user_id, new_title)
        title_updated = new_title

    # ── Sync to the Telegram bot's own memory/personalization store ──
    try:
        study_bot.load_user_into_memory(user_id, first_name, username)
        if user_id in study_bot.user_conversations:
            study_bot.user_conversations[user_id].append({"role": "user", "content": content})
            study_bot.user_conversations[user_id].append({"role": "assistant", "content": response_text})
            study_bot.trim_history(user_id)
            study_bot.save_user_memory_async(user_id)
    except Exception as se:
        print(f"Sync to Supabase memory failed: {se}")

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
        "message_limit": GLOBAL_MESSAGE_LIMIT
    })


# ── PROFILE & STATS APIS ──

@app.route("/api/user/profile", methods=["GET"])
@login_required
def get_user_profile():
    user_id = session["user_id"]
    study_bot.load_user_into_memory(user_id, session["first_name"], session["username"])
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
    study_bot.load_user_into_memory(user_id, session["first_name"], session["username"])
    profile = study_bot.get_user_data(user_id)
    liked_notes = profile.get("liked_notes") or []

    learn_history = study_bot.get_learning_context(10) or "No custom learning patterns registered yet."

    return jsonify({
        "liked_notes": liked_notes,
        "learn_context": learn_history
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
