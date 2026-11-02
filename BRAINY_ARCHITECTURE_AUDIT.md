# Brainy Architecture Audit & Request Lifecycle Specification

**Audit Date:** November 2026  
**Status:** Complete & Actionable  
**Target Repository:** Brainy (`https://github.com/shreyanshio/BrainyAi`)  
**Audited Stack:** Next.js 14 / TypeScript (Frontend), Python 3.12 Flask / Gunicorn (Backend), Supabase / PostgreSQL (Persistence), Google Gemini & Groq (AI Orchestration), Tavily & DuckDuckGo (Search), PyMuPDF (Local PDF Extraction).

---

## 1. Executive Architecture Overview

Brainy is an AI-powered study assistant and learning platform. Its full-stack architecture is composed of:

```
+-----------------------------------------------------------------------------------+
| FRONTEND LAYER (Next.js 14, React, Tailwind CSS, Cloudflare Workers / Static)      |
| - Components: Composer.tsx, MessageList.tsx, Sidebar, PDF Studio UI              |
| - Client Library: lib/api.ts (NDJSON streaming fetch, AbortSignal, Event Handling)|
+-----------------------------------------------------------------------------------+
                                         |  HTTPS / NDJSON Stream
                                         v
+-----------------------------------------------------------------------------------+
| BACKEND GATEWAY (Flask, Gunicorn, security.py, app.py)                            |
| - Authentication: Session JWT & In-Memory Handshake (sb_record_login)            |
| - Security Guard: Tenant Isolation, Rate Limiting, Input Sanitization, Anti-CSRF  |
| - Quota Controller: Atomic 30 msgs / 5 hrs per user (user_quotas table)           |
+-----------------------------------------------------------------------------------+
                                         |
         +-------------------------------+-------------------------------+
         |                                                               |
         v                                                               v
+------------------------------------+          +------------------------------------+
| FAST PATH PIPELINE                 |          | DEEP PATH PIPELINE                 |
| - Bounded Context (6-10 turns)     |          | - Multi-turn Context + Summary     |
| - Fast Gemini (gemini-3.5-lite)    |          | - Concurrent Search (Tavily+DDG)   |
| - Minimal Prompt (normal_use.txt)  |          | - PDF Chunks (PyMuPDF local page)  |
| - Direct Streaming (<400ms TTFT)   |          | - High Intelligence (Gemini 3.8)   |
+------------------------------------+          +------------------------------------+
         |                                                               |
         +-------------------------------+-------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| AI ORCHESTRATION & ROUTING ENGINE (ai_routing/)                                   |
| - Central Prompt Registry: 27 registered prompts, in-memory mtime cache           |
| - Central Workflow Router: Deterministic 11-scenario task & model classification   |
| - Provider Policy: Gemini Primary -> Groq Fallback -> OpenRouter Ancillary         |
| - Health Tracker: Rolling failure window, circuit breaker, single-project quota   |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| PERSISTENCE LAYER (Supabase REST API, PostgreSQL, In-Memory Dev Fallback)         |
| - Tables: chat_sessions, chat_messages (AEAD AES-256 encrypted), user_quotas,     |
|           user_memory, pdf_documents, pdf_pages, pdf_notes, pdf_quizzes           |
+-----------------------------------------------------------------------------------+
```

---

## 2. Complete Message Lifecycle Trace

Every user chat message undergoes an audited 16-stage execution journey:

```
[1. User Submission in Browser]
  └─ Composer.tsx captures text, validates length <= 12,000 chars, creates client-side temp message.
[2. Frontend Request Preparation]
  └─ lib/api.ts packages ChatSendRequest, attaches Bearer token, generates idempotency_key, initializes AbortController.
[3. Transport to Backend]
  └─ POST /api/chat/stream arrives at Flask gateway.
[4. Security & Guard Verification]
  └─ security.py verifies session cookie/bearer token, origin header against CSRF, and rate limits.
[5. Pre-Generation Pipeline (_prepare_chat_request)]
  ├─ Validates session_id against Supabase chat_sessions.
  ├─ Atomically consumes 1 message quota from user_quotas.
  ├─ Inserts user message to Supabase chat_messages.
  ├─ Fetches chat history context for active session.
  └─ Resolves user study profile and preferences.
[6. Workflow & Intent Classification]
  └─ workflow_router.py deterministically classifies query into Fast Path vs Deep Path workflow.
[7. Prompt Resolution]
  └─ prompt_resolver.resolve() loads base layer + specialist prompt from in-memory cache.
[8. Auxiliary Search Execution (Deep Path only)]
  └─ search_orchestrator.py dispatches concurrent Tavily (10s) and DuckDuckGo (8s) subqueries.
[9. Fenced Evidence Preparation]
  └─ Sanitizes snippets, applies SSRF checks, strips tracking params, wraps in untrusted boundary fence.
[10. Primary Provider Invocation]
  └─ Connects to Gemini (gemini-3.8-flash or gemini-3.5-flash-lite) with streaming enabled.
[11. Fallback Failover (if Gemini 429/timeout/5xx occurs)]
  └─ Rotates cleanly to Groq (llama-3.3-70b-versatile or llama-3.1-8b-instant) before token emission.
[12. Backend NDJSON Stream Generator]
  └─ Flushes chunks immediately with headers: Cache-Control: no-cache, X-Accel-Buffering: no.
[13. Browser Stream Reader]
  └─ lib/api.ts decodes NDJSON stream, dispatches onStart, onStatus, onDelta (30ms batches), onDone.
[14. Incremental UI Rendering]
  └─ MessageList.tsx dynamically parses Markdown code fences, LaTeX math formulas ($...$), and citations.
[15. Response Persistence & Auto-Titling]
  ├─ Full response saved to Supabase chat_messages (encrypted via AES-256-GCM enc_v2_).
  └─ If first turn of session, session title auto-generated from initial words.
[16. Telemetry & Analytics]
  └─ Records latency_ms (auth, context, ttft, generation, persistence), tokens, model, provider, search status.
```

---

## 3. AI Provider Call-Site Inventory

| Endpoint / Caller | File & Line | Workflow | Primary Provider | Fallback Provider | Prompt Used | Streaming? | Persistence? | Telemetry? |
|-------------------|-------------|----------|------------------|-------------------|-------------|------------|--------------|------------|
| `POST /api/chat/stream` | `app.py:2920` | Dynamic (`normal_chat`, `educational`, `math`, `coding`, `web_search`) | Gemini (`gemini-3.8-flash` / `3.5-lite`) | Groq (`llama-3.3-70b` / `3.1-8b`) | Dynamic via `PromptResolver` | **YES** (NDJSON) | **YES** (`chat_messages`) | **YES** (`chat_latency`) |
| `POST /api/chat/send` | `app.py:2804` | Dynamic | Gemini (`gemini-3.8-flash`) | Groq (`llama-3.3-70b`) | Dynamic via `PromptResolver` | NO (JSON) | **YES** (`chat_messages`) | **YES** (`ai_call`) |
| `POST /api/pdf/documents/<id>/ask` | `app.py:3741` | `pdf_qa` | Gemini (`gemini-2.5-flash` / `3.8`) | Groq (`llama-3.3-70b`) | `pdf_qa_prompt.txt` | NO (JSON) | **YES** (`pdf_qa_history`) | **YES** (`pdf_service`) |
| `POST /api/pdf/documents/<id>/notes` | `app.py:3700` | `pdf_notes` | Gemini (`gemini-3.8-flash`) | Groq (`llama-3.3-70b`) | `pdf_notes_standard.txt` | NO (JSON) | **YES** (`pdf_notes`) | **YES** (`notes_engine`) |
| `POST /api/pdf/documents/<id>/quiz` | `app.py:3772` | `pdf_quiz` | Gemini (`gemini-3.8-flash`) | Groq (`llama-3.3-70b`) | `quiz_generation.txt` | NO (JSON) | **YES** (`pdf_quizzes`) | **YES** (`quiz_engine`) |
| `POST /api/pdf/documents/<id>/questions/stream` | `app.py:3841` | `pdf_important_questions` | Gemini (`gemini-3.8-flash`) | Groq (`llama-3.3-70b`) | `important_questions.txt` | **YES** (SSE) | **YES** (`pdf_questions`) | **YES** (`pdf_service`) |
| `POST /api/pdf/documents/<id>/flashcards` | `app.py:3929` | `pdf_flashcards` | Gemini (`gemini-3.8-flash`) | Groq (`llama-3.1-8b`) | `flashcard_generation.txt` | NO (JSON) | **YES** (`pdf_flashcards`) | **YES** (`flashcard_engine`) |
| Telegram DM Handler | `study_bot.py:1650`| `telegram_chat` | Gemini (`gemini-3.5-lite`) | Groq (`llama-3.1-8b`) | `telegram_bot_prompt.txt` | NO (HTML) | **YES** (`user_memory`) | **YES** (`ai_telemetry`) |

---

## 4. Prompt Usage Inventory

The central repository defines 27 prompts registered in `prompts/prompt_registry.yaml` and resolved through `CentralPromptRegistry`:

- **Base Prompts:** `normal_use.txt` (lightweight high-efficiency base), `system_prompt.txt` (comprehensive general persona base).
- **Specialist Domain Prompts:** `coding_prompt.txt`, `coding_search.txt`, `maths.txt`, `educational_use.txt`, `brainy_prompt.txt`, `research_analysis.txt`, `step_by_step_explainer.txt`, `exam_revision.txt`.
- **Search Prompts:** `web_search.txt`, `citation_synthesis.txt`.
- **PDF Studio Prompts:** `document_grounded_qa.txt`, `qa_prompt.txt`, `summarize.txt`, `pdf_chat.txt`, `pdf_notes_standard.txt`, `pdf_notes_detailed.txt`, `pdf_notes_quick.txt`, `important_questions.txt`, `flashcard_generation.txt`, `quiz_generation.txt`, `ocr_cleanup.txt`.
- **Telegram Prompts:** `telegram_bot_prompt.txt`, `telegram_short_explainer.txt`, `telegram_quiz.txt`, `telegram_revision.txt`.

All prompts are cached in process memory with timestamp validation (`_mtimes`), avoiding redundant filesystem reads.

---

## 5. Identified Bottlenecks & Critical Latency Risks

During our codebase inspection, the following critical bottlenecks were uncovered:

1. **Unpooled Supabase HTTP Client (TLS Handshake Tax):**
   - In `app.py`, `_sb_request` used `requests.request()` directly without a persistent `requests.Session()`.
   - Result: Every REST query to Supabase initiated a separate TCP connection and TLS 1.3 handshake. With 5-7 queries per chat request (`sb_get_session`, `consume_user_quota`, `sb_insert_message`, `sb_get_recent_messages`, `load_user_into_memory`), **700ms to 1.5s was wasted on network handshakes alone**.

2. **Forced User Profile Re-fetching on Every Turn:**
   - In `app.py` line 2548, `study_bot.load_user_into_memory(..., refresh=True)` forced `refresh=True` on every single message.
   - Result: Synchronous `SELECT * FROM user_memory` fetched the entire historical chat array from the database on every turn, adding 150-250ms of blocking delay.

3. **Unbounded Context History Bloat:**
   - In `_prepare_chat_request`, the backend loaded 30 to 41 past messages (and if 41 returned, initiated an unbounded pagination loop `while True: ...`) for EVERY request, including simple greetings ("hi").
   - Result: Inflated prompt sizes from 350 tokens to 4,500+ tokens, slowing down LLM prefill time and consuming excessive token quotas.

4. **Search Execution Blocking Stream Header Dispatch:**
   - Web search was executed synchronously inside `_prepare_chat_request` before Flask returned the streaming `Response` object.
   - Result: The user's browser sat on a pending HTTP connection for 2.0+ seconds before seeing the first byte, rather than seeing an immediate `<50ms` "Searching..." stage indicator.

5. **Inverted Speed Tier Provider Priority:**
   - In `ai_routing/policy.py`, `TaskComplexity.FAST` and `TaskType.QUICK_CHAT` placed Groq ahead of Gemini, violating the Gemini-first directive for everyday interactions.

---

## 6. Recommended Implementation Sequence

1. **Implement HTTP Connection Pooling (`requests.Session` with keep-alive):** Eliminate the ~200ms per-query TLS handshake overhead for Supabase REST calls.
2. **Implement User Profile TTL Caching:** Remove `refresh=True` on every turn, caching user preferences in-memory for 120s.
3. **Implement Bounded Context Windows:** Cap history retrieval to 8 messages (4 turns) for Fast Path, avoiding full database history dumping.
4. **Implement Pre-Stream Header Dispatch & Deferred Search:** Flush initial NDJSON headers and status events immediately so TTFT is perceived instantly (<50ms).
5. **Realign Provider Hierarchy to Gemini-First:** Place `gemini-3.5-flash-lite` first for fast-path chats, preserving Groq strictly as the synthesis fallback.
