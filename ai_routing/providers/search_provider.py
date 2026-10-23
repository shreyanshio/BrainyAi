"""
Search grounding engine combining Tavily Search API with DuckDuckGo fallback.
"""

import logging
import ipaddress
import requests
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional
from ai_routing.registry import registry

logger = logging.getLogger("search_provider")

FORBIDDEN_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "metadata.google.internal",
    "metadata",
    "instance-data",
    "local",
}

def is_safe_url(url: str) -> str:
    """
    Validates that a URL is a well-formed, safe public HTTP/HTTPS URL.
    Blocks SSRF targets including loopback, link-local, cloud metadata services,
    and private IP ranges (RFC 1918 / RFC 4193).
    """
    if not url or not isinstance(url, str):
        return ""
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return ""
        hostname = parsed.hostname
        if not hostname:
            return ""
        hostname_clean = hostname.strip().lower()

        # Disallow userinfo (e.g. user:pass@host)
        if parsed.username or parsed.password:
            return ""

        # Disallow forbidden hostnames
        if (
            hostname_clean in FORBIDDEN_HOSTNAMES
            or hostname_clean.endswith(".local")
            or hostname_clean.endswith(".internal")
            or hostname_clean.endswith(".localhost")
        ):
            return ""

        # Disallow non-standard ports (e.g. internal admin ports)
        if parsed.port and parsed.port not in (80, 443, 8080, 8443):
            return ""

        # Check if hostname is an IP address
        try:
            ip = ipaddress.ip_address(hostname_clean)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                return ""
        except ValueError:
            # Hostname is a domain name, not an IP literal
            pass

        return url.strip()
    except Exception:
        return ""

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
