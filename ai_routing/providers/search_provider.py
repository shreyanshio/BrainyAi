"""
Search grounding engine combining Tavily Search API with DuckDuckGo fallback.
"""

import logging
import requests
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional
from ai_routing.registry import registry

logger = logging.getLogger("search_provider")

def is_safe_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    parsed = urlparse(url)
    return url if parsed.scheme in ("https", "http") and parsed.netloc else ""

def execute_search(query: str, max_results: int = 4) -> Dict[str, Any]:
    """
    Executes web research query using Tavily (primary) with DuckDuckGo (fallback).
    Returns structured results: {"source": "tavily"|"duckduckgo", "direct_answer": str, "citations": [{"title", "snippet", "url"}]}
    """
    clean_query = query.strip()
    if not clean_query:
        return {"source": "none", "direct_answer": "", "citations": []}

    rot = registry.get_rotator("tavily")
    if rot and rot.key_count > 0:
        for attempt in range(rot.key_count):
            try:
                key = rot.get_key()
                payload = {
                    "api_key": key,
                    "query": clean_query,
                    "search_depth": "basic",
                    "max_results": max_results,
                    "include_answer": True,
                    "include_raw_content": False
                }
                resp = requests.post(
                    "https://api.tavily.com/search",
                    json=payload,
                    timeout=15,
                    headers={"Content-Type": "application/json"}
                )
                resp.raise_for_status()
                data = resp.json()
                direct_ans = data.get("answer") or ""
                citations = []
                for item in data.get("results", [])[:max_results]:
                    title = str(item.get("title") or "")[:200]
                    content = str(item.get("content") or "")[:350]
                    url = is_safe_url(item.get("url", ""))
                    citations.append({"title": title, "snippet": content, "url": url})

                if citations or direct_ans:
                    return {
                        "source": "tavily",
                        "direct_answer": direct_ans,
                        "citations": citations
                    }
            except Exception as e:
                logger.warning("Tavily search attempt %d failed (%s), rotating key...", attempt + 1, type(e).__name__)
                continue

    # Fallback to DuckDuckGo Instant Answer API
    try:
        ddg_resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": clean_query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            timeout=8,
            headers={"User-Agent": "BrainyAI-StudyBot/2.0"}
        )
        ddg_resp.raise_for_status()
        data = ddg_resp.json()
        citations = []
        direct_ans = data.get("AbstractText") or data.get("Answer") or ""
        source_url = is_safe_url(data.get("AbstractURL") or "")

        if direct_ans:
            citations.append({
                "title": data.get("Heading") or clean_query,
                "snippet": direct_ans[:350],
                "url": source_url
            })

        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                citations.append({
                    "title": topic.get("Text")[:60] + "...",
                    "snippet": topic.get("Text")[:300],
                    "url": is_safe_url(topic.get("FirstURL") or "")
                })

        return {
            "source": "duckduckgo",
            "direct_answer": direct_ans,
            "citations": citations
        }
    except Exception as e:
        logger.warning("DuckDuckGo search fallback failed: %s", e)
        return {"source": "none", "direct_answer": "", "citations": []}
