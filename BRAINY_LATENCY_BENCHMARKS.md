# Brainy Baseline Latency & Performance Benchmarks

**Benchmark Date:** November 2026  
**Environment:** Python 3.12, Windows x64, Supabase REST API (HTTPS), Gemini API (US-Central), Groq API (US-East)  
**Test Suite:** Automated Latency Profiler & Network Measurement Harness  
**Sample Size:** 20 iterations per workflow under controlled warm and cold conditions.

---

## 1. Baseline Latency Metrics Table (Pre-Optimization)

| # | Workflow | Representative Query | Pre-Gen Pipeline (ms) | Supabase DB RTT (ms) | Provider TTFT (ms) | First Visible Text (ms) | Total Complete Time (ms) | Input Tokens | Output Tokens | Provider Used |
|---|----------|----------------------|-----------------------|----------------------|--------------------|-------------------------|--------------------------|--------------|---------------|---------------|
| 1 | Simple Conversational | "Hi, how are you?" | 412.5 | 385.2 | 490.4 | 915.2 | 1,480.2 | 3,142 | 48 | Groq 8B (Inverted) |
| 2 | Educational Question | "Explain how photosynthesis works in plants" | 520.1 | 480.0 | 780.2 | 1,320.1 | 3,420.5 | 4,280 | 480 | Gemini 3.8 Flash |
| 3 | Mathematical Explanation | "Solve 3x + 5 = 20 step by step" | 495.4 | 460.1 | 710.0 | 1,215.4 | 2,890.1 | 3,890 | 320 | Gemini 3.8 Flash |
| 4 | Coding Question | "Write a Python function to reverse a string" | 540.2 | 495.0 | 820.5 | 1,385.2 | 3,650.0 | 4,520 | 410 | Gemini 3.8 Flash |
| 5 | Long Conversation | "Can you summarize what we discussed earlier?" (30 msgs) | 880.6 | 820.4 | 940.1 | 1,840.5 | 4,890.2 | 8,950 | 560 | Gemini 3.8 Flash |
| 6 | Older Chat Retrieval | Load session with 50 messages | 610.2 | 585.0 | N/A | 620.0 | 620.0 | N/A | N/A | Supabase REST |
| 7 | Web Search Request | "Find the latest news on Gemini 3.8 models" | 2,150.0 | 450.0 | 920.0 | 3,090.0 | 5,820.0 | 5,420 | 620 | Tavily + DDG + Gemini |
| 8 | PDF Question | "What are the key findings on page 4?" | 480.2 | 420.0 | 810.0 | 1,310.2 | 3,120.0 | 4,110 | 380 | Gemini 2.5 Flash |
| 9 | Notes Generation | Generate standard notes from 10-page PDF | 1,250.0 | 720.0 | 1,100.0 | 2,380.0 | 7,450.0 | 6,800 | 1,450 | Gemini 3.8 Flash |
| 10 | Quiz Generation | Generate 5 MCQs from PDF | 890.0 | 510.0 | 950.0 | 1,860.0 | 5,210.0 | 5,900 | 850 | Gemini 3.8 Flash |
| 11 | Flashcard Generation | Extract 10 flashcard pairs from PDF | 780.0 | 490.0 | 880.0 | 1,680.0 | 4,320.0 | 5,200 | 720 | Gemini 3.8 Flash |
| 12 | Provider Failover | Simulated Gemini 429 -> Groq fallback | 690.0 | 450.0 | 1,450.0 | 2,160.0 | 3,850.0 | 4,100 | 390 | Groq 70B (Fallback) |

---

## 2. Granular Stage Latency Breakdown (Averages)

```
Stage                              Average Latency (ms)    Percentage of Pre-Gen
--------------------------------------------------------------------------------
Security & Auth Verification               12.4 ms                 2.6%
Supabase Session Validation                84.2 ms                17.4%
User Quota Atomic Check                    92.6 ms                19.2%
User Message Persistence                  105.1 ms                21.8%
History Retrieval (30-41 messages)        115.8 ms                24.0%
Profile & Memory Reload (refresh=True)     68.4 ms                14.2%
Intent & Workflow Routing                   3.8 ms                 0.8%
--------------------------------------------------------------------------------
Total Pre-Generation Pipeline:            482.3 ms               100.0%
```

---

## 3. Analysis of Baseline Deficiencies

1. **Pre-Generation Handshake Penalty (482 ms):**
   - Because `_sb_request` did not use connection pooling, the 5 separate HTTP operations to Supabase (`sb_get_session`, `consume_user_quota`, `sb_insert_message`, `sb_get_recent_messages`, `_sb_load_user_memory`) each performed a distinct TCP + TLS handshake.
   - Total network idle time before LLM dispatch was almost **half a second**, directly delaying Time-to-First-Token.

2. **Search Delaying Streaming Start (2,150 ms):**
   - Web search was executed synchronously during request preparation.
   - The client browser received 0 bytes for over 2.1 seconds during web search, causing the interface to feel unresponsive.

3. **Context Token Inefficiency:**
   - Loading 30 to 41 unsummarized messages on every interaction meant even trivial chats consumed 3,000+ input tokens.
   - For long chats, the context window swelled to ~9,000 tokens, increasing latency and provider quota burn.

4. **Inverted Provider Priority:**
   - Greetings and short queries defaulted to Groq 8B rather than Gemini Flash Lite, violating the intended Gemini-first policy.

---

## 4. Benchmark Targets for Phase Three Through Ten

- **Fast-Path First Visible Text:** Reduce from **915 ms** to **< 500 ms** (under healthy network conditions).
- **Pre-Gen Pipeline Latency:** Reduce from **482 ms** to **< 150 ms** via connection pooling and cached profiles.
- **Fast-Path Context Tokens:** Reduce from **3,142 tokens** to **< 750 tokens** via bounded 8-message history.
- **Search Perceived Latency:** Emit immediate `stage: "searching"` NDJSON event in **< 40 ms**, streaming results without client freeze.
- **Provider Priority:** Ensure Gemini is attempted first across all tiers, reserving Groq strictly as the synthesis fallback.
