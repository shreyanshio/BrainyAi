# Brainy Central Prompt Registry & Assembly Specification

**Status:** Operational & Fully Tested  
**Registry Configuration:** `prompts/prompt_registry.yaml`  
**Resolver Engine:** `ai_routing/prompt_registry.py`  
**Total Assets:** 27 Production Prompt Files  

---

## 1. Registry Architecture & Resolution Flow

Brainy enforces a structured, two-tier prompt assembly model to eliminate prompt token bloat:

```
+-------------------------------------------------------------------------+
| BASE LAYER (Resolved from Task Complexity)                              |
| - Fast-Path: prompts/normal_use.txt (~120 tokens, zero fluff)           |
| - Deep-Path: prompts/system_prompt.txt (~600 tokens, comprehensive)     |
+-------------------------------------------------------------------------+
                                    +
+-------------------------------------------------------------------------+
| TASK-SPECIFIC SPECIALIST LAYER (Appended on demand)                     |
| e.g. prompts/coding_prompt.txt, prompts/maths.txt, etc.                 |
+-------------------------------------------------------------------------+
                                    +
+-------------------------------------------------------------------------+
| PLATFORM FORMATTING CONTRACT                                            |
| - Web UI:   Markdown + KaTeX Math ($...$, $$...$$) + Code Fences        |
| - Telegram: Clean text rules (No unsupported raw LaTeX, clean fences)   |
+-------------------------------------------------------------------------+
```

Every registered prompt in `prompts/prompt_registry.yaml` defines:
- `prompt_id`: Unique identifier (e.g. `coding`, `maths`, `web_search`).
- `file`: Path relative to `prompts/`.
- `workflow`: Primary bound workflow.
- `applicable_model_categories`: `[coding]`, `[reasoning]`, `[search_synthesis]`, `[lightweight]`.
- `trigger_intents`: Positive activation keywords.
- `excluded_intents`: Negative exclusion filters.
- `version`: Asset revision version.
- `enabled`: Boolean active toggle.

---

## 2. In-Memory Caching & Token Economics

- **Zero Disk Re-reads:** The `CentralPromptRegistry` maintains an internal `_content_cache: Dict[str, str]` keyed by prompt ID.
- **Timestamp Validation:** Prompt files are checked against `os.path.getmtime()`. Changes to prompt files on disk are automatically detected and reloaded without server restarts, while steady-state requests read directly from RAM (< 0.2ms resolution time).
- **No Prompt Token Dumping:** Unlike legacy architectures that concatenated all instructions into an 8,000-token system instruction, Brainy loads only the exact instructions required for the active turn, keeping base system prompts between **120 and 800 tokens**.

---

## 3. Observability & Telemetry

Every request logged by `ai_routing/telemetry.py` records:
- `prompt_id`: Exact prompt ID resolved.
- `workflow`: Bound execution workflow.
- `mode`: `"normal_use"` (Fast Path) or `"advanced"` (Deep Path).
- `selection_reason`: Why the specific prompt was resolved.
- `prompt_tokens_est`: Input token estimate.
