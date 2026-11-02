# BrainyAi Intent Understanding & Knowledge Base System

## Overview

The `ai_routing/intent` system provides a structured, file-based natural language understanding layer for Brainy.
It decouples **Topic** (what the subject is), **Intent** (what the user wants Brainy to do), **Context** (what previous entities the user references), and **Constraints** (formatting, language, or search boundaries).

---

## File Architecture

| File | Purpose |
|---|---|
| `intent_catalog.yaml` | Master taxonomy of supported user intentions, capabilities, default workflows, and search policies. |
| `phrase_dictionary.yaml` | Multi-signal phrase dictionary mapping expressions, synonyms, signals, and negative signals to intentions. |
| `domain_glossary.yaml` | Categorized domain vocabulary (ML, CS, DSA, Math, Science, Web) separating Topic, Action, Tool, and Output terms. |
| `contextual_rules.yaml` | Pronoun resolution ("it", "that"), elliptical follow-up rules ("make it shorter"), and topic shift detection. |
| `routing_mapping.yaml` | Deterministic mapping from Intent ID to Brainy Workflow, Prompt Registry ID, Provider/Model priority, and execution path. |
| `multilingual_aliases.yaml` | Phrasing patterns and aliases across English, Hinglish, Hindi (Devanagari), and Gujarati. |
| `intent_examples.yaml` | Benchmarking and evaluation dataset with 100+ varied ground-truth user requests. |
| `confidence_policy.yaml` | Evidence-based scoring thresholds, signal weights, and ambiguity handling policies. |
| `intent_schema.py` | Strongly-typed dataclass models (`IntentResolutionResult`, `UserIntentRequest`, `TaskIntentItem`). |
| `intent_resolver.py` | Central deterministic resolver engine featuring sub-millisecond in-memory caching and mtime checks. |

---

## Separation of Concerns

```text
User Request: "Explain Dijkstra algorithm, show Python code, but keep it short without searching"
┌────────────────────────────────────────────────────────────────────────┐
│ TOPIC:       "dijkstra" (Category: computer_science_dsa)               │
│ INTENT:      Primary: "explain_concept" | Secondary: "generate_code"   │
│ CONSTRAINTS: ["no_web_search", "concise", "language:python"]           │
│ WORKFLOW:    "coding" (Primary Model: gemini-3.8-flash)                │
│ PROMPT:      "coding_prompt.txt"                                       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## How to Add a New Intent

1. **Register in `intent_catalog.yaml`**:
   Add an entry with `id`, `name`, `category`, `description`, `expected_output`, `capabilities`, `default_workflow`, and `search_policy`.
2. **Add Key Phrases in `phrase_dictionary.yaml`**:
   Add common natural language phrases, positive signals, and negative signals.
3. **Map to Runtime in `routing_mapping.yaml`**:
   Define `workflow`, `prompt_id` (matching `prompts/prompt_registry.yaml`), `primary_provider`, `primary_model`, and `is_fast_path`.
4. **Add Multilingual Phrases in `multilingual_aliases.yaml`** (if applicable):
   Add Hinglish, Hindi, or Gujarati triggers.
5. **Add Benchmark Test in `intent_examples.yaml`**:
   Include positive and negative examples and run `python ai_routing/intent/evaluate_intents.py`.
