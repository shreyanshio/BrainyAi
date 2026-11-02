# Brainy Web Search Architecture Specification

**Status:** Production Ready & Verified  
**Search Providers:** Tavily (Primary) + DuckDuckGo (Secondary / Cross-Check)  
**Modules:** `ai_routing/search_intent.py`, `ai_routing/query_planner.py`, `ai_routing/search_adapters.py`, `ai_routing/search_orchestrator.py`  

---

## 1. Architectural Philosophy

Brainy enforces a strict, transparent search policy:

1. **Deterministic Providers Only:** Tavily and DuckDuckGo are the **exclusive** web search engines. Built-in LLM stealth grounding (such as Gemini's native search tool or Groq-based scrapers) is explicitly prohibited.
2. **Mandatory Parallel Cross-Check:** High-confidence search requests invoke Tavily and DuckDuckGo concurrently to guarantee source diversity and resilience against provider outages.
3. **Strict Untrusted Data Fencing:** Web content is never treated as trusted prompt text. All scraped snippets are sanitized and enclosed in security boundaries to prevent indirect prompt injection.
4. **Targeted Execution:** Search is only triggered when genuinely necessary. Core educational concepts (e.g., photosynthesis, binary search trees, basic arithmetic) are answered from trained model weights to avoid latency and quota waste.

```
                           +------------------------+
                           |  User Incoming Message |
                           +-----------+------------+
                                       |
                                       v
                     +------------------------------------+
                     |    Search Intent Detector          |
                     |  - Positive Triggers (Time/Fact)   |
                     |  - Negative Filters (Math/Concept) |
                     +-----------------+------------------+
                                       |
                       [ Search Required = True ]
                                       |
                                       v
                     +------------------------------------+
                     |         Query Planner              |
                     |  - Strip conversational fluff      |
                     |  - Generate 1-3 targeted queries   |
                     +-----------------+------------------+
                                       |
                                       v
                     +------------------------------------+
                     |      Concurrent Orchestrator       |
                     |     (ThreadPoolExecutor Dispatch)  |
                     +--------+------------------+--------+
                              |                  |
                    (Timeout: 10s)             (Timeout: 8s)
                              v                  v
                     +----------------+  +----------------+
                     | Tavily Adapter |  |  DDG Adapter   |
                     +-------+--------+  +-------+--------+
                             \                  /
                              \                /
                               v              v
                     +------------------------------------+
                     |  URL Canonicalizer & SSRF Filter   |
                     |  - Strip UTM/fbclid parameters     |
                     |  - Block loopback, link-local, LAN |
                     +-----------------+------------------+
                                       |
                                       v
                     +------------------------------------+
                     | Cross-Verification & Deduplication |
                     |  - Match canonical URLs            |
                     |  - Tag provenance (both/tav/ddg)   |
                     +-----------------+------------------+
                                       |
                                       v
                     +------------------------------------+
                     | Untrusted Data Fencing & Citations |
                     |  - Anti-injection sanitization     |
                     |  - Standard Markdown citations [1] |
                     +-----------------+------------------+
                                       |
                                       v
                     +------------------------------------+
                     |    Gemini Flash LLM Synthesis      |
                     +------------------------------------+
```

---

## 2. Search Intent Detection (`ai_routing/search_intent.py`)

The intent detector runs deterministically before LLM invocation, applying strict positive triggers and negative exclusions.

### 2.1 Positive Triggers
- **Explicit Search Keywords:** `search`, `google`, `find out`, `lookup`, `web search`, `browse`, `dhundo`.
- **Temporal & Recency Anchors:** `latest`, `recent`, `today`, `this week`, `current`, `news`, `updates`, `2025`, `2026`.
- **Legitimacy & Fact-Checking:** `is this legitimate`, `is it a scam`, `fact check`, `verify`, `real or fake`.
- **Deep Research Queries:** Multi-perspective inquiries, market comparisons, breaking CVEs.
- **Modern Tech & Library Search:** Queries referencing cutting-edge frameworks (e.g. `React 19`, `Next.js 15`, `Gemini 3.8 SDK`, `Tailwind v4`).

### 2.2 Negative Filters (No Search Executed)
- **Greetings & Casual Banter:** `hello`, `hi`, `how are you`, `kya haal hai`, `tell me a joke`.
- **Stable Academic Concepts:** `photosynthesis`, `binary search tree`, `mitochondria`, `newton's laws`, `pythagorean theorem`.
- **Mathematics & Computation:** `solve 3x+5=20`, `integrate sin(x)`, `matrix multiplication`.
- **Pure Code & Algorithmic Tasks:** `reverse a linked list in python`, `write a quicksort function`.
- **Document Q&A Context:** Requests operating on already uploaded PDF contexts.

---

## 3. Query Planning (`ai_routing/query_planner.py`)

Users rarely type clean search queries. The Query Planner converts raw natural language into optimized keyword strings:

1. **Conversational De-noising:** Strips conversational prefixes such as `"can you please search for"`, `"tell me about"`, `"find information on"`.
2. **Subquery Distillation:**
   - Single fact: Produces 1 focused query (e.g., `"Gemini API changes 2026"`).
   - Comparative/Verification: Produces up to 3 targeted queries (e.g., query 1: `"site legitimacy domain.com"`, query 2: `"domain.com reviews scam complaints"`, query 3: `"domain.com official registration"`).
3. **Query Length Constraints:** Caps subqueries to 12 words max to prevent search engine syntax degradation.

---

## 4. Concurrent Search Orchestration (`ai_routing/search_orchestrator.py`)

Search requests execute concurrently via a background `ThreadPoolExecutor`:

- **Tavily Timeout:** 10.0 seconds.
- **DuckDuckGo Timeout:** 8.0 seconds.
- **Failure Isolation:** If Tavily encounters quota exhaustion (HTTP 429), DuckDuckGo completes independently. If DuckDuckGo fails or times out, Tavily delivers the primary result set. If both fail, the orchestrator gracefully signals zero search results without crashing.

---

## 5. Security & Prompt Injection Defenses

### 5.1 SSRF Defense (`is_safe_url`)
Every result URL is validated prior to storage or citation:
- IPv4/IPv6 loopback addresses (`127.0.0.1`, `::1`) are blocked.
- Link-local addresses (`169.254.0.0/16`) and cloud metadata endpoints (`http://169.254.169.254/latest/meta-data`, `metadata.google.internal`) are strictly rejected.
- RFC1918 private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) are blocked.
- Non-standard scheme/ports are blocked (only `http` and `https` allowed).

### 5.2 URL Canonicalization (`canonicalize_url`)
Tracking parameters are stripped to ensure exact cross-verification matching:
- Strips: `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`, `fbclid`, `gclid`, `ref`, `session_id`.
- Removes URL fragments (`#section`) and trailing slashes.

### 5.3 Anti-Prompt-Injection Fencing (`sanitize_snippet`)
Scraped web text is untrusted. Before passing snippets to the LLM:
- Control tokens like `<|im_start|>`, `<|im_end|>`, `system:`, `assistant:`, `human:` are neutralized.
- Markdown code fence delimiters (```) inside snippets are escaped.
- Snippets are wrapped in an immutable structural boundary:
  ```text
  --- BEGIN EXTERNAL SEARCH FINDINGS (UNTRUSTED DATA) ---
  [1] Title: Example Article
      URL: https://example.com/article
      Source: Tavily & DuckDuckGo (Cross-Verified)
      Snippet: ... sanitized text ...
  --- END EXTERNAL SEARCH FINDINGS ---
  ```

---

## 6. Real-Time Telemetry & Citation Metadata

Every search execution emits structured telemetry:
- `search_required`: Boolean.
- `search_providers_attempted`: e.g. `["tavily", "duckduckgo"]`.
- `search_providers_succeeded`: e.g. `["tavily", "duckduckgo"]`.
- `merged_results_count`: Number of deduplicated results.
- `cross_verified_count`: Number of sources confirmed by both engines.
- `search_latency_ms`: Execution duration.
- `citations`: List of structured objects (`index`, `title`, `url`, `source`) streamed to frontend UI for clickable source badges.
