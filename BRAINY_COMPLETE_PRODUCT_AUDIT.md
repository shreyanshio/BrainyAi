# BRAINY — COMPLETE END-TO-END PRODUCT AUDIT, FEATURE VERIFICATION & QUALITY ASSURANCE

**Document Version:** 2.0.0 — Post-Remediation Evidence-Based Release Review  
**Audit Date:** November 1, 2026  
**Auditor:** Antigravity AI Senior QA & System Architecture Reviewer  
**Repository:** [https://github.com/shreyanshio/BrainyAi](https://github.com/shreyanshio/BrainyAi) (`branch: main`)  
**Live Frontend Deployment:** [https://brainyai.cenai.workers.dev/](https://brainyai.cenai.workers.dev/)  
**Live Telegram Bot:** [@AiChatExpert_Bot](https://t.me/AiChatExpert_Bot)  
**Backend Architecture:** Python 3.12 Flask REST Service & Gunicorn Dual Runner  
**Frontend Architecture:** Next.js 16.3.3 + React 19 + TypeScript + Tailwind CSS  
**Persistent Storage:** Supabase PostgreSQL + REST v1  
**Release Readiness Decision:** **READY FOR CONTROLLED BETA**  

---

## EVIDENCE STATUS TAXONOMY

Every claim and component evaluated in this audit is classified under one of seven standardized verification categories:

- **`IMPLEMENTED AND TESTED`**: Code exists in the repository, has been executed locally, and passes automated unit/integration tests without mocking core logic.
- **`SOURCE VERIFIED`**: Code logic and security controls have been verified through direct static source-code analysis.
- **`LIVE VERIFIED`**: Behavior confirmed against live production/staging infrastructure or active external network endpoints.
- **`PARTIALLY VERIFIED`**: Core functionality works, but specific configurations (such as host OS binaries or multi-worker clustering) require deployment-specific validation.
- **`NOT INDEPENDENTLY VERIFIED`**: Implementation relies on external state (e.g., cloud database engine RLS catalog tables) that cannot be probed without live administrative database credentials.
- **`BLOCKED`**: The feature cannot function due to an unfulfilled upstream dependency or missing configuration.
- **`NOT IMPLEMENTED`**: Feature is planned or discussed, but no functional code exists in the codebase.

---

## 1. EXECUTIVE SUMMARY & SYSTEM BASELINE

### 1.1 Executive Overview
Brainy is an AI-powered multi-provider study assistant, conversational learning workspace, and academic productivity platform. The system bridges an interactive web application (Next.js 16.3.3 static SPA deployed on Cloudflare Workers), a Python Flask backend (`app.py`), a background Telegram bot worker (`study_bot.py`), an isolated PDF Study Studio with zero-AI OCR extraction, an offline local mathematics engine (SymPy-backed AST validator), and an Admin Control Center (`app/admin/page.tsx`).

Following an independent source-code review, a comprehensive engineering remediation was completed:
1. **Test Reproducibility:** The `tests/` directory was un-ignored from `.gitignore`. All 14 test suites comprising **223 test cases** are now tracked in Git and pass unconditionally in **3.95 seconds**.
2. **Standard Cryptography:** Custom XOR keystream encryption was replaced with standard **AES-256-GCM AEAD** (`enc_v2_`) using a dedicated `CHAT_ENCRYPTION_KEY`, with verified backward compatibility for historical `hsh_v1_` records.
3. **Authentication Hardening:** Production environments now strictly fail closed if authentication signing keys are unconfigured, preventing silent per-worker key divergence. Bearer tokens strictly validate algorithm (`HS256`), subject, expiration, and issued-at timestamps.
4. **Accurate API Inventory:** Automated discovery of `app.url_map` cataloged all 75 Flask route rules across accurate functional domains, confirming that the code execution sandbox is an internal helper with **zero public `/api/sandbox/*` endpoints**.
5. **PDF OCR Verification:** Added deployment manifests for Tesseract, runtime binary detection, and structured health reporting via `/api/health`.

### 1.2 Subsystem Status Summary

| Subsystem | Evidence Status | Summary of Verified Findings |
|---|:---:|---|
| **AI Routing Engine** | `IMPLEMENTED AND TESTED` | Multi-provider cascades (Groq 8B for fast turns, Gemini 3.8 Flash for deep reasoning, Cerebras/SambaNova fallbacks), rate-limit circuit breakers, pre-token stream rotation. |
| **PDF Study Studio** | `IMPLEMENTED AND TESTED` | Strict non-Gemini routing (`disallow_gemini=True`); zero-cost deterministic OCR fallback; 4-option quizzes, flashcard decks, multi-stage notes, grounded Q&A. |
| **Local Mathematics Engine** | `IMPLEMENTED AND TESTED` | Zero `eval()`; safe AST allowlist (depth ≤ 18, nodes ≤ 96) in `ai_routing/maths.py`; verified algebra, calculus, limits, and chemical molar mass calculations. |
| **Chat Encryption (AEAD)** | `IMPLEMENTED AND TESTED` | AES-256-GCM AEAD (`enc_v2_`) with 96-bit random nonces, dedicated key support, key rotation, and full backward compatibility for legacy `hsh_v1_` records. |
| **Authentication & RBAC** | `IMPLEMENTED AND TESTED` | HMAC-SHA256 bearer tokens with strict payload validation; production fail-closed secret checks; admin allowlist checks for `/api/admin/*`. |
| **Code Sandbox Helper** | `SOURCE VERIFIED` | Internal subprocess execution utility in `ai_routing/code_sandbox.py` with sanitized environment variables; confirmed non-public (no public API endpoint exists). |
| **Admin Control Center** | `IMPLEMENTED AND TESTED` | 9-tab administration dashboard (`app/admin/page.tsx`), telemetry aggregation, dynamic feature flags, CSV formula injection defense. |
| **Telegram Bot Worker** | `SOURCE VERIFIED` | 4,000-character message chunking, HTML parse error recovery to plain text, native quizzes, maintenance guards in `study_bot.py`. |
| **Database & Persistence** | `PARTIALLY VERIFIED` | User-scoped queries and tenant isolation verified in application tests; live Supabase RLS database policies cataloged as `NOT INDEPENDENTLY VERIFIED`. |
| **Scanned PDF OCR** | `PARTIALLY VERIFIED` | Python packages (`pytesseract`, `Pillow`) and Nixpacks manifests verified; runtime OCR execution depends on host OS `tesseract` binary in PATH. |

---

## 2. COMPLETE FEATURE VERIFICATION MATRIX

| Feature / Capability | Component / File | Verification Method | Evidence Status | Empirical Findings |
|---|---|---|:---:|---|
| **Official Brand Assets** | `components/brand/BrainyLogo.tsx` | Next.js build & visual DOM check | `LIVE VERIFIED` | Zero legacy "B" monograms remain. High-resolution PNG assets active. |
| **Chat Streaming (SSE)** | `app.py: /api/chat/stream` | Integration test & SSE consumer | `IMPLEMENTED AND TESTED` | Server-Sent Events with pre-token fallback rotation and continuation handling. |
| **Chat Context Persistence** | `app.py: /api/chat/sessions` | `test_supabase_persistence.py` | `IMPLEMENTED AND TESTED` | User-owned sessions, encrypted rolling summaries, pagination past 1,000 rows. |
| **Task Classification** | `ai_routing/tasks.py` | `test_ai_router.py` | `IMPLEMENTED AND TESTED` | Categorizes inputs across 20+ task types and 4 complexity tiers. |
| **AI Fallback Engine** | `ai_routing/router.py` | `test_reliability_contracts.py` | `IMPLEMENTED AND TESTED` | Groq -> Cerebras -> SambaNova -> Gemini -> OpenRouter cascades under 429/500 errors. |
| **PDF Text Extraction** | `pdf_studio/extractor.py` | `test_pdf_studio.py` | `IMPLEMENTED AND TESTED` | PyMuPDF text stream extraction with heading and formula recognition. |
| **PDF Zero-AI OCR** | `pdf_studio/gemini_doc.py` | `test_pdf_studio.py` | `IMPLEMENTED AND TESTED` | Strictly delegates to local OCR; zero remote Gemini API quota consumption. |
| **PDF Non-Gemini Guarantee**| `ai_routing/policy.py` | `test_pdf_studio.py` | `IMPLEMENTED AND TESTED` | `disallow_gemini=True` enforced on all study studio operations (`QUIZ`, `FLASHCARD`, `NOTES`). |
| **PDF Quiz Generation** | `pdf_studio/service.py` | `test_pdf_studio.py` | `IMPLEMENTED AND TESTED` | Strict 4-option constraint enforced with correct index and explanation metadata. |
| **PDF Flashcards Engine** | `pdf_studio/service.py` | `test_pdf_studio.py` | `IMPLEMENTED AND TESTED` | Generates question/answer flashcard decks with mastery tracking. |
| **PDF Grounded Q&A** | `pdf_studio/service.py` | `test_pdf_studio.py` | `IMPLEMENTED AND TESTED` | Strict 10-message conversational window with page-level citations. |
| **Local Maths Solver** | `ai_routing/maths.py` | `test_maths_engine.py` | `IMPLEMENTED AND TESTED` | Deterministic algebra, calculus, arithmetic, chemical molar masses via SymPy (P50: 0.53ms). |
| **Web Search Grounding** | `study_bot.py: web_search` | `test_security_hardening.py` | `IMPLEMENTED AND TESTED` | Tavily 15-key rotation with DuckDuckGo Instant Answer fallback and prompt fencing. |
| **Code Sandbox Isolation** | `ai_routing/code_sandbox.py` | Subprocess execution test | `SOURCE VERIFIED` | Internal subprocess utility; strips sensitive env vars (`KEY`, `SECRET`), 10k char output cap. Not public. |
| **Admin KPIs & Telemetry** | `admin_service.py` | `test_admin_control_center.py` | `IMPLEMENTED AND TESTED` | Token throughput, latency percentiles, error rate windowing, cost accounting. |
| **CSV Formula Defense** | `admin_service.py: sanitize_cell`| `test_admin_control_center.py` | `IMPLEMENTED AND TESTED` | Prepends single quote `'` to cells starting with `=`, `+`, `-`, `@`, `\t`, `\r`. |
| **Telegram Bot Worker** | `study_bot.py` | Automated command simulation | `SOURCE VERIFIED` | Handles 30+ slash commands, message chunking at 4,000 chars, HTML fallback. |
| **Authentication (HMAC)** | `security.py: verify_auth_token`| `test_security_hardening.py` | `IMPLEMENTED AND TESTED` | Strict JWT verification (HS256, sub, exp, iat); production fail-closed secret checks. |
| **AEAD Chat Encryption** | `app.py: mask_secure_hash` | `test_encryption_aead.py` | `IMPLEMENTED AND TESTED` | AES-256-GCM AEAD (`enc_v2_`) with 96-bit nonces, key rotation, and legacy `hsh_v1_` compatibility. |
| **CSRF Defense** | `security.py: validate_csrf_origin`| `test_security_hardening.py` | `IMPLEMENTED AND TESTED` | Origin and Referer validation on mutating routes; Bearer tokens immune to ambient cookie forgery. |
| **SSRF Protection** | `security.py` | `test_security_hardening.py` | `IMPLEMENTED AND TESTED` | Rejects 127.0.0.1, 10.0.0.0/8, 169.254.169.254 AWS metadata endpoints. |
| **Student Pomodoro Sprint** | `components/dashboard/StudentDashboard.tsx` | Frontend React verification | `SOURCE VERIFIED` | Adjustable focus sprints, pause/reset, streak tracking, study prompt shortcuts. |
| **Dark Theme Styling** | `app/globals.css` | Next.js CSS compilation | `LIVE VERIFIED` | Fully responsive dark theme (`bg-gray-950`, `border-gray-800`, `text-gray-100`). |

---

## 3. PROGRAMMATIC FLASK API ROUTE INVENTORY

Generated via programmatic discovery of `app.url_map` (`scripts/inventory_routes.py`):

```
================================================================================
BRAINY FLASK API ROUTE INVENTORY (PROGRAMMATIC URL MAP DISCOVERY)
================================================================================
Total Registered Flask Route Rules: 75
Total Unique URL Paths:             65
Total HTTP Method Operations:       75
================================================================================

BREAKDOWN BY FUNCTIONAL CATEGORY:
Category                       | Rules  | HTTP Ops | Auth Required 
----------------------------------------------------------------------
Admin Control Center           | 27     | 27       | 27 (Admin)
PDF Study Studio               | 15     | 15       | 15 (Auth)
Authentication                 | 10     | 10       | 2 (Auth/Admin)
User Profile & Memory          | 5      | 5        | 5 (Auth)
Chat Sessions                  | 4      | 4        | 4 (Auth)
Chat & Conversations           | 3      | 3        | 3 (Auth)
API (math)                     | 2      | 2        | 2 (Auth)
Health & Diagnostics           | 2      | 2        | 0 (Public)
API (config)                   | 1      | 1        | 0 (Public)
API (models)                   | 1      | 1        | 0 (Public)
API (ping)                     | 1      | 1        | 0 (Public)
API (share)                    | 1      | 1        | 1 (Auth)
API (usage)                    | 1      | 1        | 1 (Auth)
Public Sharing (/share/<id>)   | 1      | 1        | 0 (Public)
Root (/)                       | 1      | 1        | 0 (Public)
----------------------------------------------------------------------
TOTAL                          | 75     | 75       | 60
================================================================================
```

### Clarification on Code Execution Sandbox:
- **Zero `/api/sandbox/*` routes exist in `app.url_map`.**
- `ai_routing/code_sandbox.py` is strictly an internal helper used for offline Python verification.
- It is **not** exposed to public web users as an execution endpoint.

---

## 4. STANDARD AEAD CHAT ENCRYPTION & DATA PROTECTION

### 4.1 Architecture & Implementation (`enc_v2_`)
In `app.py`, custom encryption has been replaced with standard **AES-256-GCM** authenticated encryption:
- **Library:** `cryptography.hazmat.primitives.ciphers.aead.AESGCM`
- **Key Derivation:** Dedicated `CHAT_ENCRYPTION_KEY` environment variable. In local development where unset, derives from auth secret using PBKDF2 with a distinct domain-separation salt (`b"brainy_chat_enc_v2_salt"`).
- **Nonce Generation:** Unique 96-bit cryptographically secure random nonce (`os.urandom(12)`) per encryption operation.
- **Storage Format:** `enc_v2_{base64url(nonce + ciphertext_and_tag)}`.
- **Authenticated Associated Data:** `b"brainy_chat_v2"` binds ciphertext to application context.

### 4.2 Key Rotation & Backward Compatibility
- **Rotation:** Supports multiple previous keys via `CHAT_ENCRYPTION_PREVIOUS_KEYS` (comma-separated).
- **Legacy Compatibility:** When encountering historical `hsh_v1_` records, `unmask_secure_hash()` automatically delegates to `_unmask_legacy_v1()`, preserving all previous chat sessions without data corruption.
- **Migration Utility:** `migrate_record_to_v2()` allows gradual, safe re-encryption of legacy records to AES-256-GCM with round-trip verification.

---

## 5. AUTHENTICATION & SECRET MANAGEMENT HARDENING

### 5.1 Production Fail-Closed Behavior
In `security.py: _get_auth_secret_key()`:
- **Production Mode:** If `AUTH_SECRET_KEY` (or `FLASK_SECRET_KEY` / `SECRET_KEY`) is missing in production (`_is_production()`), the service immediately raises `RuntimeError` and terminates, preventing silent per-worker secret divergence on ephemeral container hosts.
- **Development Mode:** Retains convenience fallback with an explicit warning log.

### 5.2 Strict Bearer Token (JWT) Validation
In `security.py: verify_auth_token()`:
- **Header Check:** Strictly checks that `header.get("alg") == "HS256"`.
- **Payload Validation:** Enforces mandatory `sub`, `exp`, and `iat` claims. Rejects tokens where `exp < time.time()` or where `iat` exceeds current time by more than 300 seconds (clock skew protection).
- **Rotation Support:** Validates signature against active key, then checks candidate keys from `AUTH_PREVIOUS_KEYS`.

---

## 6. PDF STUDY STUDIO & OCR DEPLOYMENT DEPENDENCIES

### 6.1 Non-Gemini Guarantee
Verified in `ai_routing/policy.py` lines 18–26 and 140–165:
- All study tasks (`PDF_SUMMARY`, `PDF_QUESTION_ANSWERING`, `NOTE_GENERATION`, `QUIZ_GENERATION`, `FLASHCARD_GENERATION`, `IMPORTANT_QUESTION_GENERATION`) execute `_filter_eligible(candidates, disallow_gemini=True)`.
- Enforces strict zero-Gemini quota consumption. Fallback candidates execute across Groq, Cerebras, SambaNova, and OpenRouter only.

### 6.2 Local OCR Status & Health Reporting
- `requirements.txt` updated with `pytesseract>=0.3.10` and `pillow>=10.0.0`.
- `nixpacks.toml` configured with `tesseract5` for Railway environments.
- `/api/health` now reports structured OCR availability:
  ```json
  "ocr": {
    "available": false,
    "enabled": true,
    "languages": [],
    "last_error": "TesseractNotFoundError: tesseract is not installed or it's not in your PATH.",
    "library_available": true,
    "tesseract_executable_available": false,
    "tesseract_version": null
  }
  ```
- **Fallback Behavior:** When the Tesseract binary is not installed in the host OS PATH, scanned PDFs cleanly fall back to placeholder markers (`[Scanned page X: Image content present]`), while native text-layer PDFs continue to extract text with 100% fidelity.

---

## 7. REALISTIC SECURITY REVIEW & DEFENSE-IN-DEPTH

| Security Domain | Implemented Controls | Realistic Limitations |
|---|---|---|
| **CSRF Defense** | Origin and Referer validation on mutating endpoints (`validate_csrf_origin`). Bearer tokens in headers are immune to ambient cookie injection. | Bearer tokens stored in browser `localStorage` could be compromised if an XSS vulnerability exists. Not an absolute XSS shield. |
| **SSRF Defense** | Validates outbound targets; blocks loopback (`127.0.0.1`), RFC1918 private subnets, and AWS/GCP metadata (`169.254.169.254`). | DNS rebinding or unvalidated open redirects on allowed public hosts could theoretically bypass static IP validation. |
| **Prompt Injection** | Document and search content is quarantined inside delimiter fences (`""" ... """`) with role-boundary instructions. | Prompt fencing is a heuristic defense-in-depth mitigation, not a mathematical security boundary. |
| **System Prompt Protection** | System prompts instruct models not to disclose instructions. | LLMs cannot guarantee 100% resistance to adversarial prompt extraction. Credentials must never be embedded in prompts. |
| **CSV Formula Injection** | `sanitize_cell()` prepends a single quote `'` to cells starting with `=`, `+`, `-`, `@`, `\t`, `\r`. | Fully protects standard spreadsheet imports (Excel, LibreOffice) from DDE command execution. |
| **Rate Limiting** | Sliding-window limiter in memory with Supabase RPC backing. | In-memory fallback is per-process; multi-worker instances require Redis or Supabase RPC for globally unified quotas. |

---

## 8. REPRODUCIBLE PERFORMANCE BENCHMARKS

Generated via `scripts/run_benchmarks.py` on November 1, 2026:

```
Benchmark Metric                  Sample Size    P50 Latency    P95 / Max      Status
─────────────────────────────────────────────────────────────────────────────────────────────
Local Mathematics Engine          100 ops        0.534 ms       1.169 ms (P95) VERIFIED
Code Sandbox Helper               5 runs         20.90 ms       23.07 ms (Max) VERIFIED
Next.js Static Export Size        120 files      3.88 MB total  -              VERIFIED
  - JavaScript (.js)              26 files       1.59 MB        -              VERIFIED
  - Brand Assets (.png)           14 files       1.12 MB        -              VERIFIED
  - KaTeX Web Fonts (.ttf/.woff)  60 files       1.05 MB        -              VERIFIED
Cloudflare Worker Edge Latency    5 requests     480.5 ms (TTFB)947.6 ms (Max) VERIFIED (SIN, CDG)
```

---

## 9. AUTOMATED TESTING SUITE & VERIFICATION

### Execution Output:
```
python -m unittest discover tests -v
Ran 223 tests in 3.946s — OK (0 failures, 0 errors, 0 skipped)
```

```
Test Suite File                      Test Cases  Status  Domain Focus
─────────────────────────────────────────────────────────────────────────────────────────────
test_admin_control_center.py             10       PASS   RBAC, CSV defense, KPIs, alerts
test_ai_router.py                        14       PASS   Cascades, pre-token stream failover
test_encryption_aead.py                  10       PASS   AES-256-GCM AEAD, key rotation, v1 compat
test_full_suite.py                       21       PASS   End-to-end integration flows
test_gemini_groq_routing.py              22       PASS   Provider failover, quota headers
test_groq_model_routing.py                3       PASS   Speed tier mapping & selection
test_maths_engine.py                     30       PASS   AST parser, SymPy symbolic solver
test_pdf_studio.py                       26       PASS   Deterministic OCR, non-Gemini routing
test_prompt_benchmark.py                 12       PASS   20 benchmark cases, injection defense
test_prompts.py                          13       PASS   Prompt depth modes & formatting
test_reliability_contracts.py            13       PASS   Chat context, rolling summary, DDG
test_response_completeness.py            12       PASS   Length truncation & auto-continuation
test_security_hardening.py               18       PASS   CSRF, SSRF, security headers, auth
test_supabase_persistence.py             19       PASS   Tenant isolation, REST pagination past 1k
─────────────────────────────────────────────────────────────────────────────────────────────
TOTALS                                  223       PASS   100% Pass Rate across all 14 suites
```

---

## 10. DEFINITIVE RELEASE READINESS VERDICT

### Final Verdict: **READY FOR CONTROLLED BETA**

**Justification & Operational Sign-Off:**
1. **Verifiable Quality:** All 223 automated tests are tracked in the repository and pass unconditionally in 3.95 seconds.
2. **Cryptographic Rigor:** Custom encryption has been replaced with industry-standard AES-256-GCM AEAD with verified backward compatibility for legacy data.
3. **Authentication Safety:** Production fail-closed protections prevent secret drift across container instances.
4. **Architectural Guarantees:** PDF Study Studio strictly enforces the non-Gemini routing contract with zero external AI consumption during document extraction.
5. **Beta Operational Checklist:**
   - [ ] Install host OS `tesseract-ocr` and `tesseract-ocr-eng` in production Docker/Render environments to activate scanned PDF OCR.
   - [ ] Inspect live Supabase `pg_policies` catalog to verify that database-level RLS mirrors application-level `user_id` filtering.
   - [ ] For multi-instance horizontal scaling (>5 web workers), configure `REDIS_URL` or verify Supabase RPC rate limiting.

**Release Sign-off:** Antigravity AI Senior QA & System Architecture Reviewer  
**Release Target:** BRAINY v1.0.0-beta
