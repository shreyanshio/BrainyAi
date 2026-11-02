# Brainy Prompt Routing Matrix & Registry Specification

**Status:** Production Ready & Verified  
**Engine:** Central Prompt Registry (`ai_routing/prompt_registry.py`)  
**Registry Configuration:** `prompts/prompt_registry.yaml`  
**Total Registered Prompts:** 27  

---

## 1. Architectural Overview

Brainy employs a two-tier, zero-token-dump prompt assembly architecture. Rather than concatenating multiple broad prompts or dumping unused task instructions into every model call, the **Central Prompt Registry** resolves a minimal, highly targeted system instruction per request:

```
+-----------------------------------------------------------------------+
| BASE LAYER                                                            |
| - Standard/Lightweight: prompts/normal_use.txt (concise rules)        |
| - Complex/Fallback:     prompts/system_prompt.txt (full persona)      |
+-----------------------------------------------------------------------+
                                   +
+-----------------------------------------------------------------------+
| SPECIALIST TASK LAYER (Loaded on-demand if intent matches)            |
| e.g., prompts/coding_prompt.txt, maths.txt, web_search.txt, etc.      |
+-----------------------------------------------------------------------+
                                   +
+-----------------------------------------------------------------------+
| PLATFORM FORMATTING CONTRACT                                          |
| - Web UI:   Markdown + LaTeX math rules ($...$, $$...$$, code fences) |
| - Telegram: HTML/MarkdownV2 clean rules (no raw LaTeX, clean fences)   |
+-----------------------------------------------------------------------+
```

Every registered prompt in `prompts/prompt_registry.yaml` is validated at startup and bound to specific deterministic workflows and model categories.

---

## 2. Complete 27-Prompt Routing Matrix

| # | Prompt ID | Relative File Path | Workflow Binding | Primary Purpose | Trigger Intents / Keywords | Target Model Category | Platform Rules |
|---|-----------|-------------------|------------------|-----------------|----------------------------|-----------------------|----------------|
| 1 | `system_prompt` | `prompts/system_prompt.txt` | `normal_chat` | Core fallback persona & guidelines | Default fallback | `general` | Web Markdown / LaTeX |
| 2 | `normal_use` | `prompts/normal_use.txt` | `normal_chat` | High-efficiency concise chat | `chat`, `casual`, `greeting` | `lightweight` | Web Markdown / LaTeX |
| 3 | `brainy_prompt` | `prompts/brainy_prompt.txt` | `educational` | Educational persona with Hindi/Hinglish warmth | `learn`, `study`, `explain` | `reasoning` | Web Markdown / LaTeX |
| 4 | `educational_use` | `prompts/educational_use.txt` | `educational` | Structured pedagogy & explanations | `explain`, `concept`, `teach` | `reasoning` | Web Markdown / LaTeX |
| 5 | `coding_prompt` | `prompts/coding_prompt.txt` | `coding` | Clean, production-ready code generation | `code`, `debug`, `refactor`, `function` | `coding` | Markdown code fences |
| 6 | `coding_search` | `prompts/coding_search.txt` | `coding_search` | Modern framework & API code synthesis | `docs`, `api`, `sdk`, `react 19` | `coding` | Markdown code fences |
| 7 | `maths` | `prompts/maths.txt` | `mathematics` | Step-by-step mathematical problem solving | `solve`, `equation`, `calculate`, `integral` | `reasoning` | Strict LaTeX Math |
| 8 | `web_search` | `prompts/web_search.txt` | `web_search` | External evidence synthesis with citations | `search`, `latest`, `news`, `check` | `search_synthesis` | Citations + Markdown |
| 9 | `research_analysis` | `prompts/research_analysis.txt` | `deep_research` | Academic & comparative research | `compare`, `pros and cons`, `analyze` | `reasoning` | Markdown Tables |
| 10 | `quiz_generation` | `prompts/quiz_generation.txt` | `quiz` | Formatted multi-question academic quizzes | `quiz`, `test me`, `practice questions` | `reasoning` | Structured Markdown |
| 11 | `qa_prompt` | `prompts/qa_prompt.txt` | `pdf_qa` | Direct question answering on context | `pdf_qa`, `answer based on` | `reasoning` | Markdown |
| 12 | `document_grounded_qa` | `prompts/document_grounded_qa.txt` | `pdf_qa` | Strict citation-backed doc Q&A | `document_qa`, `from this pdf` | `reasoning` | Markdown + Citations |
| 13 | `summarize` | `prompts/summarize.txt` | `pdf_summary` | Executive summary of uploaded docs | `summary`, `summarize`, `brief` | `general` | Bulleted Markdown |
| 14 | `pdf_chat` | `prompts/pdf_chat.txt` | `pdf_chat` | Interactive multi-turn doc dialogue | `pdf_dialogue`, `ask about doc` | `general` | Web Markdown |
| 15 | `important_questions` | `prompts/important_questions.txt` | `pdf_important_questions` | High-yield exam question generation | `important questions`, `exam prep` | `reasoning` | Markdown Numbered |
| 16 | `flashcard_generation` | `prompts/flashcard_generation.txt` | `pdf_flashcards` | Front/Back flashcard pair generation | `flashcards`, `cards`, `anki` | `reasoning` | JSON / Delimited |
| 17 | `pdf_notes_standard` | `prompts/pdf_notes_standard.txt` | `pdf_notes` | Balanced revision notes from PDF | `notes`, `standard notes` | `general` | Sectioned Markdown |
| 18 | `pdf_notes_detailed` | `prompts/pdf_notes_detailed.txt` | `pdf_notes` | In-depth chapter summaries | `detailed notes`, `comprehensive` | `reasoning` | Sectioned Markdown |
| 19 | `pdf_notes_quick` | `prompts/pdf_notes_quick.txt` | `pdf_notes` | Rapid high-level bullet notes | `quick notes`, `cheat sheet` | `lightweight` | Bulleted Markdown |
| 20 | `exam_revision` | `prompts/exam_revision.txt` | `educational` | High-yield cram revision sheet | `exam revision`, `cram`, `last minute` | `reasoning` | High-density Markdown |
| 21 | `step_by_step_explainer` | `prompts/step_by_step_explainer.txt` | `educational` | Socratic step-by-step breakdown | `step by step`, `how it works` | `reasoning` | Numbered steps |
| 22 | `telegram_bot_prompt` | `prompts/telegram_bot_prompt.txt` | `telegram_chat` | Mobile Telegram persona (Hinglish) | `telegram_default` | `general` | Telegram Clean Rules |
| 23 | `telegram_short_explainer` | `prompts/telegram_short_explainer.txt` | `telegram_chat` | Ultra-concise mobile explanations | `telegram_short`, `batao` | `lightweight` | Telegram HTML/MDv2 |
| 24 | `telegram_quiz` | `prompts/telegram_quiz.txt` | `telegram_quiz` | Single-poll Telegram quiz questions | `telegram_quiz` | `lightweight` | Telegram Polling |
| 25 | `telegram_revision` | `prompts/telegram_revision.txt` | `telegram_chat` | Mobile-optimized bullet revision | `telegram_revision` | `lightweight` | Telegram Clean Rules |
| 26 | `ocr_cleanup` | `prompts/ocr_cleanup.txt` | `pdf_ocr` | OCR text repair & normalization | `ocr_cleanup`, `scanned` | `general` | Clean Plain Text |
| 27 | `citation_synthesis` | `prompts/citation_synthesis.txt` | `web_search` | Academic attribution formatting | `cite`, `verify references` | `search_synthesis` | Citations [1], [2] |

---

## 3. Dynamic Resolution Workflow

The `PromptResolver` in `ai_routing/prompt_registry.py` executes the following sequence:

1. **Input Normalization:** Strips conversational whitespace and determines the user's workflow intent via `WorkflowRouter`.
2. **Registry Lookup:** Finds the corresponding `PromptSpec` in `prompt_registry.yaml`.
3. **Base Layer Determination:** If the workflow is lightweight (`normal_chat`, basic queries), it selects `prompts/normal_use.txt`. If complex reasoning is required, it selects `prompts/system_prompt.txt`.
4. **Specialist Inclusion:** The specialist prompt text (e.g. `coding_prompt.txt`) is appended only if it is distinct from the base prompt.
5. **Platform Sanitation:** Appends rendering instructions (e.g. LaTeX delimiter instructions for web chat, or Unicode formatting rules for Telegram).
6. **Token Verification:** Measures prompt tokens to ensure total system prompt size remains under 600 tokens for standard requests, preventing context waste.

---

## 4. Verification and Regression Protections

- **Automated Registry Integrity Test:** `tests/test_search_orchestration_and_prompt_registry.py::TestSearchOrchestrationAndPromptRegistry::test_01_all_registry_prompts_exist_and_load` parses all 27 entries and verifies every file exists on disk, contains non-empty text, and resolves cleanly.
- **Fail-Safe Fallback:** If any prompt file is corrupted or unreadable, `PromptResolver` transparently falls back to an embedded production-safe system prompt without raising unhandled 500 exceptions.
