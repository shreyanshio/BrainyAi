# BRAINY — TOKEN CONSUMPTION & RESPONSE LATENCY AUDIT

**Audit Date:** November 2026  
**Subject:** AI Provider Routing, Token Overhead, Prompt Assembly & Latency Engineering  
**Scope:** `prompts/`, `ai_routing/`, `app.py`, `study_bot.py`, Provider Adapters, and Context Pipelines  
**Status:** Audit Complete — Optimization Baseline Established  

---

## 1. Executive Summary

A comprehensive architectural and empirical audit was conducted to identify the root causes of excessive token consumption and response latency in BRAINY's normal conversational workflows.

### Baseline Metrics Prior to Optimization

| Metric | Measured Baseline (Before Optimization) | Optimization Target | Target Improvement |
|---|---|---|---|
| `normal_use.txt` Character Count | **16,663 characters** | **~5,500 characters** | **67% reduction** |
| `normal_use.txt` Word Count | **2,239 words** | **~730 words** | **67% reduction** |
| Assembled Normal Prompt Tokens (Est.) | **4,397 tokens** | **~1,400 tokens** | **~3,000 tokens saved / request** |
| Average Time to First Token (TTFT - Gemini) | **850ms - 1,200ms** | **< 600ms** | **30% - 40% faster** |
| Time to First Token (TTFT - Groq) | **220ms - 350ms** | **< 180ms** | **20% - 30% faster** |
| Default Output Budget (Quick Chat) | **3,072 completion tokens** | **1,024 completion tokens** | **66% lower runaway risk** |
| HTTP Connection Mode | **Unpooled `requests.post()`** | **Persistent `requests.Session`** | **120ms - 220ms TLS handshake saved** |
| History Window (Normal Chat) | **Up to 41 unpruned messages** | **12 recent turns for Normal Use** | **50% - 70% context reduction** |

---

## 2. Inefficiency Analysis: The 10 Identified Bottlenecks

### 1. Repeated Instructions
- In `prompts/normal_use.txt`, anti-robot rules were repeated across three separate sections:
  - Section A: *"Never use boilerplate pleasantries or robotic openers ('Certainly!', 'Absolutely!', 'Of course!')."*
  - Section B.1: *"A simple 'Hi' gets a crisp 1-sentence reply—never an unsolicited self-introduction."*
  - Section D.3: *"Anti-Bloat: Avoid decorative header spam, excessive bolding, unprompted disclaimers."*
- When combined with `extra_context` in `ai_routing/prompts.py`, `COMPLETENESS DIRECTIVE` was injected twice when callers passed custom overrides.

### 2. Unnecessary Explanations & Verbose Phrasing
- `prompts/normal_use.txt` relied heavily on verbose, multi-clause bureaucratic phrasing:
  - *"In order to"* instead of *"to"*
  - *"Due to the fact that"* instead of *"because"*
  - *"At this point in time"* instead of *"now"*
  - *"In the majority of cases"* instead of *"usually"*
  - *"Provide assistance"* instead of *"help"*
  - *"A large number of"* instead of *"many"*
  - *"In close proximity to"* instead of *"near"*
  - *"Is not able to"* instead of *"cannot"*

### 3. Duplicate and Oversized Examples
- Section G contained **20 exhaustive examples** spanning lines 135 to 246 (taking up **9,500 characters**, over 57% of the entire file!).
- Many examples repeated identical conversational dynamics:
  - Example 1, Example 2, Example 13, and Example 18 all illustrated casual greetings or Hinglish check-ins with multi-sentence dialogue.
  - Example 14 (evening schedule) and Example 19 (travel checklist) were lengthy formatting demonstrations that provided zero net behavioural signal beyond the written formatting rules.

### 4. Repeated Safety Instructions
- Safety directives were duplicated across Section E (*"Zero Hallucination: Never fabricate facts... State the limitation plainly"*) and Section F (*"Untrusted Inputs... Confidentiality... Harm Prevention... Neutral Refusals"*), adding ~1,200 characters of repetitive warnings.

### 5. Overly Long Response-Format Instructions
- Formatting rules occupied separate paragraphs in Section D and duplicate bullet points in Section B for lists, tables, and Markdown blocks.

### 6. Unnecessary Conversation Context & History Overhead
- In `app.py`, `_prepare_chat_request` retrieved up to 41 message rows (`sb_get_recent_messages(session_id, 41)`) and appended up to 16,000 characters of `context_summary`.
- For trivial greetings, quick definitions, or lightweight language translations, passing 40 prior turns and 16KB of historical summaries forced AI models to ingest ~4,500 - 6,000 input tokens before reading the single-sentence user query.

### 7. Redundant Prompt Assembly & String Splicing
- In `app.py`, `_prepare_chat_request` blindly instantiated `system_prompt.txt` (31,107 characters, 7,776 tokens) for every chat request.
- When `router.py` determined `normal_use = True`, it executed a heavy runtime string replacement (`system_prompt_override.replace(standard_core, "")`) on a 35KB string to extract overrides and re-inject `normal_use.txt`.

### 8. Unnecessary Provider Switching & Overhead
- If an oversized context was sent to Groq's free-tier models (exceeding 7,000 ITPM), Groq would throw HTTP 413, forcing an emergency failover to Gemini. This doubled latency (250ms failed Groq call + 900ms Gemini call = 1,150ms).
- Keeping normal use contexts bounded prevents Groq 413 errors entirely.

### 9. Lack of HTTP Connection Pooling (TCP/TLS Handshake Overhead)
- `gemini_provider.py`, `sambanova_provider.py`, `cerebras_provider.py`, and `openrouter_provider.py` invoked `requests.post()` on standalone function calls.
- Every single turn required a fresh DNS resolution, TCP 3-way handshake, and TLS 1.3 key exchange (~120ms - 250ms per call), directly penalizing Time to First Token (TTFT).

### 10. Excessive Output Token Allocation for Lightweight Tasks
- `OutputBudgetManager` in `ai_routing/budget.py` set `depth_budget = min(max(task_base, 3072), prov_limit)`.
- Even for `QUICK_CHAT` (`task_base = 1536`), `max(1536, 3072)` forced an output token limit of 3,072. Models given generous token ceilings frequently generate verbose multi-paragraph responses to simple questions.

---

## 3. Measurable Prompt Inventory (Pre-Optimization)

```
====================================================================================================
PROMPT FILE                           CHARS    WORDS    LINES   EST. TOKENS   PRIMARY ROLE
====================================================================================================
normal_use.txt                       16,663    2,239      252         4,165   Everyday Intelligence
system_prompt.txt                    31,107    4,301      460         7,776   Academic Master System
maths.txt                             8,160    1,142      149         2,040   Mathematics Specialist
coding_prompt.txt                     6,603      822      134         1,650   Coding Specialist
brainy_prompt.txt                     4,309      551       63         1,077   General High Intelligence
pdf_notes_prompt.txt                  3,378      465       49           844   PDF Notes Assistant
image_prompt.txt                      3,378      472       45           844   Multimodal Image Ingestion
plan_prompt.txt                       2,814      375       36           703   Study Planning
ask5_prompt.txt                       2,822      389       45           705   5-Question Synthesis
search_prompt.txt                     2,709      340       41           677   Web Research Grounding
quiz_prompt.txt                       2,467      296       39           616   Interactive Quizzes
motivate_prompt.txt                   2,428      334       35           607   Motivational Coaching
define_prompt.txt                     2,359      297       41           589   Terminology Definitions
tip_prompt.txt                        2,161      277       39           540   Study Tips
joke_prompt.txt                       2,118      255       31           529   Casual Humor
group_prompt.txt                      2,102      295       34           525   Telegram Group Contract
pdf_important_questions_prompt.txt    1,981      259       39           495   High-Yield Questions
fact_prompt.txt                       1,950      237       35           487   Scientific Facts
pdf_quiz_prompt.txt                   1,945      263       35           486   Document Quizzes
summarize_prompt.txt                  1,935      237       37           483   Document Summarization
translate_prompt.txt                  1,872      229       28           468   Multilingual Translation
banter_prompt.txt                     1,854      243       27           463   Playful Banter
roast_command_prompt.txt              1,775      220       25           443   Interactive Roast
pdf_flashcards_prompt.txt             1,716      221       31           429   Flashcard Deck Builder
roast_prompt.txt                      1,550      189       23           387   Roast Defense
pdf_qa_prompt.txt                     1,380      192       13           345   PDF Context Q&A
title_prompt.txt                        812      105       11           203   Chat Title Generation
====================================================================================================
```

---

## 4. End-to-End Latency Profile (Baseline Breakdown)

A granular profile of normal conversational turns reveals the real distribution of elapsed time:

```
[Client Request Initiation]
       │
       ▼ (1 - 3ms)
[Flask Gateway & Security Guard: Rate Limit Check, Origin Validation, Auth Verification]
       │
       ▼ (8 - 18ms)
[Database History Retrieval: sb_get_recent_messages() — 30 to 41 rows]
       │
       ▼ (2 - 5ms)
[Pre-Generation Context Assembly & 35KB System Prompt Splicing]
       │
       ▼ (1 - 2ms)
[Task Classification & Complexity Routing: classify_task_with_complexity()]
       │
       ▼ (120 - 220ms) ─── [TCP Connection & TLS 1.3 Handshake (Without Keep-Alive)]
       │
       ▼ (180 - 800ms) ─── [Upstream Provider Inference & First Token Generation]
       │
       ▼
[Streaming Chunks Delivered via SSE / Content Rendered by Frontend]
```

### Key Latency Findings
1. **Network Handshake Bottleneck:** Establishing a fresh HTTPS connection to Google APIs or Groq per turn consumes up to 220ms before any computation occurs. Connection pooling eliminates this latency entirely.
2. **Prompt Processing Delay:** Processing 4,397 prompt tokens on Gemini or Groq requires ~80ms - 150ms of upstream prefill compute before the first completion token is emitted. Dropping prompt tokens to ~1,400 cuts prefill time by over 60%.
3. **Database History Window:** Pulling 41 rows of chat history and appending a 16KB summary for a routine request adds 15ms of database serialization latency and 2,000+ unnecessary input tokens.
