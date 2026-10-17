# Security Policy — Brainy AI

At **Brainy AI**, security and student privacy are foundational. This document describes our security architecture, data protection guarantees, and procedures for reporting vulnerabilities.

---

## 1. Supported Versions

Security updates are actively applied to the following branch:

| Version / Branch | Supported          | Status             |
| ---------------- | ------------------ | ------------------ |
| `main` (v2.0 SaaS)| :white_check_mark: | Actively supported |
| Legacy v1.x      | :x:                | Deprecated         |

---

## 2. Core Security Architecture

### A. Dual-Token Authentication & Cookie Hardening
- **Stateless Bearer Tokens (`HS256`)**: Brainy generates signed, tamper-proof bearer tokens for authenticated clients. This prevents cross-origin third-party cookie blocking between Cloudflare Workers frontends and cloud container backends (such as Railway).
- **Session Protection**: Flask cookies use `SameSite=Lax` (or `None; Secure` in production) and `HttpOnly` flags.
- **Header Synchronization**: All frontend requests attach both `credentials: 'include'` and `Authorization: Bearer <token>`.

### B. Cryptographic Privacy & Database Masking
- **Prompt Masking**: Sensitive user study questions and conversation titles are hashed / masked using SHA-256 before insertion into the Supabase database.
- **Zero Plaintext Query Leaks**: Even in the event of unauthorized read access to database storage, original student questions cannot be read in plaintext.

### C. Server-Authoritative Rate Limiting & 5-Hour Quotas
- **Per-User Throttling**: 10 messages per minute rate limiter using a sliding window.
- **Global 5-Hour Quota**: Server-authoritative atomic quota of 30 messages every 5 hours per user ID.
- **Prompt Injection Defense**: Input sanitization strips dangerous control characters, blacklists malicious jailbreak patterns, and bounds maximum input length.

### D. Administrative Control Panel (`/admin`)
- Strictly enforced server-side via the `@admin_required` decorator.
- Verified against the immutable `ADMIN_USER_IDS`, `ADMIN_USERNAMES`, and `ADMIN_EMAILS` server environment allowlists.
- Normal students attempting to query `/api/admin/*` receive immediate `403 Forbidden` responses.

### E. Supabase Row-Level Security (RLS)
- All production tables (`bot_users`, `user_memory`, `user_logins`, `chat_sessions`, `chat_messages`, `user_preferences`, `quiz_polls`, `quiz_scores`) have Row Level Security enabled.
- External or anon access without service authorization is denied by default.

---

## 3. Reporting a Vulnerability

If you discover a potential security vulnerability in Brainy AI, please report it privately:

1. **Email**: Open a security inquiry or email the maintainer at `security@cenai.study` (or contact `@shreyanshio` on GitHub).
2. **Details to include**:
   - Description of the vulnerability.
   - Proof of concept (PoC) or reproduction steps.
   - Potential impact.
3. **Response SLA**:
   - Acknowledgment within 24 hours.
   - Patch release within 72 hours for critical issues.

**Please do not open public GitHub issues for undisclosed security vulnerabilities.**
