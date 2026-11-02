# BRAINY — SECURITY OPERATIONS, RUNBOOK & INCIDENT RESPONSE

**Document Version:** 1.0.0  
**Target:** Production Operations, SRE & Security Engineering  
**Scope:** Secret Rotation, Incident Response, Session Revocation, Disaster Recovery, Continuous Monitoring  

---

## 1. Incident Response Plan (IRP)

### 1.1 Incident Classification & Severity Levels

| Severity | Definition | Target Triage Time | Target Containment Time |
|---|---|---|---|
| **SEV-1 (Critical)** | Active exploitation of RCE, full database compromise, exposed service-role key, cross-tenant data leakage. | < 15 minutes | < 1 hour |
| **SEV-2 (High)** | Broken authorization on privileged endpoints, session hijacking, confirmed SSRF or severe prompt injection vulnerability. | < 30 minutes | < 4 hours |
| **SEV-3 (Medium)** | Bypassable rate limiting, minor mass-assignment or prototype pollution, CSP bypass without active exploit. | < 2 hours | < 24 hours |
| **SEV-4 (Low)** | Informational finding, minor verbose logging, non-sensitive header inconsistency. | < 24 hours | Next deployment cycle |

### 1.2 Five-Phase Incident Handling Workflow

```
   +─────────────────────────────────────────────────────────────────────────────+
   |                             1. IDENTIFICATION                               |
   |  - Automated alert triggered (500 spike, rate limit flood, security.log)   |
   |  - External report received or anomaly detected in AI telemetry             |
   +──────────────────────────────────────┬──────────────────────────────────────+
                                          |
                                          v
   +─────────────────────────────────────────────────────────────────────────────+
   |                                2. CONTAINMENT                               |
   |  - Enable Maintenance Mode via Admin Config or Cloudflare Workers           |
   |  - Revoke affected user/admin sessions via revoke_user_tokens()             |
   |  - Temporarily block offending IP or CIDR range                             |
   +──────────────────────────────────────┬──────────────────────────────────────+
                                          |
                                          v
   +─────────────────────────────────────────────────────────────────────────────+
   |                                3. ERADICATION                               |
   |  - Rotate compromised secrets (JWT secret, Supabase keys, API keys)         |
   |  - Deploy code patch or update RLS policy via Supabase SQL migration        |
   +──────────────────────────────────────┬──────────────────────────────────────+
                                          |
                                          v
   +─────────────────────────────────────────────────────────────────────────────+
   |                                 4. RECOVERY                                 |
   |  - Verify system integrity and run security regression suite (244 tests)    |
   |  - Gradually lift maintenance mode and resume traffic                       |
   +──────────────────────────────────────┬──────────────────────────────────────+
                                          |
                                          v
   +─────────────────────────────────────────────────────────────────────────────+
   |                             5. POST-MORTEM & RCA                            |
   |  - Document root cause analysis (RCA), timeline, and defensive improvements |
   |  - Archive forensic logs and update BRAINY_SECURITY_AUDIT.md                |
   +─────────────────────────────────────────────────────────────────────────────+
```

---

## 2. Secret Rotation Standard Operating Procedures (SOPs)

### 2.1 JWT Authentication Secret Key (`AUTH_SECRET_KEY`)
To rotate the JWT signing key without disconnecting or logging out active users:
1. Generate a new 256-bit cryptographically secure key:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Set the current `AUTH_SECRET_KEY` value into `AUTH_PREVIOUS_KEYS`.
3. Set the newly generated key as `AUTH_SECRET_KEY` in the hosting environment (Railway, Docker, or environment configuration).
4. Restart the backend service.
   - Newly created tokens will be signed with the new key.
   - Active tokens signed with the previous key will continue to validate seamlessly via `AUTH_PREVIOUS_KEYS`.
5. After 7 days (the maximum lifetime of outstanding tokens), clear `AUTH_PREVIOUS_KEYS`.

### 2.2 Supabase Service Role Key & Database Credentials
1. Navigate to Supabase Project Dashboard -> **Settings** -> **API**.
2. Click **Generate new secret** for the Service Role Key.
3. Update `SUPABASE_SERVICE_KEY` in the backend environment variables.
4. Redeploy or restart the Flask service.
5. In Supabase, retire the old key once backend connectivity is verified via `GET /api/admin/health`.

### 2.3 AI Provider API Keys (Gemini, Groq, SambaNova, Cerebras)
1. Generate replacement keys in the respective provider console (Google AI Studio, Groq Console, etc.).
2. Update the comma-delimited environment variable (e.g. `GEMINI_API_KEYS=key_new_1,key_new_2`).
3. Trigger runtime reload via `POST /api/admin/ai/provider-toggle` or restart the backend.
4. Revoke previous keys in the provider dashboard.

---

## 3. Emergency Session & Access Revocation

If an account is compromised or an administrative token is leaked:

### 3.1 Immediate User Session Revocation
Execute the Python administrative revocation helper on the server:
```python
from security import revoke_user_tokens
# Revokes all active tokens issued to the user prior to this moment
revoke_user_tokens(target_user_id)
```
Or execute the administrative API:
```bash
curl -X POST https://api.brainy.ai/api/admin/users/<target_user_id>/suspend \
  -H "Authorization: Bearer <admin_token>"
```

### 3.2 Global Session Invalidation (Nuclear Option)
In the event of an uncontained session secret compromise:
1. Immediately change `AUTH_SECRET_KEY` in environment variables without populating `AUTH_PREVIOUS_KEYS`.
2. Clear Flask session store or restart the Flask process.
3. Every existing bearer token and session cookie will fail signature validation instantly, forcing all users to re-authenticate.

---

## 4. Backup, Point-in-Time Recovery & Data Protection

### 4.1 Database Backups (Supabase / PostgreSQL)
- **Automated Daily Backups:** Managed by Supabase with 7-day retention for standard tiers and 30-day retention for enterprise.
- **Point-in-Time Recovery (PITR):** Enables rolling back the database to any millisecond within the backup retention window to recover from accidental table drops or malicious modifications.
- **Local / Cold Schema Dump:**
  Schema migrations are versioned under `migrations/`:
  - `migrations/001_pdf_study_studio.sql`: PDF Studio tables, indices, RLS policies.
  - `migrations/002_chat_summary_and_constraints.sql`: Chat history and AI telemetry constraints.

### 4.2 Storage Bucket Backups (`study-pdfs`)
- All files are organized under `<user_id>/<doc_id>/original.pdf`.
- 5-day automated lifecycle cleanup policy (`cleanup_expired_documents()`) ensures that transient study material does not accumulate indefinitely, minimizing storage exposure window.

---

## 5. Security Logging, Telemetry & Anomaly Detection

### 5.1 Security Event Log Format
Security events are output to `stdout` and logged to `security.log`:
```
[SECURITY] {YYYY-MM-DD HH:MM:SS} | {event_type} | {ip} | {user_id} | {safe_detail}
```
Tracked event types:
- `rate_limit_exceeded`: IP exceeding 100 requests per minute.
- `blacklist_match`: Exploit pattern matched in parameters or payload.
- `csrf_origin_rejected`: Untrusted cross-site state-changing request blocked.
- `csrf_admin_origin_rejected`: Untrusted cross-site request targeting administrative routes.
- `server_error`: Internal 500 error intercepted and sanitized.

### 5.2 Real-Time Health & Telemetry Endpoints
- `GET /api/health`: Public liveness endpoint returning sanitized connectivity status without credentials.
- `GET /api/admin/health`: Admin-only comprehensive telemetry (Supabase latency, provider pools, memory).
- `GET /api/admin/ai-health`: Admin-only provider error rates, failure categorizations, and latency percentiles.

---

## 6. Pre-Release Security Checklist for Engineering

Before deploying any future update to production, engineers must verify:
- [ ] No raw SQL queries or string concatenations introduced; all database queries use PostgREST or RPC.
- [ ] Every new route requiring authentication has `@login_required` or `@admin_required`.
- [ ] Every route accessing user resources takes `user_id` from the verified session/token and checks ownership.
- [ ] All client-supplied dictionary inputs have strict allowlists (zero unbounded `dict.update(data)`).
- [ ] No secrets, keys, or credentials committed to git or exposed in client responses.
- [ ] Python unit and security tests pass: `python -m unittest discover tests`.
- [ ] Frontend TypeScript type-checks without errors: `npx tsc --noEmit`.
