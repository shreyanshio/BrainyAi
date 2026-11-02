# Brainy Web Search Architecture: Concurrent Tavily & DuckDuckGo Pipeline

**Status:** Production Ready & Operational  
**Search Engines:** Tavily API (Primary) + DuckDuckGo (`ddgs` v9.16.1, Cross-Check)  
**Modules:** `ai_routing/search_intent.py`, `ai_routing/query_planner.py`, `ai_routing/search_adapters.py`, `ai_routing/search_orchestrator.py`  

---

## 1. Core Architectural Mandate

1. **Dual Independent Providers:** Tavily and DuckDuckGo are the **exclusive** search tools. No hidden LLM search tools or third-party search APIs are permitted.
2. **Concurrent Execution:** High-confidence search requests invoke Tavily and DuckDuckGo in parallel using Python's `ThreadPoolExecutor`.
3. **Independent Timeouts:**
   - Tavily: 10.0 seconds.
   - DuckDuckGo: 8.0 seconds.
   - Total latency is bounded to `max(tavily, ddg)` rather than `sum(tavily + ddg)`.
4. **Resilient Degradation:** If one engine fails or exhausts quota (HTTP 429), the other engine fulfills the request without user-facing failure.

---

## 2. Security & Anti-Prompt-Injection Architecture

Web content is fundamentally untrusted. Brainy protects against Server-Side Request Forgery (SSRF) and indirect prompt injection through three defense layers:

### 2.1 SSRF Defense (`is_safe_url`)
Every URL returned by search providers is validated:
- Rejects loopback addresses (`127.0.0.1`, `::1`).
- Rejects link-local and cloud metadata endpoints (`169.254.169.254`, `metadata.google.internal`).
- Rejects RFC1918 private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
- Enforces strict HTTP/HTTPS schemes.

### 2.2 URL Canonicalization (`canonicalize_url`)
Strips tracking bloat (`utm_*`, `fbclid`, `gclid`, session tokens) and standardizes paths to allow exact cross-verification matching between Tavily and DuckDuckGo.

### 2.3 Untrusted Boundary Fencing (`sanitize_snippet`)
All scraped web snippets are scrubbed of control tokens (`<|im_start|>`, `<|im_end|>`, `system:`) and wrapped inside an immutable security boundary:
```text
--- BEGIN EXTERNAL SEARCH FINDINGS (UNTRUSTED DATA) ---
[1] Title: ...
    URL: ...
    Source: Tavily & DuckDuckGo (Cross-Verified)
    Snippet: ...
--- END EXTERNAL SEARCH FINDINGS ---
```
Gemini synthesizes findings from within this fenced boundary without allowing scraped content to alter system behavior.
