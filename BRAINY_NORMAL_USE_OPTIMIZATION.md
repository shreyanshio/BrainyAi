# BRAINY Normal Use Optimization

## Implementation

- Added `prompts/normal_use.txt` with concise everyday response guidance and compact security and safety requirements.
- Integrated Normal Use into the existing `PromptRegistry` and `AIRouter`; no second router or classifier was introduced.
- FAST/LIGHT quick chat, short simple explanations, translations, and short writing/rewriting use the compact prompt and the existing registry-driven fast candidate chain. The local maths fast path remains first for computable arithmetic.
- Existing specialist and document routes retain their task prompts. PDF Study Studio's non-Gemini filter is unchanged. If `normal_use.txt` is missing, the composer safely uses the established full prompt.
- Existing provider fallback remains in place. If a provider fails after Normal Use selection, telemetry logs the failure-based escalation reason and fallback model. The original message list is passed unchanged to the next provider.
- Telemetry now records mode, selection reason, fallback/escalation reason, and estimated prompt-token size alongside existing provider, model, API-reported input/output tokens, total tokens, cost, and latency data. Prompt tokens are estimated as characters divided by four; API-reported input tokens remain provider totals. No message body is logged. The existing Supabase payload/schema is unchanged; new mode and reason dimensions are available in the in-process telemetry records and structured logs, and are not persisted as new Supabase columns.

## Routing behavior

| Request | Handling |
|---|---|
| Greetings, short definitions, simple questions, translation, rewriting | Normal Use prompt; configured Groq fast model is first via the current policy |
| Suitable arithmetic | Local maths engine; no provider call |
| Complex reasoning, coding, advanced math, science, specialist tasks | Existing advanced/specialist prompts and candidate policy |
| PDF Study Studio | Existing task prompts and strictly non-Gemini provider candidates |
| Fast provider unavailable | Existing fallback chain; failure-based escalation reason recorded |

The fast model is read from the existing `GROQ_MODEL_FAST` registry setting (default in this checkout: `llama-3.1-8b-instant`). Advanced routes use the existing registry-configured model IDs, including the Gemini reasoning/code/balanced models where the routing policy selects them. This implementation does not add model IDs or verify live provider availability; actual candidate filtering and availability remain controlled by the registry and provider layer.

## Prompt-size comparison

Measured locally by composing the existing and Normal Use quick-chat prompts for Web with the repository's configured templates:

| Prompt | Characters | Estimated tokens (characters ÷ 4) |
|---|---:|---:|
| Existing full quick-chat composition | 32,034 | 8,008 |
| Normal Use composition | 3,217 | 804 |
| Difference | 28,817 fewer | 7,204 fewer (about 90.0%) |

This is a prompt-size estimate, not provider-reported usage. No before/after production telemetry baseline was present, so no measured API token, cost, or latency savings are claimed. Runtime telemetry now captures the data needed for that comparison where the provider reports token usage.

## Tests

Added regression coverage for everyday classification and fast candidates, local arithmetic, complex reasoning and coding, large-document PDF routing, prompt fallback when the Normal Use file is missing, compact prompt composition, history preservation, specialist prompt preservation, and provider fallback without repeated calls.

Verification run:

- `python -m unittest discover -s tests -p 'test_normal_use_routing.py' -v` — 7 passed.
- `python -m unittest discover -s tests -p 'test_prompts.py' -v` — 15 passed.
- `python -m unittest discover -s tests -p 'test_pdf_studio.py' -v` — 26 passed, including the non-Gemini routing guarantee.
- `python -m unittest discover -s tests -v` — 232 tests discovered; 228 passed and 4 failed in existing code-execution sandbox tests (`test_environment_sanitization_excludes_secrets`, `test_failed_python_execution`, `test_successful_python_execution`, `test_timeout_enforcement`). All four returned `execution_unavailable` in this restricted environment. The Normal Use, prompt, and PDF tests passed in the full run.
- `pytest` was attempted for a focused run, but pytest is not installed in this environment; the same regression tests passed under the repository's `unittest` runner.

Provider calls in the new routing tests are mocked. No real AI quota was consumed by these tests. The local maths-engine fast-path regression uses the local engine only.

## Files changed

- `prompts/normal_use.txt`
- `ai_routing/prompts.py`
- `ai_routing/tasks.py`
- `ai_routing/router.py`
- `ai_routing/telemetry.py`
- `tests/test_prompts.py`
- `tests/test_normal_use_routing.py`
- `README.md`
- `BRAINY_NORMAL_USE_OPTIMIZATION.md`

## Safely editing the compact prompt

Keep the security and safety section intact, retain uncertainty and factuality requirements, and keep task-specific directions in their specialist prompts. Keep everyday answer guidance concise and do not include model/provider names. Run `python -m unittest discover -s tests -p 'test_prompts.py'` and `python -m unittest discover -s tests -p 'test_normal_use_routing.py'` after edits.
