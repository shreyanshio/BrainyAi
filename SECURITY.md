# Security Policy — Brainy AI

At **Brainy AI**, student data privacy, defensive engineering, and infrastructure integrity are foundational. This policy outlines our security architecture, data handling safeguards, and procedures for responsible vulnerability disclosure.

---

## 1. Supported Versions

Security patches and bug fixes are actively applied to the following branch:

| Version / Branch | Supported | Status |
|---|---|---|
| `main` (v2.0 SaaS) | :white_check_mark: | Actively supported |
| Legacy v1.x | :x: | Deprecated |

---

## 2. Core Security Architecture

### A. Dual-Token Authentication & Cookie Hardening
* **Stateless HS256 Bearer Tokens**: Authenticated clients receive a cryptographically signed HMAC-SHA256 JWT containing verified user claims (`user_id`, `username`, `first_name`). This eliminates cross-origin third-party cookie blocking between Cloudflare Workers and Railway backends.
* **Cookie Security**: Where cookies are used, they enforce `HttpOnly`, `SameSite=None` (in production over HTTPS) or `SameSite=Lax` (in local development), and the `Secure` attribute.
* **Dual Header Propagation**: Client requests attach both `Authorization: Bearer <token>` and `credentials: 'include'` to ensure consistent identity validation.

### B. Cryptographic Privacy & Prompt Masking
* **SHA-256 Obfuscation**: In the database, conversation session titles and sensitive student queries are hashed using SHA-256 before storage in Supabase tables.
* **Zero Plaintext Query Leaks**: Even if read access to raw database tables were compromised, user queries cannot be read in plaintext.

### C. Server-Authoritative Rate Limiting & 5-Hour Quotas
* **Per-User Rate Limiting**: Enforces a sliding-window maximum of 10 requests per minute per user ID.
* **Atomic 5-Hour Quota**: Limits students to 30 queries per 5-hour cycle, enforced strictly on the server before dispatching queries to external AI APIs.
* **Input Sanitization**: Control characters, shell injection vectors, and known prompt injection / jailbreak patterns are intercepted and rejected by `security.py`.

### D. Administrative Authorization (`/admin`)
* **Strict Server-Side Guard**: Administrative routes under `/api/admin/*` are protected by the `@admin_required` decorator.
* **Immutable Environment Allowlist**: Access requires identity matching against server-side environment variables (`ADMIN_USER_IDS`, `ADMIN_USERNAMES`, `ADMIN_EMAILS`).
* **Non-Privileged Rejection**: Unauthorized requests receive immediate `403 Forbidden` responses.

### E. Supabase Row Level Security (RLS)
* All 8 production tables (`bot_users`, `user_memory`, `user_logins`, `chat_sessions`, `chat_messages`, `user_preferences`, `quiz_polls`, `quiz_scores`) have Row Level Security enabled.
* Direct public/anonymous client access is blocked; queries are mediated exclusively by the server via `service_role` credentials.

---

## 3. Reporting a Vulnerability

We take security reports seriously and appreciate responsible disclosure.

### Private Reporting Channels
If you discover a potential security vulnerability, **do not open a public GitHub issue**. Instead, report it privately:

1. **Email**: Send details to `security@cenai.study`.
2. **GitHub Security Advisories**: If available on the repository, submit a draft report via the **Security > Report a vulnerability** tab.
3. **Maintainer Contact**: Contact [@shreyanshio](https://github.com/shreyanshio) directly on GitHub.

### What to Include in Your Report
To help us investigate and triage the issue quickly, please provide:
* A detailed description of the vulnerability and its potential impact.
* Clear, step-by-step reproduction instructions or a minimal Proof of Concept (PoC).
* Affected endpoints, files, or components.
* Suggestions for remediation, if known.

### What to Expect
* **Acknowledgment**: We aim to acknowledge receipt of reports within 48 hours.
* **Assessment**: We will investigate the issue, verify its severity, and keep you updated on remediation progress.
* **Patching**: Critical vulnerabilities will be prioritized for immediate patching.
* **Attribution**: Responsible reporters will be credited in our release notes (unless anonymity is requested).

---

## 4. Credential & Secret Management

If you suspect an API key, bot token, or service-role credential has been exposed:
1. Immediately revoke the key in the provider console (e.g., Supabase, Groq, Google Cloud, Telegram BotFather).
2. Generate a new credential and update your environment variables.
3. Notify the project maintainer so deployment configurations can be refreshed.
