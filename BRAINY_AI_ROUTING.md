# Brainy AI Routing & Two-Path Request Architecture Specification

**Status:** Production Ready & Operational  
**Modules:** `ai_routing/workflow_router.py`, `ai_routing/policy.py`, `ai_routing/tasks.py`, `ai_routing/router.py`  
**Primary Engine:** Google Gemini (`gemini-3.8-flash`, `gemini-3.5-flash-lite`)  
**Secondary Fallback:** Groq (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`)  

---

## 1. Architectural Philosophy: Fast Path vs Deep Path

Brainy enforces an intelligent separation of requests to avoid running complex, expensive pipelines for lightweight interactions:

```
                            +------------------------+
                            | User Incoming Message  |
                            +-----------+------------+
                                        |
                                        v
                            +------------------------+
                            | Workflow Router Check  |
                            | (Deterministic Regex)  |
                            +-----------+------------+
                                        |
                    +-------------------+-------------------+
                    |                                       |
                    v                                       v
         [ FAST PATH PIPELINE ]                  [ DEEP PATH PIPELINE ]
  - Greetings & Casual Chat               - Explicit Web Research (Tavily+DDG)
  - Short Definitions (<= 6 words)        - Breaking News & Verification
  - Simple Calculations                   - PDF Studio Workflows
  - Straightforward Code Explanations     - Multi-turn Academic Pedagogy
                    |                                       |
  - History Limit: 8 messages             - History Limit: 20 messages + Summary
  - Prompt: normal_use.txt                - Prompt: Task Specialist Prompt
  - Model: gemini-3.5-flash-lite          - Model: gemini-3.8-flash
  - Output Budget: 512-1024 tokens        - Output Budget: 2048-4096 tokens
  - Streaming Start: < 30 ms              - Streaming Start: Immediate Stage Event
                    |                                       |
                    +-------------------+-------------------+
                                        |
                                        v
                            +------------------------+
                            |  LLM Generation Stream |
                            +------------------------+
```

---

## 2. Deterministic Routing Rules & Workflow Taxonomy

| Workflow ID | Path Type | Trigger Conditions | Prompt Asset | Primary Model | Fallback Model | Output Cap |
|-------------|-----------|--------------------|--------------|---------------|----------------|------------|
| `normal_chat` | **FAST** | Greetings, conversational banter, definitions <= 6 words | `prompts/normal_use.txt` | `gemini-3.5-flash-lite` | `llama-3.1-8b-instant` | 512 tok |
| `mathematics` | **FAST** | Mathematical equations, arithmetic, derivations | `prompts/maths.txt` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 1,500 tok |
| `coding` | **FAST** | Code syntax, debugging, algorithms, functions | `prompts/coding_prompt.txt` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 2,048 tok |
| `educational` | **DEEP** | Foundational STEM topics, pedagogy, chapter study | `prompts/brainy_prompt.txt` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 2,048 tok |
| `web_search` | **DEEP** | Temporal anchors, recent news, domain legitimacy | `prompts/web_search.txt` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 1,500 tok |
| `coding_search` | **DEEP** | Cutting-edge framework docs (e.g. React 19) | `prompts/coding_search.txt` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 2,048 tok |
| `pdf_qa` | **DEEP** | Document grounded Q&A with page citations | `prompts/qa_prompt.txt` | `gemini-2.5-flash` | `llama-3.3-70b-versatile` | 1,024 tok |
| `pdf_notes` | **DEEP** | Executive, standard, or detailed PDF notes | `prompts/pdf_notes_standard.txt` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 2,048 tok |
| `pdf_quiz` | **DEEP** | 5-10 question multiple-choice quiz from PDF | `prompts/quiz_generation.txt` | `gemini-3.8-flash` | `llama-3.3-70b-versatile` | 1,500 tok |
| `pdf_flashcards` | **DEEP**| High-yield term/definition flashcard extraction | `prompts/flashcard_generation.txt` | `gemini-3.8-flash` | `llama-3.1-8b-instant` | 1,200 tok |

---

## 3. Gemini-First Provider Policy

Brainy prioritizes Google Gemini across all operational workloads:

1. **Gemini Primary:**
   - `gemini-3.8-flash`: Serves as the primary engine for educational depth, mathematics, coding, PDF studio, and search synthesis.
   - `gemini-3.5-flash-lite`: Serves as the primary workhorse for Fast-Path normal chat, delivering TTFT under 250ms.
2. **Groq Fallback:**
   - Groq (`llama-3.3-70b-versatile` and `llama-3.1-8b-instant`) is reserved strictly as an **LLM fallback** when Gemini encounters recoverable errors (HTTP 429 quota exhaustion, connection reset, or socket timeout).
   - Groq is **NEVER** used as a replacement search engine or default primary provider.
3. **Transparent Health Tracking & Failover:**
   - Candidate failover occurs before output tokens are emitted, preserving stream integrity.
   - Provider health scores are tracked across rolling 60-second windows. If Gemini encounters 3 consecutive failures, it is temporarily marked degraded for 60 seconds and traffic seamlessly shifts to Groq.
