#!/usr/bin/env python3
"""
Test script for Tavily MCP integration
"""

import os
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.tools.tavily_unified_client import tavily_search_mcp, tavily_extract_mcp
from src.tools.retriever import retrieve_market_data_mcp


def test_mcp_search():
    """Test MCP search functionality"""
    print("🔍 Testing Tavily MCP Search...")
    
    # Test basic search
    query = "AI market trends 2025"
    print(f"Query: {query}")
    
    try:
        result = tavily_search_mcp(query, max_results=3)
        print(f"✅ MCP Search Result: {result.get('success', False)}")
        
        if result.get('success'):
            search_results = result.get('search_results', [])
            facts = result.get('facts', [])
            sources = result.get('sources', [])
            print(f"📊 Found {len(search_results) if search_results else 0} results")
            print(f"📝 Facts: {len(facts) if facts else 0}")
            print(f"🔗 Sources: {len(sources) if sources else 0}")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")


def test_mcp_retriever():
    """Test MCP retriever integration"""
    print("\n🔍 Testing MCP Retriever Integration...")
    
    query = "Electric vehicle adoption rates"
    print(f"Query: {query}")
    
    try:
        result = retrieve_market_data_mcp(query)
        print(f"✅ MCP Retriever Result: {result.get('success', False)}")
        print(f"🔧 Method: {result.get('method', 'unknown')}")
        
        if result.get('success'):
            search_results = result.get('search_results', [])
            facts = result.get('facts', [])
            sources = result.get('sources', [])
            print(f"📊 Search Results: {len(search_results) if search_results else 0}")
            print(f"📝 Facts: {len(facts) if facts else 0}")
            print(f"🔗 Sources: {len(sources) if sources else 0}")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")


def test_content_extraction():
    """Test content extraction functionality"""
    print("\n🔍 Testing Content Extraction...")
    
    # Test with a simple URL first
    url = "https://example.com"
    print(f"URL: {url}")
    
    try:
        result = tavily_extract_mcp(url)
        print(f"✅ Content Extraction: {result.get('success', False)}")
        
        if result.get('success'):
            content = result.get('content', '')
            title = result.get('title', '')
            print(f"📄 Title: {title}")
            print(f"📄 Content length: {len(content)} characters")
            if content:
                print(f"📄 Content preview: {content[:200]}...")
            else:
                print("📄 No content extracted")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")


def main():
    """Run all MCP tests"""
    print("🚀 Starting Tavily MCP Integration Tests")
    print("=" * 50)
    
    # Check if API key is set
    if not os.getenv("TAVILY_API_KEY"):
        print("❌ TAVILY_API_KEY environment variable not set")
        print("Please set it with: export TAVILY_API_KEY=your_api_key_here")
        return
    
    print(f"✅ TAVILY_API_KEY is set")
    
    # Run tests
    test_mcp_search()
    test_mcp_retriever()
    test_content_extraction()
    
    print("\n" + "=" * 50)
    print("🏁 MCP Integration Tests Complete")


if __name__ == "__main__":
    main()
