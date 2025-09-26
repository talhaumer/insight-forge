#!/usr/bin/env python3
"""
Market Research Workflow - Main Entry Point
Minimal implementation with function-based approach
"""

from src.graph import run_market_research
import json


def main():
    """Main function to run market research workflow"""
    print("Market Research Workflow")
    print("=" * 30)

    # Example queries
    queries = [
        "Trends in electric vehicle adoption 2025",
        "AI market growth predictions",
        "Sustainable energy investments",
    ]

    for query in queries:
        print(f"\nResearching: {query}")
        print("-" * 40)

        result = run_market_research(query)

        print("Result:")
        print(json.dumps(result, indent=2))
        print()


if __name__ == "__main__":
    main()
