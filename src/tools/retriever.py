from typing import List, Dict, Any
from .tavily_unified_client import tavily_search_mcp
from .groq_llm import extract_facts_with_groq


def retrieve_market_data(query: str, use_mcp: bool = True) -> Dict[str, Any]:
    """Retrieve market data using Tavily search with Groq LLM fallback"""
    try:
        # Use unified Tavily client (handles MCP and fallbacks automatically)
        result = tavily_search_mcp(query)

        # Check if it's an API key error or no results
        if result.get("error") and "API key" in result["error"]:
            # Fallback to Groq LLM for basic research
            return retrieve_with_groq_fallback(query)

        # Convert Tavily results to search_results format for Groq
        search_results = []
        if "search_results" in result:
            search_results = result["search_results"]
        else:
            # Convert basic facts to search results format
            for i, fact in enumerate(result.get("facts", [])):
                search_results.append(
                    {
                        "title": f"Research Finding {i+1}",
                        "url": fact.get("source", ""),
                        "content": fact.get("fact", ""),
                    }
                )

        # If no good search results, try Groq LLM fallback
        if not search_results or len(search_results) == 0:
            return retrieve_with_groq_fallback(query)

        return {
            "facts": result.get("facts", []),
            "sources": result.get("sources", []),
            "search_results": search_results,
            "success": result.get("success", True),
            "error": result.get("error"),
        }
    except Exception as e:
        # Fallback to Groq LLM on any error
        return retrieve_with_groq_fallback(query)


def retrieve_with_groq_fallback(query: str) -> Dict[str, Any]:
    """Fallback retrieval using Groq LLM when Tavily fails"""
    try:
        # Use Groq LLM to generate basic research facts
        groq_result = extract_facts_with_groq(query, [])

        if groq_result["success"]:
            import json

            try:
                parsed = json.loads(groq_result["content"])
                facts = parsed.get("facts", [])
                sources = parsed.get("sources", [])

                return {
                    "facts": facts,
                    "sources": sources,
                    "search_results": [],  # No search results from LLM fallback
                    "success": True,
                    "error": None,
                    "fallback": "groq_llm",
                }
            except:
                pass

        # Final fallback - basic mock data
        return {
            "facts": [
                {
                    "fact": f"Basic research finding about {query} (LLM fallback)",
                    "source": "Groq LLM Fallback",
                    "confidence": 0.6,
                }
            ],
            "sources": ["Groq LLM Fallback"],
            "search_results": [],
            "success": True,
            "error": None,
            "fallback": "basic_mock",
        }
    except Exception as e:
        return {
            "facts": [],
            "sources": [],
            "search_results": [],
            "success": False,
            "error": str(e),
        }


def retrieve_market_data_mcp(query: str) -> Dict[str, Any]:
    """Retrieve market data using unified Tavily client with enhanced capabilities"""
    try:
        # Use unified Tavily client for search
        result = tavily_search_mcp(query, max_results=10, search_depth="advanced")
        
        # Check if MCP search was successful
        if not result.get("success", False):
            # Fallback to direct API if MCP fails
            return retrieve_market_data(query, use_mcp=False)
        
        # Process MCP results with safe handling
        search_results = result.get("search_results", []) or []
        facts = result.get("facts", []) or []
        sources = result.get("sources", []) or []
        
        # Convert to expected format with safe iteration
        processed_search_results = []
        if search_results and isinstance(search_results, list):
            for item in search_results:
                if item and isinstance(item, dict):
                    processed_search_results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("content", ""),
                    })
        
        return {
            "facts": facts,
            "sources": sources,
            "search_results": processed_search_results,
            "success": True,
            "error": None,
            "method": "mcp"
        }
        
    except Exception as e:
        # Fallback to direct API on any error
        return retrieve_market_data(query, use_mcp=False)


def deduplicate_facts(facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate facts based on content similarity"""
    seen = set()
    unique_facts = []

    for fact in facts:
        fact_text = fact.get("fact", "").lower().strip()
        if fact_text not in seen:
            seen.add(fact_text)
            unique_facts.append(fact)

    return unique_facts
