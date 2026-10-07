"""
Unified Tavily Client for Market Research Workflow
Consolidates all Tavily functionality with MCP support and fallbacks
"""

import asyncio
import json
import os
import re
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Try to import MCP modules, fallback if not available
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    # Create dummy classes for fallback
    class ClientSession:
        pass
    class StdioServerParameters:
        pass
    def stdio_client(*args, **kwargs):
        pass


class TavilyUnifiedClient:
    """Unified Tavily client with MCP support and fallbacks"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY environment variable is required")
        
        self.mcp_available = MCP_AVAILABLE
        self.client_session: Optional[ClientSession] = None
        self._tavily_client = None
    
    def _get_tavily_client(self):
        """Get or create Tavily client for direct API calls"""
        if self._tavily_client is None:
            try:
                from tavily import TavilyClient
                self._tavily_client = TavilyClient(api_key=self.api_key)
            except ImportError:
                raise ImportError("Tavily package not installed")
        return self._tavily_client
    
    async def connect_mcp(self):
        """Connect to Tavily MCP server (if available)"""
        if not self.mcp_available:
            return False
            
        try:
            # For now, we'll use the direct API fallback since MCP server setup is complex
            # In production, you would set up a proper MCP server
            print("Using direct API fallback for Tavily (MCP server not configured)")
            self.client_session = None
            return False
        except Exception as e:
            print(f"Failed to connect to Tavily MCP server: {e}")
            self.client_session = None
            return False
    
    async def disconnect_mcp(self):
        """Disconnect from Tavily MCP server"""
        if self.client_session:
            self.client_session = None
    
    def search(self, query: str, max_results: int = 5, search_depth: str = "basic") -> Dict[str, Any]:
        """
        Perform a web search using the best available method
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            search_depth: Search depth ("basic" or "advanced")
        
        Returns:
            Dictionary containing search results
        """
        try:
            client = self._get_tavily_client()
            response = client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth
            )
            
            # Handle different response formats from Tavily API
            search_results = response.get("results", [])
            if not search_results:
                search_results = response.get("search_results", [])
            
            # Convert to expected format
            processed_results = []
            for item in search_results:
                processed_results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                })
            
            # Extract facts and sources
            facts = response.get("answer", "")
            if isinstance(facts, str) and facts:
                facts = [{"fact": facts, "source": "Tavily API", "confidence": 0.8}]
            else:
                facts = response.get("facts", [])
            
            sources = response.get("sources", [])
            
            return {
                "success": True,
                "search_results": processed_results,
                "facts": facts if facts else [],
                "sources": sources if sources else [],
                "method": "direct_api"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Search failed: {e}",
                "method": "direct_api"
            }
    
    def extract_content(self, url: str) -> Dict[str, Any]:
        """
        Extract content from a specific URL
        
        Args:
            url: URL to extract content from
        
        Returns:
            Dictionary containing extracted content
        """
        try:
            client = self._get_tavily_client()
            
            # Use search with the URL as query to extract content
            response = client.search(
                query=f"site:{url}",
                max_results=1,
                search_depth="advanced"
            )
            
            # Extract content from search results
            content = ""
            title = ""
            if response.get("results"):
                result = response["results"][0]
                content = result.get("content", "")
                title = result.get("title", "")
            
            return {
                "success": True,
                "content": content,
                "title": title,
                "url": url,
                "method": "direct_api"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Content extraction failed: {e}",
                "method": "direct_api"
            }
    
    def map_website(self, url: str) -> Dict[str, Any]:
        """
        Map the structure of a website (placeholder implementation)
        
        Args:
            url: URL to map
        
        Returns:
            Dictionary containing website structure
        """
        if not self.mcp_available:
            return {
                "success": False,
                "error": "Website mapping requires MCP (not implemented in direct API)",
                "method": "unavailable"
            }
        
        # Placeholder for MCP implementation
        return {
            "success": False,
            "error": "Website mapping not implemented",
            "method": "mcp_unavailable"
        }
    
    def crawl_website(self, url: str, max_pages: int = 10) -> Dict[str, Any]:
        """
        Crawl a website to extract content (placeholder implementation)
        
        Args:
            url: URL to crawl
            max_pages: Maximum number of pages to crawl
        
        Returns:
            Dictionary containing crawled content
        """
        if not self.mcp_available:
            return {
                "success": False,
                "error": "Website crawling requires MCP (not implemented in direct API)",
                "method": "unavailable"
            }
        
        # Placeholder for MCP implementation
        return {
            "success": False,
            "error": "Website crawling not implemented",
            "method": "mcp_unavailable"
        }


# Global instance for easy access
tavily_client = None

def get_tavily_client():
    """Resolve credentials at call time so imports work without API keys."""
    global tavily_client
    if tavily_client is None:
        tavily_client = TavilyUnifiedClient()
    return tavily_client


# Convenience functions for backward compatibility
def tavily_search(query: str, max_results: int = 5, search_depth: str = "basic") -> Dict[str, Any]:
    """
    Convenience function for Tavily search
    
    Args:
        query: Search query
        max_results: Maximum number of results
        search_depth: Search depth ("basic" or "advanced")
    
    Returns:
        Dictionary containing search results
    """
    return get_tavily_client().search(query, max_results, search_depth)


def tavily_search_mcp(query: str, max_results: int = 5, search_depth: str = "basic") -> Dict[str, Any]:
    """
    Convenience function for Tavily search (MCP-compatible name)
    
    Args:
        query: Search query
        max_results: Maximum number of results
        search_depth: Search depth ("basic" or "advanced")
    
    Returns:
        Dictionary containing search results
    """
    return get_tavily_client().search(query, max_results, search_depth)


def tavily_extract_mcp(url: str) -> Dict[str, Any]:
    """
    Convenience function for content extraction
    
    Args:
        url: URL to extract content from
    
    Returns:
        Dictionary containing extracted content
    """
    return get_tavily_client().extract_content(url)


def tavily_map_mcp(url: str) -> Dict[str, Any]:
    """
    Convenience function for website mapping
    
    Args:
        url: URL to map
    
    Returns:
        Dictionary containing website structure
    """
    return get_tavily_client().map_website(url)


def tavily_crawl_mcp(url: str, max_pages: int = 10) -> Dict[str, Any]:
    """
    Convenience function for website crawling
    
    Args:
        url: URL to crawl
        max_pages: Maximum number of pages to crawl
    
    Returns:
        Dictionary containing crawled content
    """
    return get_tavily_client().crawl_website(url, max_pages)
