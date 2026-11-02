# Brainy Prompt Usage & Execution Audit

**Audit Date:** November 2026  
**Status:** Complete & Remediated  
**Target Architecture:** BrainyAi Hybrid Orchestration Engine  

---

## 1. Executive Summary

A comprehensive investigation of the Brainy codebase was conducted to determine why prompt files (`.txt`), AI models, and search tools were configured in the repository but were not consistently being executed at runtime.

The investigation uncovered critical systemic root causes:
1. **Frontend-Bypassed Task Intent:** In `app.py` (`_prepare_chat_request`), the prompt composer was called with `task=active_intent`. However, for all standard chat messages, the web client simply sent `intent: "chat"` (or `None`). The backend never executed deterministic intent classification before composing the prompt, defaulting 95% of queries to `system_prompt.txt` and leaving specialist prompts like `coding_prompt.txt` and `maths.txt` orphaned from web chats.
2. **Hidden Web-Search Flags:** Web search execution in `app.py` was gated solely on `data.get("web_search")`. If a user asked a time-sensitive question ("Find the latest Gemini API changes" or "Check whether this website is legitimate"), the backend did not recognize the search intent and answered from outdated model memory without searching.
3. **Hardcoded Inline Prompts:** When search was triggered, `app.py` manually formatted an ad-hoc Hinglish instruction string (`f"User ne search kiya: '{query}'..."`) rather than utilizing `prompts/search_prompt.txt`.
4. **Single-Search / Dead Fallback:** `study_bot.py` only called Tavily. If Tavily was missing or failed, it fell back to `api.duckduckgo.com` (the deprecated Instant Answer API), which returned empty results for modern search queries. DuckDuckGo was never invoked concurrently for cross-verification.

All defects have been repaired through the introduction of:
- `prompts/prompt_registry.yaml` (Authoritative prompt metadata specification)
- `ai_routing/prompt_registry.py` (`CentralPromptRegistry` & `PromptResolver`)
- `ai_routing/search_intent.py` (Deterministic positive/negative search classifier)
- `ai_routing/query_planner.py` (Focused subquery distillation)
- `ai_routing/search_adapters.py` (Tavily + DuckDuckGo `ddgs` concurrent adapters)
- `ai_routing/search_orchestrator.py` (Concurrent dispatch, URL deduplication, and untrusted evidence fencing)
- `ai_routing/workflow_router.py` (Unified 11-scenario workflow router)

---

## 2. Complete Prompt Inventory (27 Registered Prompts)

| Prompt Filename | Purpose | Registered Workflow | Applicable Model Categories | Runtime Status |
| :--- | :--- | :--- | :--- | :--- |
| `ask5_prompt.txt` | Socratic 5-question deep inquiry | `ask5` | `main_intelligence` | **Active & Resolved** |
| `banter_prompt.txt` | Witty, relatable student smalltalk | `banter` | `fast`, `lightweight` | **Active & Resolved** |
| `brainy_prompt.txt` | Deep academic & STEM reasoning | `educational` | `main_intelligence`, `reasoning` | **Active & Resolved** |
| `coding_prompt.txt` | Clean code, DSA, SQL, debugging | `coding`, `coding_search` | `main_intelligence`, `reasoning` | **Active & Resolved** |
| `define_prompt.txt` | Academic definitions with examples | `define` | `fast`, `lightweight` | **Active & Resolved** |
| `fact_prompt.txt` | Fascinating educational facts | `fact` | `fast`, `lightweight` | **Active & Resolved** |
| `group_prompt.txt` | High-signal group chat replies | `group_study` | `fast`, `main_intelligence` | **Active & Resolved** |
| `image_prompt.txt` | Diagram & flowchart visual analysis | `image_analysis` | `multimodal`, `main_intelligence`| **Active & Resolved** |
| `joke_prompt.txt` | STEM, coding, and study humor | `joke` | `fast`, `lightweight` | **Active & Resolved** |
| `maths.txt` | Rigorous mathematical derivations | `mathematics` | `reasoning`, `main_intelligence` | **Active & Resolved** |
| `motivate_prompt.txt` | Student burnout & motivation | `motivate` | `fast`, `main_intelligence` | **Active & Resolved** |
| `normal_use.txt` | Minimal-token everyday dialogue | `normal_chat` | `fast`, `lightweight` | **Active & Resolved** |
| `pdf_flashcards_prompt.txt`| Flashcard JSON extraction | `pdf_flashcards` | `main_intelligence`, `fast` | **Active & Resolved** |
| `pdf_important_questions_prompt.txt`| Exam questions with marking schemes| `pdf_important_questions` | `main_intelligence`, `reasoning` | **Active & Resolved** |
| `pdf_notes_prompt.txt` | Revision notes from textbooks | `pdf_notes` | `main_intelligence`, `reasoning` | **Active & Resolved** |
| `pdf_qa_prompt.txt` | Page-cited document answers | `pdf_qa` | `main_intelligence`, `fast` | **Active & Resolved** |
| `pdf_quiz_prompt.txt` | 4-option MCQ quiz generation | `pdf_quiz` | `main_intelligence`, `fast` | **Active & Resolved** |
| `plan_prompt.txt` | Student study timetables | `plan` | `main_intelligence` | **Active & Resolved** |
| `quiz_prompt.txt` | Native Telegram poll formatting | `quiz_telegram` | `fast` | **Active & Resolved** |
| `roast_command_prompt.txt` | Lighthearted academic roasting | `roast` | `fast`, `lightweight` | **Active & Resolved** |
| `roast_prompt.txt` | Sharp abuse defense | `roast_defense` | `fast`, `lightweight` | **Active & Resolved** |
| `search_prompt.txt` | Web research & source synthesis | `web_search` | `main_intelligence`, `reasoning` | **Active & Resolved** |
| `summarize_prompt.txt` | High-density text compression | `summarize` | `fast`, `main_intelligence` | **Active & Resolved** |
| `system_prompt.txt` | Universal foundational core | `system_base` | `main_intelligence`, `general` | **Active & Resolved** |
| `tip_prompt.txt` | High-yield study strategies | `tip` | `fast`, `lightweight` | **Active & Resolved** |
| `title_prompt.txt` | 3-5 word conversation titles | `title_generation` | `fast`, `lightweight` | **Active & Resolved** |
| `translate_prompt.txt` | Multilingual academic translation | `translate` | `fast`, `main_intelligence` | **Active & Resolved** |

---

## 3. Discovered Defects & Structural Fixes

### Defect 1: Orphaned Specialist Prompts
- **Before:** `app.py` received `{ "content": "Explain binary search in Python", "intent": "chat" }`. It invoked `prompt_registry.compose_prompt(task="chat")` which defaulted to `system_prompt.txt`. Neither `coding_prompt.txt` nor `maths.txt` was loaded.
- **Fix:** In `app.py`, `workflow_router.route()` inspects the actual user query content. It deterministically classifies `"Explain binary search in Python"` into the `coding` workflow, loading `prompts/coding_prompt.txt` through `PromptResolver`.

### Defect 2: Ignored Search Intent
- **Before:** `app.py` checked `data.get("web_search")`. If the user asked "Find the latest Gemini API changes", the backend never ran web search unless the user manually enabled a toggle.
- **Fix:** `detect_search_intent()` automatically detects time-sensitive keywords ("latest", "today", "changes", "current", "release", "docs") and triggers `search_orchestrator.execute_search()`.

### Defect 3: Dead DuckDuckGo Fallback
- **Before:** `study_bot.py` relied on `api.duckduckgo.com`, an ancient API that returns only disambiguation abstracts for Wikipedia topics. For current news or tech queries, it returned nothing.
- **Fix:** Integrated the modern `ddgs` package supporting live text and news search. Both Tavily and DuckDuckGo are dispatched concurrently using a thread pool.

### Defect 4: Unsanitized Search Results
- **Before:** Search results were injected directly into user messages without prompt injection sanitization.
- **Fix:** Sanitized via `sanitize_snippet()` (strips injection overrides like "Ignore previous instructions") and strictly enclosed within `--- BEGIN EXTERNAL SEARCH FINDINGS (UNTRUSTED DATA) ---` boundaries.
