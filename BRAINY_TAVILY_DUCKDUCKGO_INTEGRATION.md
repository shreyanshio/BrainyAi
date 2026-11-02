# Brainy Tavily & DuckDuckGo Search Integration Guide

**Status:** Production Ready & Operational  
**Implementation Files:** `ai_routing/search_adapters.py`, `ai_routing/search_orchestrator.py`  
**Primary Engine:** Tavily Search API  
**Secondary / Cross-Check Engine:** DuckDuckGo (`ddgs` v9.16.1)  

---

## 1. Tavily Search Adapter Integration

Tavily serves as Brainy's primary search engine, optimized specifically for factual grounding and context extraction.

### 1.1 API Configuration & Parameters
- **Endpoint:** `POST https://api.tavily.com/search`
- **Request Headers:** `Content-Type: application/json`
- **Request Payload:**
  ```json
  {
    "api_key": "<TAVILY_API_KEY>",
    "query": "targeted search query",
    "search_depth": "basic",
    "max_results": 5,
    "include_answer": false,
    "include_raw_content": false,
    "include_images": false
  }
  ```
  *Note:* `include_answer` is explicitly set to `false` so Brainy's designated LLM (Gemini Flash) handles answer synthesis rather than accepting pre-canned third-party summaries.

### 1.2 Key Management & Quota Protection
- **Environment Keys:** Reads `TAVILY_API_KEYS` (comma-delimited) or `TAVILY_API_KEY`.
- **Single-Project Rotation:** When HTTP 429 (quota exhausted) is returned, the adapter marks the active key exhausted and cycles to the next available key within the user's project.
- **Log Masking:** Keys are never logged in plain text; the adapter applies `mask_credential(key)` yielding format `********1234`.

### 1.3 Error Handling
- **HTTP 401:** Logs warning for invalid credentials and skips Tavily for the current session.
- **HTTP 429:** Rotates key or gracefully yields empty results, allowing DuckDuckGo to provide fallback evidence.
- **Timeout (10s):** Aborts Tavily request cleanly via `requests.post(..., timeout=10.0)`.

---

## 2. DuckDuckGo Search Adapter Integration

DuckDuckGo provides independent cross-verification and serves as a reliable secondary search channel.

### 2.1 Package & Engine Selection
- **Library:** Modern `ddgs` package (v9.16.1), the active successor to the deprecated `duckduckgo_search` library.
- **Authentication:** Zero API keys required, providing an infallible fallback if third-party API quotas lapse.
- **Dual Retrieval Modes:**
  1. **News Mode (`DDGS().news()`):** Triggered when the query contains temporal keywords (`breaking`, `latest news`, `today`, `yesterday`).
  2. **Text Mode (`DDGS().text()`):** Default mode for general web, technical documentation, and domain verification.
- **Parameters:** `region="in-en"`, `safesearch="moderate"`, `max_results=5`.

### 2.2 Operational Considerations & Limitations
- **Upstream Rate Limiting:** Aggressive automated bursts may trigger temporary IP bans from DuckDuckGo's public HTML endpoints.
- **Mitigation:**
  - Queries are capped to 1-3 targeted queries max per user message.
  - Strict 8.0-second timeout ensures DDG latency spikes never degrade the user chat experience.
  - DuckDuckGo results are cross-verified with Tavily; if DDG fails, Tavily alone fulfills the request.

---

## 3. Result Normalization, Deduplication & Cross-Verification

Both search adapters return standardized `SearchResultItem` dataclasses:

```python
@dataclass
class SearchResultItem:
    title: str
    url: str
    snippet: str
    source: str        # 'tavily' | 'duckduckgo' | 'both'
    score: float = 1.0
```

### 3.1 URL Deduplication Pipeline
1. **Canonicalization:** Both URL sets pass through `canonicalize_url()`:
   - Strips protocol nuances (`http` vs `https` normalized).
   - Removes query tracking bloat (`utm_*`, `fbclid`, `gclid`, `session_id`).
   - Strips trailing slashes and hash fragments (`#...`).
2. **Provenance Merging:**
   - If a URL appears in both Tavily and DuckDuckGo result sets, it is merged into a single entry with `source="both"`.
   - The merged entry receives a **cross-verification boost** (`score = 2.0`), bubbling it to the top of the evidence list.
3. **Snippet Truncation & Sanitization:**
   - Snippets are limited to 350 characters to prevent prompt bloat.
   - Control sequences (`<|im_start|>`, `system:`) are stripped to prevent injection attacks.

---

## 4. Execution Telemetry & Citation Output

When both providers complete, the search orchestrator formats clean citation references:

```json
[
  {
    "index": 1,
    "title": "Google Gemini 3.8 Flash Release Notes",
    "url": "https://ai.google.dev/updates/gemini-3-8",
    "source": "Tavily & DuckDuckGo (Cross-Verified)"
  },
  {
    "index": 2,
    "title": "Gemini API Documentation",
    "url": "https://ai.google.dev/docs",
    "source": "Tavily"
  }
]
```

These structured citations are:
1. Passed in the SSE stream (`type: "citations"`) for interactive UI badges.
2. Formatted into the untrusted evidence block passed to Gemini Flash for synthesis.

---

## 5. Verification Matrix

| Test Case | Scenario | Expected Behavior | Verification Status |
|-----------|----------|-------------------|---------------------|
| `test_04_tavily_adapter_success` | Mocked Tavily 200 OK | Normalizes title, URL, snippet | PASS |
| `test_05_duckduckgo_adapter_success` | Mocked DDGS 200 OK | Normalizes title, URL, snippet | PASS |
| `test_06_duckduckgo_news_fallback` | Breaking news keyword | Dispatches to `DDGS().news()` | PASS |
| `test_07_ssrf_protection` | Private IPs & cloud metadata | Rejects `169.254.169.254`, `127.0.0.1` | PASS |
| `test_08_canonicalize_url` | Dirty tracking URLs | Strips UTM/fbclid, standardizes path | PASS |
| `test_09_prompt_injection_sanitization` | Jailbreak tokens in web snippet | Neutralizes `<|im_start|>` and delimiters | PASS |
| `test_10_merge_and_deduplicate_results` | Overlapping URLs in Tavily & DDG | Merges to `both`, boosts ranking score | PASS |
| `test_11_orchestrator_concurrent_dispatch` | Live dual dispatch | Runs concurrently under 1 second | PASS |
| `test_12_orchestrator_tavily_failure_ddg_fallback` | Tavily 429 rate limit | DDG delivers evidence without error | PASS |
| `test_13_orchestrator_both_providers_fail` | Complete network outage | Returns empty list gracefully, zero 500s | PASS |
