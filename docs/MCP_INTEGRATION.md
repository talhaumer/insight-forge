# Integration status

Insight Forge uses the Tavily Python SDK directly. There is no configured MCP server or working MCP transport.

`tavily_search_mcp`, `tavily_extract_mcp` and `retrieve_market_data_mcp` remain compatibility aliases. Their names do not imply MCP calls. `connect_mcp()` returns false; map/crawl helpers remain unimplemented and return failures.

The active workflow calls `retrieve_market_data`, which filters search results and refuses to substitute mock or model-only facts. Credentials are resolved at call time, so importing the application does not require an API key.

Run `python -m pytest -q` for offline provider-boundary and workflow regression tests. A live search smoke test requires your own credentials and is not included in offline CI.
