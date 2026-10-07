# Tavily retrieval contract

The workflow uses one direct API retrieval path. `src/tools/retriever.py` accepts only non-empty search excerpts with HTTP(S) source URLs and derives the source list from those records. Provider failure, missing credentials and empty evidence return `success=False` with empty evidence and facts.

There is no fallback to generated research. Legacy `_mcp` aliases delegate to the direct API; the `use_mcp` argument is retained for compatibility and ignored.

Only the first five usable results are passed to extraction, matching the LLM helper's context limit. Extracted source URLs must belong to that set. This validates provenance membership, not factual truth or page freshness.
