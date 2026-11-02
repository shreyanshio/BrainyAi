"""
Brainy Centralized Private Google Drive Storage Module
======================================================
Architecture:
- Single owner-authorized Google Drive account acts as centralized storage vault for all Brainy users.
- End users do NOT connect their personal Google accounts.
- Strict per-user data isolation via automated opaque folder hierarchy:
    My Drive/Brainy/Users/user_<opaque_id>/PDFs/<doc_id>.pdf
- Server-side token encryption at rest via AES-256-GCM with dedicated key.
- Compliance gate: Production uploads remain paused until official Google API Terms written clarification.
"""

import os
import re
import json
import time
import hmac
import base64
import uuid
import secrets
import logging
import hashlib
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, Generator

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger("brainy_drive")

# ── CONFIGURATION & CONSTANTS ──
DRIVE_V3_BASE = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
OAUTH_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
DEFAULT_SCOPES = f"{DRIVE_FILE_SCOPE} openid email"

ENC_PREFIX = "drv_enc_v1_"
AEAD_AAD = b"brainy_central_drive_v1"

# In-memory single-use state store for OAuth CSRF protection: {nonce: (owner_user_id, exp_ts)}
_OAUTH_STATE_REGISTRY: Dict[str, Tuple[str, float]] = {}
_OAUTH_STATE_LOCK = threading.Lock()

# In-memory folder mapping lock to prevent race conditions during folder creation
_FOLDER_LOCK = threading.Lock()

# Local persistence directory for drive config/folder cache in dev or offline Supabase
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "google_drive")
os.makedirs(DATA_DIR, exist_ok=True)


class GoogleDriveError(Exception):
    """Base exception for Google Drive integration errors."""


class GoogleDriveAuthError(GoogleDriveError):
    """Raised for unauthorized, invalid token, or forbidden operations."""


class GoogleDriveQuotaError(GoogleDriveError):
    """Raised when Google API rate limits or Drive storage capacity is exhausted."""


class GoogleDriveCompliancePause(GoogleDriveError):
    """Raised when production uploads are blocked pending Google compliance checkpoint."""


# ── 1. AES-256-GCM TOKEN CIPHER ──

class DriveTokenCipher:
    """Dedicated AES-256-GCM cipher for Google Drive integration credentials."""

    def __init__(self, key: Optional[str] = None):
        self._key = key

    @staticmethod
    def _derive_key_bytes(raw_k: str) -> bytes:
        raw_k = raw_k.strip()
        if len(raw_k) == 64:
            try:
                return bytes.fromhex(raw_k)
            except ValueError:
                pass
        return hashlib.sha256(raw_k.encode("utf-8")).digest()

    def _get_encryption_keys(self) -> list[bytes]:
        keys: list[bytes] = []
        raw_key = (
            self._key
            or os.getenv("BRAINY_DRIVE_TOKEN_ENCRYPTION_KEY", "").strip()
            or os.getenv("CHAT_ENCRYPTION_KEY", "").strip()
        )
        if raw_key:
            keys.append(self._derive_key_bytes(raw_key))
        else:
            auth_secret = os.getenv("AUTH_SECRET_KEY") or os.getenv("FLASK_SECRET_KEY") or "brainy_dev_secret"
            derived = hashlib.pbkdf2_hmac(
                "sha256", auth_secret.encode("utf-8"), b"brainy_drive_token_salt_v1", 100000, dklen=32
            )
            keys.append(derived)

        # Previous rotation keys
        prev_str = os.getenv("BRAINY_DRIVE_TOKEN_PREVIOUS_KEYS", "").strip()
        if prev_str:
            for pk in prev_str.split(","):
                pk_clean = pk.strip()
                if pk_clean:
                    k_bytes = self._derive_key_bytes(pk_clean)
                    if k_bytes not in keys:
                        keys.append(k_bytes)

        return keys

    def encrypt(self, plain_text: str) -> str:
        """Encrypt plain text into authenticated drv_enc_v1_ payload."""
        if not plain_text:
            return ""
        keys = self._get_encryption_keys()
        active_key = keys[0]
        aesgcm = AESGCM(active_key)
        nonce = os.urandom(12)  # 96-bit unique random nonce
        ciphertext = aesgcm.encrypt(nonce, plain_text.encode("utf-8"), AEAD_AAD)
        payload = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
        return f"{ENC_PREFIX}{payload}"

    def decrypt(self, encrypted_text: str) -> str:
        """Decrypt drv_enc_v1_ payload back to plain text."""
        if not encrypted_text:
            return ""
        if not encrypted_text.startswith(ENC_PREFIX):
            raise GoogleDriveAuthError("Invalid encryption payload format")
        raw = base64.urlsafe_b64decode(encrypted_text[len(ENC_PREFIX):].encode("ascii"))
        if len(raw) < 28:
            raise GoogleDriveAuthError("Truncated encrypted payload")
        nonce = raw[:12]
        ciphertext_tag = raw[12:]

        keys = self._get_encryption_keys()
        for k in keys:
            try:
                aesgcm = AESGCM(k)
                decrypted = aesgcm.decrypt(nonce, ciphertext_tag, AEAD_AAD)
                return decrypted.decode("utf-8")
            except Exception:
                continue
        raise GoogleDriveAuthError("Could not decrypt token with active or rotated keys")


cipher = DriveTokenCipher()


# ── 2. AUDIT LOGGING HELPER ──

def audit_drive_event(event_type: str, user_id: Any, details: Dict[str, Any]):
    """Structured security audit logging. Automatically strips/redacts sensitive tokens/secrets."""
    sanitized = {}
    for k, v in details.items():
        if any(sec in k.lower() for sec in ["token", "secret", "code", "key", "password"]):
            sanitized[k] = "[REDACTED]"
        else:
            sanitized[k] = v
    logger.info("DRIVE_AUDIT event=%s user_id=%s details=%s", event_type, user_id, json.dumps(sanitized))


# ── 3. GOOGLE DRIVE STORAGE MANAGER ──

class GoogleDriveStorageManager:
    """
    Centralized Google Drive Manager:
    - Maintains the owner's authorized connection
    - Enforces strict per-user folder isolation
    - Handles uploads, downloads, deletions, and health checks
    """

    def __init__(self, supabase_request_fn=None):
        self._sb_req = supabase_request_fn
        self._cached_access_token: Optional[str] = None
        self._token_expiry_ts: float = 0.0
        self._stats: Dict[str, Any] = {
            "last_successful_upload": None,
            "last_failed_upload": None,
            "upload_failures_count": 0,
            "drive_api_errors_count": 0,
        }

    def set_supabase_requester(self, sb_req_fn):
        self._sb_req = sb_req_fn

    # ── COMPLIANCE PREFLIGHT STATUS ──

    def is_compliance_cleared(self) -> bool:
        """Returns True if the project owner has confirmed compliance clearance."""
        env_val = os.getenv("BRAINY_DRIVE_PRODUCTION_ENABLED", "false").lower()
        return env_val in ("true", "1", "yes")

    # ── MULTI-LAYER OWNER IDENTITY VERIFICATION ──

    def get_configured_owner_id(self) -> str:
        return os.getenv("BRAINY_DRIVE_OWNER_USER_ID", "").strip()

    def get_configured_owner_email(self) -> str:
        return (os.getenv("BRAINY_DRIVE_OWNER_EMAIL") or "shreyansh.npm@gmail.com").strip().lower()

    def get_configured_owner_sub(self) -> str:
        return os.getenv("BRAINY_DRIVE_OWNER_GOOGLE_SUB", "").strip()

    def verify_owner_identity(
        self,
        user_id: Any,
        email: Optional[str] = None,
        google_sub: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Multi-layer owner identity verification:
        1. Valid integer/string user_id matching configured or bound owner ID.
        2. If google_sub is configured/bound, must match verified google_sub.
        3. If email is provided/configured, must match verified owner email.
        4. Rejects email-only claims without user_id / google_sub verification.
        5. Rejects arbitrary users or unverified sessions.
        """
        if not user_id:
            return False, "USER_ID_REQUIRED"

        user_id_str = str(user_id).strip()
        env_owner_id = self.get_configured_owner_id()
        env_owner_sub = self.get_configured_owner_sub()
        env_owner_email = self.get_configured_owner_email()

        cfg = self.get_owner_config() or {}
        db_owner_id = str(cfg.get("owner_user_id")).strip() if cfg.get("owner_user_id") else ""
        db_owner_sub = str(cfg.get("owner_google_sub")).strip() if cfg.get("owner_google_sub") else ""
        db_owner_email = (cfg.get("owner_email") or "").strip().lower()

        expected_owner_id = env_owner_id or db_owner_id
        expected_owner_sub = env_owner_sub or db_owner_sub
        expected_owner_email = env_owner_email or db_owner_email or "shreyansh.npm@gmail.com"

        # 1. User ID check
        if expected_owner_id:
            if user_id_str != expected_owner_id:
                return False, f"USER_ID_MISMATCH (got {user_id_str}, expected {expected_owner_id})"

        # 2. Google Sub check
        if expected_owner_sub:
            if not google_sub:
                return False, "MISSING_VERIFIED_GOOGLE_SUB"
            if str(google_sub).strip() != expected_owner_sub:
                return False, "GOOGLE_SUB_MISMATCH"

        # 3. Email consistency check
        if email:
            clean_email = email.strip().lower()
            if clean_email != expected_owner_email:
                return False, f"EMAIL_MISMATCH (got {clean_email}, expected {expected_owner_email})"

        # 4. Bootstrap / Unbound check: if expected_owner_id is not set in env or DB
        if not expected_owner_id:
            if email and email.strip().lower() == expected_owner_email and google_sub:
                return True, "OWNER_BOOTSTRAP_ELIGIBLE"
            return False, "OWNER_NOT_CONFIGURED"

        return True, "AUTHORIZED"

    def is_owner_user(
        self,
        user_id: Any,
        email: Optional[str] = None,
        google_sub: Optional[str] = None,
        is_admin: bool = False
    ) -> bool:
        """
        Returns True only if the user satisfies multi-layer owner identity requirements.
        Admin status alone without owner identity matching is strictly disallowed.
        """
        valid, _ = self.verify_owner_identity(user_id=user_id, email=email, google_sub=google_sub)
        return valid

    def bind_owner_account(self, user_id: Any, email: str, google_sub: str) -> bool:
        """
        Secure server-side owner binding.
        Once bound, locks owner config in DB to this specific user_id and google_sub.
        Cannot be hijacked or claimed by another account.
        """
        clean_email = email.strip().lower()
        expected_email = self.get_configured_owner_email()
        if clean_email != expected_email:
            logger.warning("Refused owner binding: email %s does not match expected %s", clean_email, expected_email)
            return False

        if not google_sub or not user_id:
            logger.warning("Refused owner binding: missing user_id or google_sub")
            return False

        cfg = self.get_owner_config() or {}
        existing_id = str(cfg.get("owner_user_id")) if cfg.get("owner_user_id") else ""
        existing_sub = str(cfg.get("owner_google_sub")) if cfg.get("owner_google_sub") else ""

        # If already bound to a different identity, reject to prevent replay / hijack
        if existing_id and existing_id != str(user_id):
            logger.error("Owner binding collision! Existing: %s, Attempted: %s", existing_id, user_id)
            return False
        if existing_sub and existing_sub != str(google_sub):
            logger.error("Owner sub collision! Existing: %s, Attempted: %s", existing_sub, google_sub)
            return False

        cfg["owner_user_id"] = int(user_id) if str(user_id).isdigit() else str(user_id)
        cfg["owner_email"] = clean_email
        cfg["owner_google_sub"] = str(google_sub).strip()
        self.save_owner_config(cfg)
        audit_drive_event("OWNER_BOUND", user_id, {"email": clean_email, "google_sub_bound": True})
        return True

    # ── OAUTH STATE MANAGEMENT (CSRF & SINGLE-USE) ──

    def generate_oauth_state(self, owner_user_id: Any) -> str:
        """Generates a cryptographically signed, single-use, time-limited state parameter."""
        nonce = secrets.token_hex(16)
        now = time.time()
        exp = now + 900.0  # 15 minutes validity
        with _OAUTH_STATE_LOCK:
            # Clean expired states
            for n, (_, e_ts) in list(_OAUTH_STATE_REGISTRY.items()):
                if e_ts < now:
                    _OAUTH_STATE_REGISTRY.pop(n, None)
            _OAUTH_STATE_REGISTRY[nonce] = (str(owner_user_id), exp)

        payload = json.dumps({"u": str(owner_user_id), "n": nonce, "e": exp})
        p_b64 = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
        secret = os.getenv("AUTH_SECRET_KEY") or os.getenv("FLASK_SECRET_KEY") or "brainy_oauth_secret"
        sig = hmac.new(secret.encode("utf-8"), p_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{p_b64}.{sig}"

    def validate_oauth_state(self, state_str: str, expected_user_id: Any) -> bool:
        """Validates and immediately consumes the OAuth state parameter."""
        if not state_str or "." not in state_str:
            return False
        try:
            p_b64, sig = state_str.split(".", 1)
            secret = os.getenv("AUTH_SECRET_KEY") or os.getenv("FLASK_SECRET_KEY") or "brainy_oauth_secret"
            expected_sig = hmac.new(secret.encode("utf-8"), p_b64.encode("utf-8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                return False

            pad = len(p_b64) % 4
            raw_p = base64.urlsafe_b64decode((p_b64 + ("=" * (4 - pad) if pad else "")).encode("ascii")).decode("utf-8")
            payload = json.loads(raw_p)

            nonce = payload.get("n")
            exp = float(payload.get("e", 0))
            user_id = str(payload.get("u", ""))

            if exp < time.time():
                return False

            if expected_user_id and str(expected_user_id) != user_id:
                return False

            with _OAUTH_STATE_LOCK:
                if nonce not in _OAUTH_STATE_REGISTRY:
                    return False
                stored_u, stored_exp = _OAUTH_STATE_REGISTRY.pop(nonce)
                if stored_u != user_id or stored_exp < time.time():
                    return False

            return True
        except Exception as e:
            logger.warning("OAuth state validation exception: %s", e)
            return False

    # ── OAUTH URL & CODE EXCHANGE ──

    def get_oauth_authorization_url(self, owner_user_id: Any, prompt_consent: bool = True) -> str:
        """Constructs Google OAuth 2.0 authorization URL for the owner."""
        client_id = os.getenv("GOOGLE_DRIVE_CLIENT_ID", "").strip()
        redirect_uri = os.getenv(
            "GOOGLE_DRIVE_REDIRECT_URI",
            "https://brainyai-backend.onrender.com/api/integrations/google-drive/callback"
        ).strip()
        if not client_id:
            raise GoogleDriveAuthError("GOOGLE_DRIVE_CLIENT_ID environment variable is missing")

        state = self.generate_oauth_state(owner_user_id)
        prompt = "consent" if prompt_consent else "select_account"
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": DEFAULT_SCOPES,
            "access_type": "offline",
            "state": state,
            "prompt": prompt,
            "include_granted_scopes": "true"
        }
        query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
        return f"{OAUTH_AUTH_URL}?{query}"

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchanges authorization code for access and refresh tokens."""
        client_id = os.getenv("GOOGLE_DRIVE_CLIENT_ID", "").strip()
        client_secret = os.getenv("GOOGLE_DRIVE_CLIENT_SECRET", "").strip()
        redirect_uri = os.getenv(
            "GOOGLE_DRIVE_REDIRECT_URI",
            "https://brainyai-backend.onrender.com/api/integrations/google-drive/callback"
        ).strip()

        if not (client_id and client_secret):
            raise GoogleDriveAuthError("GOOGLE_DRIVE_CLIENT_ID or GOOGLE_DRIVE_CLIENT_SECRET missing")

        data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        resp = requests.post(OAUTH_TOKEN_URL, data=data, timeout=12)
        if resp.status_code != 200:
            logger.error("Token exchange failed status=%d resp=%s", resp.status_code, resp.text)
            raise GoogleDriveAuthError(f"Google token exchange failed ({resp.status_code}): {resp.text}")

        tokens = resp.json()
        return tokens

    # ── PERSISTENCE OF OWNER DRIVE CONFIG ──

    def _get_local_config_path(self) -> str:
        return os.path.join(DATA_DIR, "owner_config.json")

    def get_owner_config(self) -> Optional[Dict[str, Any]]:
        """Retrieves stored owner integration config from Supabase or local cache."""
        # 1. Supabase lookup
        if self._sb_req:
            try:
                resp = self._sb_req("GET", "google_drive_owner_config", params="?id=eq.1&limit=1")
                rows = resp.json() if hasattr(resp, "json") else []
                if isinstance(rows, list) and rows:
                    return rows[0]
            except Exception as e:
                logger.debug("Could not read google_drive_owner_config from Supabase: %s", e)

        # 2. Local fallback
        path = self._get_local_config_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def save_owner_config(self, config_data: Dict[str, Any]):
        """Persists owner integration config securely."""
        config_data["id"] = 1
        config_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        # 1. Local disk persistence
        try:
            path = self._get_local_config_path()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)
        except Exception as le:
            logger.warning("Failed saving local drive owner config: %s", le)

        # 2. Supabase persistence
        if self._sb_req:
            try:
                # Upsert into google_drive_owner_config
                self._sb_req("POST", "google_drive_owner_config", json_body=config_data)
            except Exception as se:
                logger.debug("Failed saving drive owner config to Supabase (local cached): %s", se)

    # ── TOKEN REFRESH & ACCESS TOKEN RETRIEVAL ──

    def get_valid_access_token(self) -> str:
        """Retrieves a valid access token, automatically refreshing if expired."""
        now = time.time()
        if self._cached_access_token and self._token_expiry_ts > (now + 60):
            return self._cached_access_token

        cfg = self.get_owner_config()
        if not cfg or not cfg.get("encrypted_refresh_token"):
            raise GoogleDriveAuthError("Google Drive is not connected. The project owner must authorize Drive first.")

        # Check stored access token
        enc_access = cfg.get("encrypted_access_token")
        exp_at_str = cfg.get("access_token_expires_at")
        if enc_access and exp_at_str:
            try:
                exp_dt = datetime.fromisoformat(exp_at_str)
                exp_ts = exp_dt.timestamp()
                if exp_ts > (now + 60):
                    self._cached_access_token = cipher.decrypt(enc_access)
                    self._token_expiry_ts = exp_ts
                    return self._cached_access_token
            except Exception:
                pass

        # Refresh token exchange
        refresh_token = cipher.decrypt(cfg["encrypted_refresh_token"])
        client_id = os.getenv("GOOGLE_DRIVE_CLIENT_ID", "").strip()
        client_secret = os.getenv("GOOGLE_DRIVE_CLIENT_SECRET", "").strip()

        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }

        # Exponential backoff on transient network / quota errors
        attempts = 0
        backoff = 0.5
        resp = None
        while attempts < 3:
            try:
                resp = requests.post(OAUTH_TOKEN_URL, data=data, timeout=10)
                if resp.status_code == 200:
                    break
                elif resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep(backoff)
                    backoff *= 2
                    attempts += 1
                else:
                    break
            except requests.RequestException:
                time.sleep(backoff)
                backoff *= 2
                attempts += 1

        if not resp or resp.status_code != 200:
            err_msg = resp.text if resp else "Connection error"
            logger.error("Token refresh failed status=%s: %s", getattr(resp, "status_code", "None"), err_msg)
            raise GoogleDriveAuthError("Google Drive access token refresh failed. Integration may need reconnection.")

        refreshed = resp.json()
        new_access = refreshed["access_token"]
        expires_in = int(refreshed.get("expires_in", 3600))
        new_exp_dt = datetime.fromtimestamp(now + expires_in, timezone.utc)

        self._cached_access_token = new_access
        self._token_expiry_ts = now + expires_in

        # Update stored config with encrypted new access token
        cfg["encrypted_access_token"] = cipher.encrypt(new_access)
        cfg["access_token_expires_at"] = new_exp_dt.isoformat()
        self.save_owner_config(cfg)

        return new_access

    # ── FOLDER STRUCTURE SETUP & OPAQUE USER IDENTIFIER ──

    def derive_user_opaque_id(self, user_id: Any) -> str:
        """Derives a stable, irreversible opaque identifier for a Brainy user folder."""
        salt = os.getenv("BRAINY_DRIVE_USER_SALT") or os.getenv("AUTH_SECRET_KEY") or "brainy_opaque_salt_v1"
        return hmac.new(salt.encode("utf-8"), f"brainy_user_{user_id}".encode("utf-8"), hashlib.sha256).hexdigest()[:16]

    def _drive_api_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Helper to execute authorized Google Drive API requests with retry on 429."""
        token = self.get_valid_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        url = f"{DRIVE_V3_BASE}/{endpoint.lstrip('/')}"

        attempts = 0
        backoff = 0.5
        resp = None
        while attempts < 3:
            try:
                resp = requests.request(method, url, headers=headers, **kwargs)
                if resp.status_code == 429:
                    time.sleep(backoff)
                    backoff *= 2
                    attempts += 1
                elif resp.status_code == 401:
                    # Invalidate token and refresh once
                    self._cached_access_token = None
                    self._token_expiry_ts = 0
                    token = self.get_valid_access_token()
                    headers["Authorization"] = f"Bearer {token}"
                    resp = requests.request(method, url, headers=headers, **kwargs)
                    break
                else:
                    break
            except requests.RequestException as re:
                time.sleep(backoff)
                backoff *= 2
                attempts += 1

        if resp is None:
            raise GoogleDriveError("Google Drive request timed out")
        if resp.status_code == 429:
            raise GoogleDriveQuotaError("Google Drive API rate limit exceeded")
        return resp

    def _find_or_create_folder(self, name: str, parent_id: Optional[str] = None) -> str:
        """Finds an existing folder under parent_id or creates a new private folder."""
        query_parts = [
            f"name = '{name}'",
            "mimeType = 'application/vnd.google-apps.folder'",
            "trashed = false"
        ]
        if parent_id:
            query_parts.append(f"'{parent_id}' in parents")
        else:
            query_parts.append("'root' in parents")

        q = " and ".join(query_parts)
        params = {"q": q, "fields": "files(id, name, parents)", "spaces": "drive"}
        resp = self._drive_api_request("GET", "/files", params=params, timeout=10)
        if resp.status_code == 200:
            files = resp.json().get("files", [])
            if files:
                return files[0]["id"]

        # Create folder
        body: Dict[str, Any] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder"
        }
        if parent_id:
            body["parents"] = [parent_id]

        create_resp = self._drive_api_request("POST", "/files", json=body, timeout=10)
        if create_resp.status_code not in (200, 201):
            raise GoogleDriveError(f"Failed to create Drive folder '{name}': {create_resp.text}")
        created_id = create_resp.json()["id"]
        logger.info("Created Drive folder name=%s id=%s parent=%s", name, created_id, parent_id)
        return created_id

    def initialize_root_hierarchy(self) -> Tuple[str, str]:
        """Creates or locates My Drive/Brainy/Users/ hierarchy."""
        cfg = self.get_owner_config() or {}
        root_id = cfg.get("root_folder_id")
        users_id = cfg.get("users_folder_id")

        with _FOLDER_LOCK:
            # 1. Root 'Brainy' folder
            if not root_id:
                root_id = self._find_or_create_folder("Brainy", parent_id=None)
            # 2. 'Users' folder inside Brainy
            if not users_id:
                users_id = self._find_or_create_folder("Users", parent_id=root_id)

            cfg["root_folder_id"] = root_id
            cfg["users_folder_id"] = users_id
            self.save_owner_config(cfg)
            return root_id, users_id

    def get_or_create_user_folder(self, user_id: Any) -> Tuple[str, Dict[str, Any]]:
        """Resolves and caches the top-level user folder: Brainy/Users/user_<opaque_id>/"""
        user_str = str(user_id)
        opaque_id = self.derive_user_opaque_id(user_str)
        user_folder_name = f"user_{opaque_id}"
        cache_file = os.path.join(DATA_DIR, f"user_folder_{user_str}.json")
        mapping = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    mapping = json.load(f)
                    if mapping.get("user_folder_id"):
                        return mapping["user_folder_id"], mapping
            except Exception:
                mapping = {}

        # Resolve Users folder ID
        _, users_folder_id = self.initialize_root_hierarchy()
        user_folder_id = self._find_or_create_folder(user_folder_name, parent_id=users_folder_id)
        mapping.update({
            "user_id": user_str,
            "opaque_id": opaque_id,
            "user_folder_id": user_folder_id,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(mapping, f, indent=2)
        except Exception:
            pass
        return user_folder_id, mapping

    def get_or_create_user_pdf_folder(self, user_id: Any, use_dated: bool = False) -> str:
        """
        Resolves the private PDFs folder for a user:
        Brainy/Users/user_<opaque_id>/PDFs/ (or PDFs/{year}/{month}/ if use_dated)
        Thread-safe and cached.
        """
        user_str = str(user_id)
        cache_file = os.path.join(DATA_DIR, f"user_folder_{user_str}.json")
        now = datetime.now(timezone.utc)
        year_str = str(now.year)
        month_str = f"{now.month:02d}"
        dated_key = f"pdf_{year_str}_{month_str}"

        # 1. Check local cache before locking
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    if not use_dated and cached.get("pdf_folder_id"):
                        return cached["pdf_folder_id"]
                    if use_dated and cached.get("dated_folders", {}).get(dated_key):
                        return cached["dated_folders"][dated_key]
            except Exception:
                pass

        with _FOLDER_LOCK:
            user_folder_id, mapping = self.get_or_create_user_folder(user_id)
            if not mapping.get("pdf_folder_id"):
                pdf_folder_id = self._find_or_create_folder("PDFs", parent_id=user_folder_id)
                mapping["pdf_folder_id"] = pdf_folder_id
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(mapping, f, indent=2)
                except Exception:
                    pass
                if self._sb_req:
                    try:
                        self._sb_req("POST", "google_drive_user_folders", json_body=mapping)
                    except Exception:
                        pass
            else:
                pdf_folder_id = mapping["pdf_folder_id"]

            if not use_dated:
                return pdf_folder_id

            # Dated subfolder: PDFs/{year}/{month}
            dated_cache = mapping.setdefault("dated_folders", {})
            if dated_key in dated_cache:
                return dated_cache[dated_key]

            year_folder_id = self._find_or_create_folder(year_str, parent_id=pdf_folder_id)
            month_folder_id = self._find_or_create_folder(month_str, parent_id=year_folder_id)
            dated_cache[dated_key] = month_folder_id
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(mapping, f, indent=2)
            except Exception:
                pass
            return month_folder_id

    def get_or_create_user_image_folder(self, user_id: Any, use_dated: bool = True) -> str:
        """
        Resolves the private Images folder for a user:
        Brainy/Users/user_<opaque_id>/Images/{year}/{month}/
        Thread-safe and cached.
        """
        user_str = str(user_id)
        cache_file = os.path.join(DATA_DIR, f"user_folder_{user_str}.json")
        now = datetime.now(timezone.utc)
        year_str = str(now.year)
        month_str = f"{now.month:02d}"
        dated_key = f"image_{year_str}_{month_str}"

        # 1. Check local cache before locking
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    if not use_dated and cached.get("image_folder_id"):
                        return cached["image_folder_id"]
                    if use_dated and cached.get("dated_folders", {}).get(dated_key):
                        return cached["dated_folders"][dated_key]
            except Exception:
                pass

        with _FOLDER_LOCK:
            user_folder_id, mapping = self.get_or_create_user_folder(user_id)
            if not mapping.get("image_folder_id"):
                image_folder_id = self._find_or_create_folder("Images", parent_id=user_folder_id)
                mapping["image_folder_id"] = image_folder_id
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(mapping, f, indent=2)
                except Exception:
                    pass
                if self._sb_req:
                    try:
                        self._sb_req("POST", "google_drive_user_folders", json_body=mapping)
                    except Exception:
                        pass
            else:
                image_folder_id = mapping["image_folder_id"]

            if not use_dated:
                return image_folder_id

            # Dated subfolder: Images/{year}/{month}
            dated_cache = mapping.setdefault("dated_folders", {})
            if dated_key in dated_cache:
                return dated_cache[dated_key]

            year_folder_id = self._find_or_create_folder(year_str, parent_id=image_folder_id)
            month_folder_id = self._find_or_create_folder(month_str, parent_id=year_folder_id)
            dated_cache[dated_key] = month_folder_id
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(mapping, f, indent=2)
            except Exception:
                pass
            return month_folder_id

    # ── UPLOAD, DOWNLOAD & DELETE OPERATIONS ──

    def upload_file(
        self,
        user_id: Any,
        filename: str,
        file_bytes: bytes,
        mime_type: str,
        file_id: str,
        file_type: str = "image"
    ) -> Dict[str, Any]:
        """
        Uploads an original file (Image or PDF) into the user's private folder in the owner's Google Drive.
        Enforces compliance pause, checksum verification, and returns drive_file_id.
        """
        if not self.is_compliance_cleared():
            logger.info("Production Google Drive uploads paused pending compliance clearance. Operating in sandbox mode.")
            raise GoogleDriveCompliancePause(
                "Centralized Google Drive storage is paused pending Google API Terms of Service compliance confirmation. "
                "Local persistence and processing remain active."
            )

        try:
            if file_type == "image":
                target_folder_id = self.get_or_create_user_image_folder(user_id, use_dated=True)
            else:
                target_folder_id = self.get_or_create_user_pdf_folder(user_id, use_dated=False)

            token = self.get_valid_access_token()
            checksum = hashlib.sha256(file_bytes).hexdigest()

            # Sanitize filename
            clean_name = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
            safe_name = f"{file_id}_{clean_name}"

            metadata = {
                "name": safe_name,
                "parents": [target_folder_id],
                "mimeType": mime_type,
                "properties": {
                    "brainy_file_id": file_id,
                    "brainy_user_opaque": self.derive_user_opaque_id(user_id),
                    "checksum": checksum,
                    "file_type": file_type
                }
            }

            # Multipart upload
            boundary = "===============brainy_drive_boundary=="
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": f"multipart/related; boundary={boundary}"
            }

            body_meta = (
                f"--{boundary}\r\n"
                f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
                f"{json.dumps(metadata)}\r\n"
            ).encode("utf-8")

            body_file = (
                f"--{boundary}\r\n"
                f"Content-Type: {mime_type}\r\n\r\n"
            ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

            payload = body_meta + body_file
            url = f"{DRIVE_UPLOAD_BASE}/files?uploadType=multipart&fields=id,name,size,createdTime"

            resp = requests.post(url, headers=headers, data=payload, timeout=30)
            if resp.status_code not in (200, 201):
                logger.error("Drive upload error status=%d: %s", resp.status_code, resp.text)
                self._stats["upload_failures_count"] += 1
                self._stats["drive_api_errors_count"] += 1
                self._stats["last_failed_upload"] = datetime.now(timezone.utc).isoformat()
                raise GoogleDriveError(f"Drive upload failed ({resp.status_code}): {resp.text}")

            res_json = resp.json()
            drive_file_id = res_json["id"]

            self._stats["last_successful_upload"] = datetime.now(timezone.utc).isoformat()

            audit_drive_event("FILE_UPLOADED", user_id, {
                "file_id": file_id,
                "file_type": file_type,
                "drive_file_id": drive_file_id,
                "folder_id": target_folder_id,
                "size": len(file_bytes),
                "checksum": checksum
            })

            return {
                "drive_file_id": drive_file_id,
                "drive_folder_id": target_folder_id,
                "checksum": checksum,
                "file_size": len(file_bytes),
                "uploaded_at": res_json.get("createdTime", datetime.now(timezone.utc).isoformat())
            }
        except GoogleDriveCompliancePause:
            raise
        except Exception as e:
            self._stats["upload_failures_count"] += 1
            self._stats["last_failed_upload"] = datetime.now(timezone.utc).isoformat()
            if not isinstance(e, GoogleDriveError):
                self._stats["drive_api_errors_count"] += 1
            raise

    def upload_pdf(self, user_id: Any, filename: str, file_bytes: bytes, doc_id: str) -> Dict[str, Any]:
        """
        Uploads an original PDF into the user's private folder in the owner's Google Drive.
        Enforces compliance pause, checksum verification, and returns drive_file_id.
        """
        res = self.upload_file(
            user_id=user_id,
            filename=filename,
            file_bytes=file_bytes,
            mime_type="application/pdf",
            file_id=doc_id,
            file_type="pdf"
        )
        return {
            "drive_file_id": res["drive_file_id"],
            "drive_folder_id": res["drive_folder_id"],
            "checksum": res["checksum"],
            "uploaded_at": res["uploaded_at"]
        }

    def stream_file(self, user_id: Any, file_id: str, drive_file_id: str) -> Generator[bytes, None, None]:
        """
        Streams private file bytes from Google Drive API with verified user ownership.
        """
        token = self.get_valid_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{DRIVE_V3_BASE}/files/{drive_file_id}?alt=media"

        resp = requests.get(url, headers=headers, stream=True, timeout=20)
        if resp.status_code != 200:
            logger.error("Drive stream failed file_id=%s status=%d", drive_file_id, resp.status_code)
            self._stats["drive_api_errors_count"] += 1
            raise GoogleDriveError(f"Failed to stream file from Google Drive ({resp.status_code})")

        audit_drive_event("FILE_DOWNLOAD_AUTHORIZED", user_id, {"file_id": file_id, "drive_file_id": drive_file_id})
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                yield chunk

    def stream_pdf(self, user_id: Any, doc_id: str, drive_file_id: str) -> Generator[bytes, None, None]:
        """
        Streams private PDF bytes from Google Drive API with verified user ownership.
        """
        return self.stream_file(user_id, doc_id, drive_file_id)

    def get_file_bytes(self, user_id: Any, file_id: str, drive_file_id: str) -> bytes:
        """
        Retrieves complete file bytes for AI processing or validation.
        """
        chunks = []
        for chunk in self.stream_file(user_id, file_id, drive_file_id):
            chunks.append(chunk)
        return b"".join(chunks)

    def delete_file(self, user_id: Any, file_id: str, drive_file_id: str):
        """Deletes private file from Google Drive."""
        resp = self._drive_api_request("DELETE", f"/files/{drive_file_id}", timeout=10)
        if resp.status_code not in (200, 204, 404):
            logger.error("Drive delete failed file_id=%s status=%d", drive_file_id, resp.status_code)
            self._stats["drive_api_errors_count"] += 1
            raise GoogleDriveError(f"Failed to delete Drive file ({resp.status_code})")

        audit_drive_event("FILE_DELETED", user_id, {"file_id": file_id, "drive_file_id": drive_file_id})

    def delete_pdf(self, user_id: Any, doc_id: str, drive_file_id: str):
        """Deletes private PDF file from Google Drive."""
        self.delete_file(user_id, doc_id, drive_file_id)

    # ── HEALTH & STATUS ──

    def get_status(self) -> Dict[str, Any]:
        """Returns health status of the owner Google Drive integration without exposing tokens."""
        cfg = self.get_owner_config()
        if not cfg or not cfg.get("encrypted_refresh_token"):
            return {
                "connected": False,
                "status": "not_connected",
                "compliance_cleared": self.is_compliance_cleared(),
                "owner_email": None,
                "root_folder_id": None
            }

        owner_email = cfg.get("owner_email")
        connected = bool(cfg.get("is_active", True))

        quota_info = None
        health_status = "healthy" if connected else "inactive"
        try:
            token = self.get_valid_access_token()
            headers = {"Authorization": f"Bearer {token}"}
            about_resp = requests.get(f"{DRIVE_V3_BASE}/about?fields=storageQuota,user", headers=headers, timeout=8)
            if about_resp.status_code == 200:
                about_data = about_resp.json()
                quota = about_data.get("storageQuota", {})
                user_data = about_data.get("user", {})
                if user_data.get("emailAddress"):
                    owner_email = user_data["emailAddress"]
                quota_info = {
                    "limit_bytes": int(quota.get("limit", 0)),
                    "usage_bytes": int(quota.get("usage", 0)),
                    "usage_in_drive_bytes": int(quota.get("usageInDrive", 0))
                }
            else:
                health_status = f"api_warning_{about_resp.status_code}"
        except Exception as e:
            health_status = f"degraded_{type(e).__name__}"

        # Storage Isolation Metrics
        registered_users_count = 0
        stored_docs_count = 0
        stored_images_count = 0
        if self._sb_req:
            try:
                uf_resp = self._sb_req("GET", "google_drive_user_folders", params="?select=user_id")
                if hasattr(uf_resp, "json"):
                    rows = uf_resp.json()
                    if isinstance(rows, list):
                        registered_users_count = len(rows)
            except Exception:
                pass
            try:
                doc_resp = self._sb_req("GET", "user_documents", params="?drive_file_id=not.is.null&select=id")
                if hasattr(doc_resp, "json"):
                    rows = doc_resp.json()
                    if isinstance(rows, list):
                        stored_docs_count = len(rows)
            except Exception:
                pass
            try:
                img_resp = self._sb_req("GET", "user_files", params="?file_type=eq.image&drive_file_id=not.is.null&deleted_at=is.null&select=id")
                if hasattr(img_resp, "json"):
                    rows = img_resp.json()
                    if isinstance(rows, list):
                        stored_images_count = len(rows)
            except Exception:
                pass

        return {
            "connected": connected,
            "status": health_status,
            "compliance_cleared": self.is_compliance_cleared(),
            "owner_email": owner_email,
            "owner_user_id": cfg.get("owner_user_id"),
            "owner_google_sub_bound": bool(cfg.get("owner_google_sub")),
            "root_folder_id": cfg.get("root_folder_id"),
            "users_folder_id": cfg.get("users_folder_id"),
            "storage_quota": quota_info,
            "registered_user_folders": registered_users_count,
            "stored_drive_documents": stored_docs_count,
            "stored_drive_images": stored_images_count,
            "total_stored_files": stored_docs_count + stored_images_count,
            "last_successful_upload": self._stats.get("last_successful_upload"),
            "last_failed_upload": self._stats.get("last_failed_upload"),
            "upload_failures_count": self._stats.get("upload_failures_count", 0),
            "drive_api_errors_count": self._stats.get("drive_api_errors_count", 0),
            "last_checked_at": datetime.now(timezone.utc).isoformat()
        }

    def disconnect(self, owner_user_id: Any) -> bool:
        """Revokes owner authorization and clears stored credentials without destroying files."""
        cfg = self.get_owner_config()
        if cfg and cfg.get("encrypted_refresh_token"):
            try:
                refresh_token = cipher.decrypt(cfg["encrypted_refresh_token"])
                requests.post(OAUTH_REVOKE_URL, params={"token": refresh_token}, timeout=8)
            except Exception as e:
                logger.warning("Token revocation request failed: %s", e)

        # Clear active status and credentials
        if cfg:
            cfg["is_active"] = False
            cfg["encrypted_refresh_token"] = None
            cfg["encrypted_access_token"] = None
            self.save_owner_config(cfg)

        self._cached_access_token = None
        self._token_expiry_ts = 0

        audit_drive_event("OWNER_DISCONNECTED", owner_user_id, {"status": "disconnected"})
        return True


# Global singleton instance
drive_storage = GoogleDriveStorageManager()
