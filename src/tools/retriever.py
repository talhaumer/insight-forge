"""Retrieve evidence from Tavily; never substitute generated or mock facts."""

from typing import Any, Dict, List
from urllib.parse import urlsplit
from .tavily_unified_client import tavily_search


def is_source_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        url = urlsplit(value)
        return (
            url.scheme in {"http", "https"}
            and bool(url.hostname)
            and not url.username
            and not url.password
        )
    except ValueError:
        return False


def retrieve_market_data(query: str, use_mcp: bool = False) -> Dict[str, Any]:
    """The legacy use_mcp argument is ignored; transport is the direct API."""
    try:
        result = tavily_search(query, max_results=10, search_depth="advanced")
        if not result.get("success"):
            raise ValueError("Search provider unavailable")
        evidence = []
        for item in result.get("search_results", []) or []:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if (
                is_source_url(item.get("url"))
                and isinstance(content, str)
                and content.strip()
            ):
                evidence.append(
                    {
                        "title": item.get("title", ""),
                        "url": item["url"],
                        "content": content,
                    }
                )
        if not evidence:
            raise ValueError("No usable source evidence returned")
        return {
            "success": True,
            "error": None,
            "facts": [],
            "search_results": evidence,
            "sources": list(dict.fromkeys(item["url"] for item in evidence)),
            "method": "direct_api",
        }
    except Exception:
        return {
            "success": False,
            "error": "Search unavailable or no usable source evidence returned",
            "facts": [],
            "sources": [],
            "search_results": [],
            "method": "direct_api",
        }


def retrieve_market_data_mcp(query: str) -> Dict[str, Any]:
    """Compatibility alias; no MCP transport is implemented."""
    return retrieve_market_data(query)


def deduplicate_facts(facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    unique = []
    for fact in facts:
        key = (fact["fact"].lower().strip(), fact["source"])
        if key not in seen:
            seen.add(key)
            unique.append(fact)
    return unique
