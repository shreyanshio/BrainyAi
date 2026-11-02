# BRAINY — APPLICATION SECURITY ARCHITECTURE

**Document Version:** 2.0.0  
**Classification:** Defensive Security Architecture & Threat Boundary Specification  
**Status:** Validated & Released  
**Target System:** BRAINY (Web Application, Telegram Bot, REST API, PDF Study Studio, AI Routing Engine)

---

## 1. Application Architecture & High-Level Topology

BRAINY is an intelligent AI-powered study companion designed for students and educators. Its architecture consists of six primary functional tiers operating across separated network boundaries:

```
+───────────────────────────────────────────────────────────────────────────────────+
|                                    CLIENT TIER                                    |
|   +──────────────────────────────+            +───────────────────────────────+   |
|   |  Next.js 14 Web Frontend     |            |  Telegram Native Client       |   |
|   |  (React, TypeScript, Tailwind|            |  (Mobile, Desktop, Web App)   |   |
|   |   Cloudflare Workers Hosted) |            |                               |   |
|   +──────────────┬───────────────+            +───────────────┬───────────────+   |
+──────────────────┼────────────────────────────────────────────┼───────────────────+
                   | HTTPS (TLS 1.3) / JSON                     | HTTPS / Webhook /
                   | Origin & Referer Checked                   | Polling
                   v                                            v
+───────────────────────────────────────────────────────────────────────────────────+
|                                 APPLICATION GATEWAY                               |
|                         Flask REST API & Security Guard                           |
|   +───────────────────────────────────────────────────────────────────────────+   |
|   |  Security Guard Middleware:                                               |   |
|   |  - Token Bucket / Supabase RPC Distributed Rate Limiting (100 req/min/IP)  |   |
|   |  - Query / Body Sanitization & Exploit Signature Filter                   |   |
|   |  - Dual Authentication Resolver (HS256 Bearer JWT + Ambient Cookie)       |   |
|   |  - Strict CSRF Origin / Sec-Fetch-Site Policy Enforcement                 |   |
|   |  - Security Response Headers (CSP, HSTS, nosniff, SAMEORIGIN, no-store)   |   |
|   +───────────────────────────────────────────────────────────────────────────+   |
+───────────┬──────────────────────────┬─────────────────────────────┬──────────────+
            |                          |                             |
            v                          v                             v
+───────────────────────+  +───────────────────────+  +─────────────────────────────+
|   AI ROUTING ENGINE   |  |   PDF STUDY STUDIO    |  |       DATABASE TIER         |
|  - Task Classifier    |  |  - PyMuPDF Native Ext |  |  Supabase PostgreSQL        |
|  - Provider Failover  |  |  - Tesseract OCR Pipe |  |  - Row Level Security (RLS) |
|  - AST Math Evaluator |  |  - Ownership Bound    |  |  - Session / Message Store  |
|  - SSRF-Safe Search   |  |  - 5-Day Retention    |  |  - Encrypted User Memory    |
+───────────┬───────────+  +───────────┬───────────+  +──────────────┬──────────────+
            |                          |                             |
            v                          v                             v
+───────────────────────+  +───────────────────────+  +─────────────────────────────+
| EXTERNAL AI PROVIDERS |  |   STORAGE BUCKET      |  |     ADMINISTRATIVE APIS     |
| - Google Gemini 2.5   |  | Supabase Storage      |  |  - Role & Email Allowlist   |
| - Groq Llama 3.3      |  | 'study-pdfs' (Private)|  |  - User Management & Quota  |
| - SambaNova Systems   |  | Server-mediated auth  |  |  - Provider Health Telemetry|
| - Cerebras Inference  |  | user_id isolation     |  |  - Immutable Audit Logging  |
+───────────────────────+  +───────────────────────+  +─────────────────────────────+
```

---

## 2. Trust Boundaries

BRAINY strictly separates untrusted actors from protected internal services through five distinct security boundaries:

### Boundary 1: Client Browser / Telegram Client to Flask API
- **Classification:** Untrusted to Semi-Trusted.
- **Controls Enforced:**
  - TLS 1.3 encryption in transit.
  - Rate limiting per remote IP (100 requests/minute default, configurable).
  - Exploit pattern inspection on parameters and payloads (XSS, SQLi, command injection patterns).
  - CSRF origin validation matching against explicit origin allowlists (`DEFAULT_ALLOWED_ORIGINS` + dynamic environment origins).
  - Case-insensitive Bearer token authentication and cryptographically signed session cookies (`HttpOnly`, `SameSite=None/Lax`, `Secure`).

### Boundary 2: Flask API to PostgreSQL Database (Supabase)
- **Classification:** Trusted Server-to-Database Channel.
- **Controls Enforced:**
  - Authenticated REST API calls via HTTPS using the Supabase Service Role Key or Anon Key.
  - Parameterized PostgREST queries preventing SQL injection at the protocol layer.
  - Row Level Security (RLS) policies defining tenant boundaries on all tables (`chat_sessions`, `chat_messages`, `user_documents`, `document_pages`, `document_notes`, `document_quizzes`, `document_flashcards`, `document_study_progress`).
  - Stored Procedures / RPC calls (`increment_rate_limit_window`) executing isolated atomic queries with strict input casting.

### Boundary 3: Flask API to Supabase Object Storage
- **Classification:** Private Storage Channel.
- **Controls Enforced:**
  - Dedicated private bucket: `study-pdfs` (public access completely disabled).
  - Direct client uploads are prohibited; all uploads pass through `pdf_service.upload_and_process_pdf()` on the backend.
  - File path structure strictly isolated by user ID: `<user_id>/<doc_id>/original.pdf`.
  - Zero public URL generation; downloads and page renders require server-side user ownership validation.

### Boundary 4: Flask API to External AI Providers
- **Classification:** Outbound Secure Integration.
- **Controls Enforced:**
  - API keys stored strictly in server-side environment variables (`GEMINI_API_KEYS`, `GROQ_API_KEYS`, etc.), never exposed to clients.
  - Prompt injection boundary fencing: Grounding search outputs and external web results are wrapped in non-executable demarcation blocks (`<<<SEARCH_GROUNDING_BEGIN>>>` ... `<<<SEARCH_GROUNDING_END>>>`) with strict system prompt directives.
  - Payload size limits: Ingestion capped at model token budgets with fallback continuation handling.

### Boundary 5: Flask API to Administrative Interfaces
- **Classification:** Privileged Administrative Boundary.
- **Controls Enforced:**
  - Dual-layer RBAC via `@admin_required` decorator.
  - Mandatory verified identity corroboration: Requires an active session AND matching against `ADMIN_USER_IDS`, `ADMIN_USERNAMES`, or `ADMIN_EMAILS` (corroborated via Google Identity Services verified email tokens).
  - Self-action prevention: Admins cannot suspend or delete their own accounts.
  - Comprehensive action auditing recorded in `admin_service.audit`.

---

## 3. Authentication & Authorization Flow

BRAINY supports four distinct, hardened authentication mechanisms designed to accommodate diverse client environments without compromising security:

```
                                  AUTHENTICATION WORKFLOW
                                  
   +─────────────────────────────────────────────────────────────────────────────+
   |                             Client Request                                  |
   +──────────────────────────────────────┬──────────────────────────────────────+
                                          |
                +─────────────────────────┴─────────────────────────+
                |                                                   |
         [Web Platform]                                    [Telegram Platform]
                |                                                   |
      +─────────┴─────────+                               +─────────┴─────────+
      |                   |                               |                   |
 [Google GIS]       [Student Pass]                  [WebApp initData]  [Bot Chat Auth]
      |                   |                               |                   |
  Verify ID          Generate Pass                    HMAC-SHA256         Telegram ID
 Token via GIS       HMAC Signed                      Validation via       Validation
 Google API          Random UID                       Bot Token Secret    Against DB
      |                   |                               |                   |
      +─────────┬─────────+                               +─────────┬─────────+
                |                                                   |
                v                                                   v
   +─────────────────────────────────────────────────────────────────────────────+
   |                        Session & Token Generation                           |
   |  - HS256 JWT Bearer Token (Payload: sub, username, name, email, role, iat, exp)|
   |  - Flask Session Cookie (HttpOnly, Secure, SameSite)                       |
   +──────────────────────────────────────┬──────────────────────────────────────+
                                          |
                                          v
   +─────────────────────────────────────────────────────────────────────────────+
   |                           Request Authorization                             |
   |  1. Bearer Header Check: Verify signature, expiry, and revocation table     |
   |  2. Ambient Cookie Check: Verify session state AND CSRF Origin / Sec-Fetch  |
   |  3. Role Verification: Strict RBAC check if privileged endpoint requested    |
   +─────────────────────────────────────────────────────────────────────────────+
```

### 3.1 Google Identity Services (GIS) OAuth
- Client receives a Google ID Token (`credential`) via Google One Tap or GIS Button.
- Token is submitted via `POST /api/auth/google`.
- Server validates the token against `https://oauth2.googleapis.com/tokeninfo?id_token=<token>` or Google OAuth libraries.
- Server validates audience (`aud` == `GOOGLE_CLIENT_ID`), issuer (`iss` in `accounts.google.com`), and expiration.
- User email, name, and profile picture are extracted; user record is upserted into Supabase `users` table.

### 3.2 Cryptographic Student Pass
- One-click zero-password authentication for friction-free student access (`POST /api/auth/student_pass`).
- Generates a cryptographic pseudo-anonymous student identity:
  - `user_id`: 64-bit integer derived from `secrets.randbits(52)`.
  - `pass_key`: Hexadecimal token derived from `secrets.token_hex(24)`.
- Prevents collisions and spoofing through cryptographic uniqueness.

### 3.3 Telegram WebApp `initData` Verification
- WebApp transmits query string `initData` containing user data, query ID, and `hash`.
- Server calculates `secret_key = HMAC_SHA256("WebAppData", TELEGRAM_BOT_TOKEN)`.
- Server sorts all parameters alphabetically (excluding `hash`), computes `calculated_hash = HMAC_SHA256(secret_key, data_check_string)`.
- Requires exact `hmac.compare_digest(calculated_hash, received_hash)` match; rejects replayed or forged queries.

### 3.4 Stateless HS256 JWT Bearer Tokens
- Tokens are signed using server secret `_get_auth_secret_key()` with algorithm `HS256`.
- Payload schema: `{"sub": user_id, "username": str, "name": str, "email": str, "role": str, "iat": int, "exp": int}`.
- Validity checks:
  - Header algorithm must be strictly `HS256`.
  - Signature verified using active key or legacy rotation candidates (`AUTH_PREVIOUS_KEYS`).
  - Mandatory `sub` and `exp` claims. Expiration strictly evaluated against `time.time()`.
  - Issued-at (`iat`) checked for future clock drift (> 300s rejected).
  - Token signature checked against `_revoked_token_signatures`.
  - User ID checked against `_user_revoked_before` timestamp.

---

## 4. Frontend-to-Backend Security Architecture

1. **Cross-Origin Resource Sharing (CORS):**
   - Configured with `flask_cors.CORS`.
   - Origins restricted to `DEFAULT_ALLOWED_ORIGINS` and trusted production endpoints (`https://brainyai.cenai.workers.dev`, `https://web.telegram.org`, etc.).
   - Explicit headers exposed: `Content-Type`, `Authorization`.
   - `Access-Control-Allow-Credentials: true` strictly enforced.

2. **CSRF Mitigation for Ambient Session Cookies:**
   - Any state-changing HTTP method (`POST`, `PUT`, `PATCH`, `DELETE`) relying on cookie authentication must pass `validate_csrf_origin()`.
   - Validates `Origin` and `Referer` headers against `get_allowed_origins()` and current request `host_url`.
   - Rejects `Sec-Fetch-Site: cross-site` requests immediately with `403 CSRF_ORIGIN_REJECTED`.
   - Bearer token authenticated requests are inherently CSRF-immune as browsers do not attach custom `Authorization` headers across domains.

---

## 5. Backend-to-Database & Storage Architecture

1. **Database Access Paradigm:**
   - RESTful PostgREST queries over TLS 1.3.
   - Zero raw SQL string interpolation.
   - Column projection allowlists (`select=id,user_id,title,created_at`) prevent over-fetching sensitive columns.

2. **Row Level Security (RLS) Policies:**
   - Every table maintains explicit RLS enabling:
     - `ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;`
     - `ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;`
     - `ALTER TABLE user_documents ENABLE ROW LEVEL SECURITY;`
     - `ALTER TABLE document_pages ENABLE ROW LEVEL SECURITY;`
     - `ALTER TABLE document_notes ENABLE ROW LEVEL SECURITY;`
     - `ALTER TABLE document_quizzes ENABLE ROW LEVEL SECURITY;`
     - `ALTER TABLE document_flashcards ENABLE ROW LEVEL SECURITY;`
     - `ALTER TABLE document_study_progress ENABLE ROW LEVEL SECURITY;`
   - Tenant isolation policies restrict `SELECT`, `INSERT`, `UPDATE`, and `DELETE` operations strictly to matching authenticated user IDs (`auth.uid() = user_id`).

3. **Storage Bucket Hardening:**
   - Bucket `study-pdfs` configured as `public = false`.
   - Direct download URLs require authentication.
   - Server handles all file writes, streaming downloads, and page extractions.

---

## 6. Identified Attack Surfaces & Enforcement Mapping

| Sensitive Operation / Target | Potential Threat | Enforcing Module | Applied Security Control |
|---|---|---|---|
| User Authentication | Credential Stuffing, Replay, Forgery | `security.py`, `app.py` | Google GIS Tokeninfo verification, HMAC-SHA256 signature, HS256 JWT verification |
| Session Termination | Zombie Token Replay, Stolen JWT Reuse | `security.py`, `app.py` | `revoke_auth_token()`, `revoke_user_tokens()`, `session.clear()` |
| User Profile Preferences | Mass Assignment, Prototype Pollution | `app.py` | `ALLOWED_PREFERENCE_KEYS` whitelist, length and type validation |
| Chat Session Access / Deletion | IDOR / BOLA | `app.py`, `study_bot.py` | `sb_get_session(session_id, user_id)` tenant check, RLS |
| PDF Document Upload | Remote Code Execution, File Bomb, Path Traversal | `pdf_studio/service.py` | `validate_pdf_file` (%PDF- magic bytes, 10MB cap, `os.path.basename` clean) |
| PDF Document Retrieval / Delete | IDOR / Cross-Tenant Data Access | `pdf_studio/service.py` | `get_document(doc_id, user_id)` strict ownership validation |
| Administrative Actions | Privilege Escalation (BFLA) | `app.py`, `admin_service` | `@admin_required`, Verified email check, self-action prevention |
| Math Engine Problem Solving | Remote Code Execution / Sandbox Escape | `ai_routing/maths.py` | Safe AST node allowlist, zero `eval()`, zero `exec()`, length caps |
| Web Search Research | Server-Side Request Forgery (SSRF) | `ai_routing/providers/search_provider.py` | `is_safe_url` IP validation, loopback / RFC 1918 / cloud metadata blocking |
| AI Prompt Grounding | Prompt Injection / Instruction Overriding | `ai_routing/router.py` | `_sanitize_grounding_text()`, boundary fences, safety directives |
| Rate-Limited APIs | Denial of Service / API Abuse | `security.py` | Token bucket per IP, Supabase RPC `increment_rate_limit_window` |
| Client-Side Rendering | Cross-Site Scripting (XSS), Clickjacking | `security.py` | Strict CSP (`object-src 'none'`, `base-uri 'self'`), `X-Frame-Options: SAMEORIGIN` |
