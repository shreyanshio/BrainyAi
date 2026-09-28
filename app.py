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
from flask import Flask, request, jsonify, session, send_from_directory
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
    CORS(app, supports_credentials=True)

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

SUPABASE_URL = study_bot.SUPABASE_URL
SUPABASE_KEY = study_bot.SUPABASE_KEY
MESSAGE_LIMIT = 50

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
# { session_id: { "status": "pending"|"authenticated", "user": { ... } } }
auth_sessions = {}
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
            return r.json()
    except Exception as e:
        logger.warning("Supabase list_sessions error: %s", e)

    return MEM_SESSIONS.get(user_id, [])


def sb_create_session(user_id: int, title: str, session_id: str | None = None) -> dict:
    if not session_id:
        session_id = str(uuid.uuid4())
    payload = {"id": session_id, "user_id": user_id, "title": title}

    # Save in memory cache
    sess_obj = {"id": session_id, "user_id": user_id, "title": title, "created_at": datetime.now(timezone.utc).isoformat()}
    if user_id not in MEM_SESSIONS:
        MEM_SESSIONS[user_id] = []
    # Avoid duplicate in mem
    if not any(s["id"] == session_id for s in MEM_SESSIONS[user_id]):
        MEM_SESSIONS[user_id].insert(0, sess_obj)

    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/chat_sessions",
            headers=_sb_headers("return=representation"), json=payload, timeout=8
        )
        if r.status_code in (200, 201):
            return r.json()[0]
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
                return rows[0]
    except Exception as e:
        logger.warning("Supabase get_session error: %s", e)

    # Check memory cache
    user_sessions = MEM_SESSIONS.get(user_id, [])
    for s in user_sessions:
        if s["id"] == session_id:
            return s

    # Auto-create if not found so chat NEVER breaks
    return sb_create_session(user_id, "New Study Session", session_id=session_id)


def sb_rename_session(session_id: str, user_id: int, title: str) -> None:
    for s in MEM_SESSIONS.get(user_id, []):
        if s["id"] == session_id:
            s["title"] = title
    try:
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/chat_sessions?id=eq.{session_id}&user_id=eq.{user_id}",
            headers=_sb_headers(), json={"title": title}, timeout=8
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
            return r.json()
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
            return list(reversed(r.json()))
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
        payload = {"session_id": session_id, "role": role, "content": content}
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


# Serve the single merged index.html (HTML + CSS + JS all in one file).
# Lives right next to app.py — no templates/ subfolder needed.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


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
        auth_sessions.pop(session_id, None)
        return jsonify({"status": "authenticated", "user": user})

    return jsonify({"status": "pending"})


@app.route("/api/auth/verify", methods=["GET"])
def auth_verify():
    session_id = request.args.get("session_id")
    user_id = request.args.get("user_id")
    first_name = request.args.get("first_name", "")
    username = request.args.get("username", "")

    if not session_id or not user_id:
        return "❌ Missing session_id or user_id", 400

    if session_id in auth_sessions:
        auth_sessions[session_id] = {
            "status": "authenticated",
            "user": {"id": int(user_id), "first_name": first_name, "username": username}
        }
        return """
        <html>
            <head>
                <title>Login Successful</title>
                <style>
                    body {
                        background-color: #0d1117; color: #c9d1d9;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                        display: flex; flex-direction: column; align-items: center; justify-content: center;
                        height: 100vh; margin: 0;
                    }
                    .card {
                        background: rgba(22, 27, 34, 0.8); border: 1px solid #30363d; border-radius: 12px;
                        padding: 30px; text-align: center; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
                        backdrop-filter: blur(4px);
                    }
                    h1 { color: #58a6ff; font-size: 24px; margin-bottom: 10px; }
                    p { font-size: 16px; margin-bottom: 20px; }
                    .success-icon { font-size: 48px; margin-bottom: 15px; }
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="success-icon">🔓</div>
                    <h1>Login Authorized</h1>
                    <p>Verification successful! You can now close this window and return to your chat page.</p>
                </div>
            </body>
        </html>
        """
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
            "username": session.get("username", "")
        }
    })


@app.route("/api/auth/google", methods=["POST"])
def auth_google():
    """Handle Google Identity Services login credential token.

    Requires GOOGLE_CLIENT_ID to be configured and the token's signature to
    verify successfully — there is no unverified fallback. Accepting a
    token whose signature wasn't checked would let anyone log in as any
    email address just by crafting a JWT with that email in it.
    """
    data = request.json or {}
    token = data.get("credential")
    if not token:
        return jsonify({"error": "Missing Google credential token"}), 400

    google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    if not google_client_id:
        logger.error("GOOGLE_CLIENT_ID is not set — refusing Google login.")
        return jsonify({"error": "Google login is not configured on this server."}), 503

    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        id_info = id_token.verify_oauth2_token(
            token, google_requests.Request(), google_client_id
        )
    except Exception as e:
        logger.warning("Google token verification failed: %s", e)
        return jsonify({"error": "Invalid or expired Google token."}), 401

    if not id_info.get("email_verified", False):
        return jsonify({"error": "Google account email is not verified."}), 401

    email = id_info.get("email", "")
    name = id_info.get("name") or (email.split("@")[0] if email else "Google Student")
    google_sub = id_info.get("sub") or email or name

    # Deterministic integer user_id
    user_id = int(hashlib.md5(f"google_{google_sub}".encode()).hexdigest(), 16) % (10**9)
    username = email.split("@")[0] if email else name.lower().replace(" ", "_")

    session["user_id"] = user_id
    session["first_name"] = name
    session["username"] = username
    session["email"] = email.strip().lower()  # verified by Google — safe to gate admin access on

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
            "picture": id_info.get("picture", "")
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
    user_msg_count = sum(1 for m in messages if m["role"] == "user")

    return jsonify({
        "messages": messages,
        "user_message_count": user_msg_count,
        "message_limit": MESSAGE_LIMIT
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
    content = data.get("content", "").strip()

    if not session_id or not content:
        return jsonify({"error": "Missing session_id or content"}), 400

    # Sanitize user input
    content = sanitize_input(content)

    # Blacklist check
    if is_blacklisted(content):
        log_security_event("blacklist_blocked", ip, user_id, content[:100])
        return jsonify({"error": "Invalid input detected."}), 403

    # Per-user rate limit: 10 messages per minute
    if not check_rate_limit("user_{}".format(user_id), limit=10, window=60):
        log_security_event("user_rate_limit", ip, user_id, "")
        return jsonify({"error": "Message limit reached. Please wait a moment."}), 429

    sess = sb_get_session(session_id, user_id)
    if not sess:
        return jsonify({"error": "Session not found"}), 404

    # Enforce the 50-message-per-session limit BEFORE spending an AI call
    current_count = sb_count_user_messages(session_id)
    if current_count >= MESSAGE_LIMIT:
        return jsonify({
            "error": "limit_reached",
            "message": "This chat hit its 50-message limit. Start a new chat to keep going.",
            "user_message_count": current_count,
            "message_limit": MESSAGE_LIMIT
        }), 403

    # Save user message
    sb_insert_message(session_id, "user", content)
    new_count = current_count + 1

    # Fetch last 15 messages (now including the one we just saved) for context
    messages_context = [{"role": m["role"], "content": m["content"]} for m in sb_get_recent_messages(session_id, 15)]

    # Run intent detection
    intent, payload = study_bot.detect_intent(content)

    system_prompt = study_bot.SYSTEM_PROMPT
    max_tok = None

    # ── Zero Sugarcoating toggle ──────────────────────────
    tone = data.get("tone", "standard")
    if tone == "blunt":
        system_prompt = (
            system_prompt
            + "\n\nTONE OVERRIDE — ZERO SUGARCOATING MODE:\n"
            "Be blunt, direct, and no-nonsense. Skip encouragement fluff, "
            "skip 'Great question!', skip motivational padding. "
            "Give the answer straight, correct mistakes directly, "
            "and be brutally honest about what the student is getting wrong. "
            "Still be helpful — just cut the sugar."
        )

    # Ground the model in real facts about itself so it doesn't guess/hallucinate
    # when the user asks about limits or features.
    remaining = MESSAGE_LIMIT - new_count
    system_prompt = (
        system_prompt
        + f"\n\nFACTS ABOUT THIS CHAT (answer accurately if asked, don't guess):\n"
        f"- This session has a hard limit of {MESSAGE_LIMIT} messages total.\n"
        f"- {new_count} messages used so far, {remaining} remaining.\n"
        f"- Once the limit is hit, the user must start a new chat to continue.\n"
        f"- Only the last 15 messages of a session are kept as context."
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

    return jsonify({
        "role": "assistant",
        "content": format_for_web(response_text),
        "new_title": title_updated,
        "user_message_count": new_count,
        "message_limit": MESSAGE_LIMIT
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
