# Brainy Performance Security & Privacy Review

**Status:** Verified & Hardened  
**Audit Standard:** Zero-Trust Client, Server-Enforced Boundaries  
**Security Modules:** `security.py`, `app.py`, `pdf_studio/service.py`  

---

## 1. Tenant Data Isolation & Multi-User Privacy

1. **User-Scoped Queries:**
   - Every Supabase query explicitly binds `user_id=eq.{user_id}` or verifies session ownership before reading/writing data.
   - Cross-user data retrieval is architecturally impossible at the query layer.
2. **Encrypted Chat History at Rest:**
   - User chat messages are encrypted using AEAD AES-256-GCM (`enc_v2_` format) with 96-bit unique nonces before storage in the Supabase database.
   - Legacy `hsh_v1_` records are automatically migrated on read.
3. **No Cross-User Caching:**
   - The in-memory exact response cache (`ai_routing/cache.py`) enforces strict isolation: personal profile data, chat session messages, and private PDF documents are **never** globally cached.

---

## 2. Credential Security & Masking

1. **Zero Client-Side Secret Exposure:**
   - Provider API keys (`GEMINI_API_KEY`, `GROQ_API_KEYS`, `TAVILY_API_KEYS`, `SUPABASE_KEY`) remain strictly on the backend server.
   - Frontend bundles contain zero API keys or service role credentials.
2. **Credential Redaction in Logs (`mask_credential`):**
   - Whenever provider errors or quota events are logged, all keys are masked (e.g. `********1234`).
   - Private user queries and prompt chain-of-thought are never logged to console or disk.

---

## 3. Defense Against API Abuse & CSRF

1. **Anti-CSRF Origin Checking:**
   - Mutation endpoints (`POST`, `PATCH`, `DELETE`) enforce origin header validation against the configured `APP_URL` and permitted domains.
   - Cross-origin malicious requests are rejected with HTTP 403.
2. **Dual-Tier Rate Limiting:**
   - Global rate limit: 10 messages per minute per user.
   - Search rate limit: 5 search queries per minute per user (burst ceiling).
   - Atomic quota window: 30 messages per 5 hours per user, atomically tracked via `brainy_consume_user_quota` stored procedure in Supabase.
