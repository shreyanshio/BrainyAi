# BRAINY — SECURITY REMEDIATION REPORT

**Report Date:** November 2026  
**Auditor / Engineer:** Defensive Security Engineering Team  
**Remediation Scope:** Broken Function Level Authorization (BFLA), Session Invalidation, Mass Assignment, CSP Hardening, Automated Security Regression Tests  
**Target Files:** `app.py`, `security.py`, `tests/test_security_hardening.py`  
**Status:** Remediated & Verified  

---

## 1. Overview of Remediations

This report documents the security fixes engineered during the hardening audit of the BRAINY platform. All code changes follow defensive security principles:
1. Strict server-side authorization enforcement.
2. Complete session invalidation covering both ambient cookies and stateless JWT tokens.
3. Explicit allowlisting for all client-supplied input dictionaries.
4. Tightening of browser Content Security Policies.
5. 100% automated test coverage for all remediated vulnerabilities.

---

## 2. Itemized Remediation Details

### Finding SEC-01: Broken Function Level Authorization (BFLA) on Administrative AI Health & Telemetry Routes

- **Vulnerability Description:**  
  The endpoints `/api/admin/ai-health` and `/api/admin/ai-telemetry` expose real-time system health telemetry, provider error rates, failure events, and operational metrics. These endpoints were decorated with `@login_required` instead of `@admin_required`. Consequently, any authenticated student could inspect sensitive operational provider metrics.
- **Severity:** High (OWASP API Security Top 10 API5:2023 - Broken Function Level Authorization)
- **File Modified:** `app.py`
- **Code Diff:**
  ```python
  # BEFORE
  @app.route("/api/admin/ai-health", methods=["GET"])
  @app.route("/api/admin/ai-telemetry", methods=["GET"])
  @login_required
  def admin_ai_health():

  # AFTER
  @app.route("/api/admin/ai-health", methods=["GET"])
  @app.route("/api/admin/ai-telemetry", methods=["GET"])
  @admin_required
  def admin_ai_health():
  ```
- **Verification Evidence:**  
  Created automated test `test_student_user_forbidden_from_admin_ai_health` in `tests/test_security_hardening.py`. Authenticating with a valid student token and requesting `/api/admin/ai-health` now returns `HTTP 403 Forbidden`.

---

### Finding SEC-02: Stateless Bearer Token Replay After Logout

- **Vulnerability Description:**  
  The `/api/auth/logout` endpoint executed `session.clear()`, which destroyed the server-side Flask session cookie. However, web clients that stored HS256 JWT tokens (generated via `create_auth_token`) in `localStorage` could still submit those tokens, and `verify_auth_token()` would accept them until their expiration timestamp (`exp`), rendering logout incomplete for Bearer-authenticated clients.
- **Severity:** High (OWASP ASVS V3 - Session Management / Session Invalidation)
- **Files Modified:** `security.py`, `app.py`
- **Code Remediation:**
  1. Added in-memory token signature revocation store `_revoked_token_signatures: dict[str, float]`.
  2. Added user revocation epoch store `_user_revoked_before: dict[int, float]`.
  3. Added helper functions:
     - `revoke_auth_token(token: str) -> bool`: Extracts token signature and caches it until `exp`.
     - `revoke_user_tokens(user_id: int) -> None`: Sets an invalidation threshold for any token issued prior to the current timestamp.
     - `is_token_revoked(token: str, payload: dict) -> bool`: Checks signature and `iat <= _user_revoked_before[user_id]`.
  4. Integrated revocation check into `verify_auth_token()`:
     ```python
     if is_token_revoked(token, payload):
         return None
     ```
  5. Updated `/api/auth/logout` in `app.py`:
     ```python
     @app.route("/api/auth/logout", methods=["POST"])
     def auth_logout():
         user_id = session.get("user_id")
         auth_header = request.headers.get("Authorization", "").strip()
         if auth_header.lower().startswith("bearer "):
             token = auth_header[7:].strip()
             revoke_auth_token(token)

         data = request.get_json(silent=True) or {}
         req_token = data.get("token")
         if req_token and isinstance(req_token, str):
             revoke_auth_token(req_token)

         if user_id:
             revoke_user_tokens(user_id)

         session.clear()
         return jsonify({"status": "logged_out", "revoked": True})
     ```
- **Verification Evidence:**  
  Created automated tests `test_token_revocation_on_logout` and `test_user_wide_revocation_invalidates_earlier_tokens` in `tests/test_security_hardening.py`. Revoked tokens return `HTTP 401 Unauthorized` on subsequent requests.

---

### Finding SEC-03: Mass Assignment / Over-Posting in User Preferences

- **Vulnerability Description:**  
  The endpoint `POST /api/user/preferences` directly merged incoming JSON request keys into user profile storage (`updated_preferences.update(data)`). An attacker could submit privileged properties (e.g. `role: "admin"`, `is_admin: True`, `quota: 999999`) or oversized nested objects, polluting user profile memory.
- **Severity:** Medium (OWASP API Security Top 10 API6:2023 - Mass Assignment)
- **File Modified:** `app.py`
- **Code Remediation:**
  1. Defined strict allowlist of permissible preference keys:
     ```python
     ALLOWED_PREFERENCE_KEYS = {
         "theme", "font_size", "model_preference", "language",
         "depth_preference", "study_reminders", "math_rendering", "sound_effects"
     }
     ```
  2. Implemented strict dictionary validation and value filtering:
     ```python
     @app.route("/api/user/preferences", methods=["POST"])
     @login_required
     def update_user_preferences():
         user_id = session["user_id"]
         data = request.get_json(silent=True)
         if not isinstance(data, dict):
             return jsonify({"error": "Invalid request body: expected JSON object"}), 400

         filtered_preferences = {}
         for key, val in data.items():
             if key not in ALLOWED_PREFERENCE_KEYS:
                 continue
             if isinstance(val, str):
                 if len(val) > 64:
                     continue
                 filtered_preferences[key] = val
             elif isinstance(val, bool):
                 filtered_preferences[key] = val
             elif isinstance(val, (int, float)) and not isinstance(val, bool):
                 filtered_preferences[key] = val
         ...
     ```
- **Verification Evidence:**  
  Created automated tests `test_preference_mass_assignment_disallowed_keys_ignored` and `test_preference_rejects_non_dict_body`. Injected keys (`role`, `is_admin`, `quota`) are filtered out completely.

---

### Finding SEC-04: Missing Restrictive Directives in Content Security Policy (CSP)

- **Vulnerability Description:**  
  While the existing CSP set robust policies for `script-src`, `style-src`, and `frame-ancestors`, it lacked explicit restrictions on `object-src` and `base-uri`. Without `object-src 'none'`, legacy plugins or object tags could be leveraged if an injection occurred. Without `base-uri 'self'`, `<base href="...">` tags could redirect relative script and link lookups.
- **Severity:** Medium (OWASP Top 10:2021 A05 - Security Misconfiguration)
- **File Modified:** `security.py`
- **Code Remediation:**  
  Added `object-src 'none'; base-uri 'self'` to the `Content-Security-Policy` header in `security_headers()`:
  ```python
  response.headers['Content-Security-Policy'] = (
      "default-src 'self'; "
      "script-src 'self' 'unsafe-inline' https://telegram.org https://cdnjs.cloudflare.com "
      "https://accounts.google.com https://apis.google.com; "
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
      "font-src 'self' https://fonts.gstatic.com; "
      "img-src 'self' data: https://*.googleusercontent.com https://lh3.googleusercontent.com; "
      "frame-src https://accounts.google.com; "
      "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org; "
      "connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com; "
      "object-src 'none'; "
      "base-uri 'self'"
  )
  ```
- **Verification Evidence:**  
  Created automated test `test_csp_includes_object_src_none_and_base_uri_self` in `tests/test_security_hardening.py`. Responses confirm the presence of both directives.

---

## 3. Summary of Regression & Verification Results

All 244 unit and security regression tests executed cleanly with zero failures:
```
Ran 244 tests in 3.866s
OK
```
Frontend TypeScript type-checking completed with zero diagnostic errors:
```
npx.cmd tsc --noEmit
Exit Code: 0
```
No existing user workflows (Telegram bot, chat sessions, PDF Studio, quiz generation, notes assistant) were broken or regressed by these security enhancements.
