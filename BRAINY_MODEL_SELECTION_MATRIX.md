# Brainy Model Selection Matrix & Provider Policy

**Status:** Production Ready & Verified  
**Primary AI Engine:** Google Gemini (`gemini-3.8-flash`, `gemini-3.8-flash-lite`)  
**Secondary AI Fallback:** Groq (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`)  
**Ancillary Fallbacks:** Cerebras, OpenRouter, SambaNova  

---

## 1. Architectural Model Selection Policy

Brainy implements a strict, context-aware model routing policy designed to maximize response intelligence, reduce latency, and preserve free-tier quotas:

1. **Gemini 3.8 Flash is the Primary Workhorse:**
   - Handles all complex reasoning, educational pedagogy, mathematical derivations, code generation, and web search evidence synthesis.
   - Selected whenever high quality, structured outputs, or multi-lingual fluency is demanded.
2. **Gemini 3.8 Flash-Lite Handles Lightweight Chat:**
   - Selected for greetings, conversational banter, quick clarifying questions, and simple summaries.
   - Drastically cuts latency (<400ms time-to-first-token) and reduces token burn.
3. **Groq is Reserved Strictly as an LLM Fallback:**
   - Groq is **NEVER** used as a web search provider.
   - Groq models (`llama-3.3-70b-versatile` for reasoning, `llama-3.1-8b-instant` for lightweight chat) are invoked **only** when Gemini encounters rate limits (HTTP 429), connection resets, or network timeouts.
4. **No Artificial Search Substitution:**
   - Neither Gemini nor Groq may secretly replace Tavily or DuckDuckGo. The LLM only receives and synthesizes external search findings provided by the search orchestrator.

---

## 2. Model Selection Matrix by Workflow

| Workflow ID | Primary Model | Fallback Model | Output Token Budget | Search Required? | Primary Prompt File |
|-------------|---------------|----------------|---------------------|------------------|---------------------|
| `web_search` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 1,500 | **YES** (Tavily+DDG) | `prompts/web_search.txt` |
| `coding_search` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 2,048 | **YES** (Tavily+DDG) | `prompts/coding_search.txt` |
| `coding` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 2,048 | NO | `prompts/coding_prompt.txt` |
| `mathematics` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 1,500 | NO | `prompts/maths.txt` |
| `educational` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 1,500 | NO | `prompts/educational_use.txt` |
| `deep_research` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 2,500 | **YES** (Tavily+DDG) | `prompts/research_analysis.txt` |
| `normal_chat` | `gemini-3.8-flash-lite` | `llama-3.1-8b-instant` | 512 | NO | `prompts/normal_use.txt` |
| `pdf_notes` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 2,048 | NO | `prompts/pdf_notes_standard.txt` |
| `pdf_summary` | `gemini-3.8-flash` | `llama-3.1-8b-instant` | 1,024 | NO | `prompts/summarize.txt` |
| `pdf_qa` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 1,024 | NO | `prompts/document_grounded_qa.txt` |
| `pdf_flashcards`| `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 1,500 | NO | `prompts/flashcard_generation.txt` |
| `pdf_questions` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 1,500 | NO | `prompts/important_questions.txt` |
| `telegram_chat` | `gemini-3.8-flash-lite` | `llama-3.1-8b-instant` | 512 | Conditional | `prompts/telegram_bot_prompt.txt` |

---

## 3. Provider Failover & Health Tracking Architecture

The router tracks provider availability across rolling time windows via `ai_routing/provider_health.py`:

```
+-----------------------------------------------------------+
| Provider Call Attempt (e.g. gemini-3.8-flash)            |
+-----------------------------+-----------------------------+
                              |
                 [ Success / Failure Check ]
                              |
          +-------------------+-------------------+
          |                                       |
    (HTTP 200 OK)                           (HTTP 429/5xx/Timeout)
          |                                       |
          v                                       v
+--------------------+                 +--------------------+
| Health Score Boost |                 | Record Error Event |
| Reset error count  |                 | Consecutive Errs++ |
+--------------------+                 +----------+---------+
                                                  |
                                      [ Consecutive Errs >= 3 ]
                                                  |
                                                  v
                                       +--------------------+
                                       | Mark Provider Degraded
                                       | 60-second Cooldown |
                                       +----------+---------+
                                                  |
                                                  v
                                       +--------------------+
                                       | Dispatch to Fallback
                                       | (Groq / Cerebras)  |
                                       +--------------------+
```

### 3.1 Single-Project Quota Discipline
When Gemini returns HTTP 429:
- The system adheres strictly to project quota limits.
- It **never** attempts multi-account hopping or spoofed identities.
- It cleanly logs the rate-limit event with masked credentials (`mask_credential(key)`) and fails over directly to Groq.

### 3.2 Streaming Failover Mechanics
- **Pre-Token Failure:** If an upstream provider drops the connection before yielding its first token chunk, the stream generator catches the error, rotates immediately to the next candidate model, and streams from the beginning.
- **Mid-Token Error:** If a network interruption occurs after tokens have already been delivered to the client, the stream emits a clean terminal event with an informative retry hint rather than leaving the socket hanging.

---

## 4. Verification & Automated Tests

All routing permutations and failover boundaries are verified in `tests/test_advanced_orchestration.py` and `tests/test_search_orchestration_and_prompt_registry.py`:

1. **Deterministic Primary Routing:** Asserts that educational and coding requests always route to Gemini Flash.
2. **Deterministic Lightweight Routing:** Asserts that casual greetings route to Gemini Flash-Lite.
3. **Mocked Fallback Failover:** Asserts that when Gemini Flash is forced to fail (simulated 429/500), the orchestrator routes to Groq without crashing or altering prompt requirements.
4. **Prompt Registry Consistency:** Asserts that the model category requested by the router matches the model category defined in `prompt_registry.yaml`.
