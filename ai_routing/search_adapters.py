"""
BrainyAi Web Search Adapters & Canonical Result Normalization
Concrete implementations for Tavily Search (Primary) and DuckDuckGo Search (Secondary / Cross-Check).
Enforces uniform schema, anti-injection sanitization, SSRF protection, URL deduplication,
and independent failure tolerance.
"""

import os
import re
import time
import logging
import ipaddress
import requests
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from ai_routing.registry import registry, mask_credential

logger = logging.getLogger("search_adapters")

FORBIDDEN_HOSTNAMES = {
    "localhost", "127.0.0.1", "::1", "0.0.0.0",
    "metadata.google.internal", "metadata", "instance-data", "local"
}

_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "_ga"
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

        if parsed.username or parsed.password:
            return ""

        if (
            hostname_clean in FORBIDDEN_HOSTNAMES
            or hostname_clean.endswith(".local")
            or hostname_clean.endswith(".internal")
            or hostname_clean.endswith(".localhost")
        ):
            return ""

        if parsed.port and parsed.port not in (80, 443, 8080, 8443):
            return ""

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
            pass

        return url.strip()
    except Exception:
        return ""


def canonicalize_url(url: str) -> str:
    """
    Strips marketing tracking parameters while preserving real content query parameters.
    Normalizes domain casing and removes redundant trailing slashes.
    """
    safe = is_safe_url(url)
    if not safe:
        return ""
    try:
        parsed = urlparse(safe)
        clean_host = (parsed.hostname or "").lower()
        port_str = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
        netloc = f"{clean_host}{port_str}"

        # Clean query parameters
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        filtered_pairs = [
            (k, v) for k, v in query_pairs
            if k.lower() not in _TRACKING_PARAMS and not k.lower().startswith("utm_")
        ]
        new_query = urlencode(filtered_pairs)
        path = parsed.path.rstrip("/") if parsed.path and parsed.path != "/" else parsed.path

        return urlunparse((parsed.scheme.lower(), netloc, path, parsed.params, new_query, ""))
    except Exception:
        return safe


def sanitize_snippet(text: str, max_chars: int = 500) -> str:
    """
    Sanitizes retrieved snippet text against prompt injection tokens
    while preserving factual legibility.
    """
    if not text:
        return ""
    clean = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    # Neutralize prompt injection phrases
    clean = re.sub(
        r"(?i)\b(?:ignore\s+all\s+previous\s+instructions|system\s+prompt|system\s+directive|developer\s+mode)\b",
        "[REDACTED_INJECTION_PATTERN]",
        clean
    )
    return clean.strip()[:max_chars]


@dataclass
class NormalizedSearchResult:
    title: str
    url: str
    snippet: str
    published_at: Optional[str] = None
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    provider: str = "tavily"  # "tavily", "duckduckgo", or "both"
    relevance_score: Optional[float] = None
    content: Optional[str] = None
    cross_verified: bool = False


class TavilySearchAdapter:
    """
    Primary search provider adapter.
    Uses Tavily Search API with explicit params: include_answer=False, search_depth, max_results.
    """

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def search(
        self,
        query: str,
        max_results: int = 4,
        search_depth: str = "basic",
        topic: str = "general",
        time_range: Optional[str] = None
    ) -> List[NormalizedSearchResult]:
        rot = registry.get_rotator("tavily")
        if not rot or rot.key_count == 0:
            logger.info("Tavily API key not configured; skipping Tavily")
            return []

        clean_query = query.strip()
        if not clean_query:
            return []

        key = rot.get_key()
        if not key:
            return []

        payload: Dict[str, Any] = {
            "api_key": key,
            "query": clean_query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": False,  # Brainy LLM synthesizes evidence directly
            "include_raw_content": False,
            "topic": topic
        }
        if time_range:
            payload["time_range"] = time_range

        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            if resp.status_code == 429:
                rot.quarantine_key(key, cooldown_seconds=60.0)
                logger.warning("Tavily 429 rate limit reached on %s", mask_credential(key))
                return []

            resp.raise_for_status()
            data = resp.json()
            results = []

            for item in data.get("results", [])[:max_results]:
                raw_url = item.get("url") or ""
                canon_url = canonicalize_url(raw_url)
                if not canon_url:
                    continue

                title = sanitize_snippet(str(item.get("title") or "Source"), max_chars=180)
                snippet = sanitize_snippet(str(item.get("content") or ""), max_chars=450)
                pub_date = item.get("published_date")

                results.append(NormalizedSearchResult(
                    title=title,
                    url=canon_url,
                    snippet=snippet,
                    published_at=str(pub_date) if pub_date else None,
                    provider="tavily",
                    relevance_score=item.get("score")
                ))

            logger.info("Tavily returned %d verified results for '%s'", len(results), clean_query[:40])
            return results

        except requests.exceptions.Timeout:
            logger.warning("Tavily search timed out after %.1fs", self.timeout)
            return []
        except Exception as e:
            logger.warning("Tavily search failed (%s): %s", type(e).__name__, e)
            return []


class DuckDuckGoSearchAdapter:
    """
    Secondary search provider and independent cross-check adapter.
    Uses current 'ddgs' package for compliant text and news queries.
    """

    def __init__(self, timeout: float = 8.0, region: str = "in-en"):
        self.timeout = timeout
        self.region = region

    def search(
        self,
        query: str,
        max_results: int = 4,
        is_news: bool = False,
        timelimit: Optional[str] = None
    ) -> List[NormalizedSearchResult]:
        clean_query = query.strip()
        if not clean_query:
            return []

        try:
            from ddgs import DDGS
        except ImportError:
            logger.warning("ddgs package not installed; DuckDuckGo unavailable")
            return []

        results = []
        try:
            ddgs_client = DDGS(timeout=int(self.timeout))

            if is_news:
                raw_items = ddgs_client.news(
                    clean_query,
                    region=self.region,
                    safesearch="moderate",
                    max_results=max_results,
                    timelimit=timelimit
                )
            else:
                raw_items = ddgs_client.text(
                    clean_query,
                    region=self.region,
                    safesearch="moderate",
                    max_results=max_results,
                    timelimit=timelimit
                )

            for item in (raw_items or [])[:max_results]:
                raw_url = item.get("href") or item.get("url") or ""
                canon_url = canonicalize_url(raw_url)
                if not canon_url:
                    continue

                title = sanitize_snippet(str(item.get("title") or "Source"), max_chars=180)
                snippet = sanitize_snippet(str(item.get("body") or ""), max_chars=450)
                pub_date = item.get("date")

                results.append(NormalizedSearchResult(
                    title=title,
                    url=canon_url,
                    snippet=snippet,
                    published_at=str(pub_date) if pub_date else None,
                    provider="duckduckgo"
                ))

            logger.info("DuckDuckGo returned %d results for '%s'", len(results), clean_query[:40])
            return results

        except Exception as e:
            logger.warning("DuckDuckGo search failed (%s): %s", type(e).__name__, e)
            return []


def merge_and_deduplicate_results(
    tavily_results: List[NormalizedSearchResult],
    ddg_results: List[NormalizedSearchResult],
    max_total: int = 7
) -> List[NormalizedSearchResult]:
    """
    Merges results from Tavily and DuckDuckGo.
    Deduplicates by canonical URL, preserves multi-provider provenance ('both'),
    and favors official or longer snippets.
    """
    seen_urls: Dict[str, NormalizedSearchResult] = {}
    merged: List[NormalizedSearchResult] = []

    # Process Tavily results first (Primary)
    for r in tavily_results:
        c_url = canonicalize_url(r.url) or r.url
        r.url = c_url
        seen_urls[c_url] = r
        merged.append(r)

    # Process DuckDuckGo results (Secondary / Cross-Check)
    for r in ddg_results:
        c_url = canonicalize_url(r.url) or r.url
        r.url = c_url
        if c_url in seen_urls:
            existing = seen_urls[c_url]
            existing.provider = "both"
            existing.cross_verified = True
            # Combine snippets if the other has complementary details
            if len(r.snippet) > len(existing.snippet):
                existing.snippet = r.snippet
            if not existing.published_at and r.published_at:
                existing.published_at = r.published_at
        else:
            seen_urls[c_url] = r
            merged.append(r)

    return merged[:max_total]
