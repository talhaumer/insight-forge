from typing import Dict, Any
from datetime import datetime
from .state import WorkflowState
from .tools.retriever import retrieve_market_data, retrieve_market_data_mcp, deduplicate_facts
from .tools.groq_llm import (
    extract_facts_with_groq,
    analyze_facts_with_groq,
    generate_report_with_groq,
)
from .guardrails.schemas import validate_facts, validate_report
from .guardrails.moderation import check_content, is_safe_content
from .observability import metrics_collector


def market_researcher(state: WorkflowState) -> WorkflowState:
    """Market Researcher agent - retrieves and extracts facts using Groq LLM"""
    query = state["query"]

    # Retrieve raw search data using MCP
    result = retrieve_market_data_mcp(query)

    if not result["success"]:
        state["tool_error"] = True
        state["context"] = f"Failed to retrieve data for query: {query}"
        metrics_collector.record_tool_call("retriever", 0, success=False)
        metrics_collector.record_fallback()
        return state

    # Use Groq LLM to extract structured facts
    groq_result = extract_facts_with_groq(query, result.get("search_results", []))

    if not groq_result["success"]:
        # Fallback to basic facts if Groq fails
        facts = result.get("facts", [])
        
        # If no facts from Tavily, create basic facts from search results
        if not facts and result.get("search_results"):
            facts = []
            for i, item in enumerate(result["search_results"][:5]):  # Limit to first 5 results
                if item.get("content"):
                    facts.append({
                        "fact": item["content"][:200] + "..." if len(item["content"]) > 200 else item["content"],
                        "source": item.get("url", "Unknown"),
                        "confidence": 0.6  # Lower confidence for basic extraction
                    })
        
        state["context"] = (
            f"Groq extraction failed, using basic facts: {groq_result.get('error', 'Unknown error')}"
        )
        metrics_collector.record_fallback()
    else:
        # Parse Groq response
        try:
            import json
            import re

            # Extract JSON from markdown code blocks if present
            content = groq_result["content"]
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = content

            parsed = json.loads(json_str)
            facts = parsed.get("facts", [])
            state["needs_more_context"] = parsed.get("needs_more_context", False)
        except Exception as e:
            facts = result.get("facts", [])
            state["context"] = f"Failed to parse Groq response: {str(e)}, using basic facts"

    # Deduplicate facts
    facts = deduplicate_facts(facts)

    # Check if we need more context
    if len(facts) < 2:
        state["needs_more_context"] = True

    # Update state
    fallback_type = result.get("fallback", "tavily_search")
    state["context"] = (
        f"Retrieved {len(facts)} facts about {query} using {fallback_type}"
    )
    state["tools_used"].append(fallback_type)
    state["outputs"]["facts"] = facts
    state["outputs"]["sources"] = result.get("sources", [])

    return state


def analyst(state: WorkflowState) -> WorkflowState:
    """Analyst agent - extracts structured insights and validates using Groq LLM"""
    facts = state["outputs"].get("facts", [])
    query = state["query"]

    # Use Groq LLM to analyze facts
    groq_result = analyze_facts_with_groq(facts, query)

    if not groq_result["success"]:
        # Fallback to basic validation
        state[
            "context"
        ] += f" | Groq analysis failed: {groq_result.get('error', 'Unknown error')}"
        schema_valid = validate_facts(facts)
        state["schema_ok"] = schema_valid

        # Basic policy check
        violations = []
        for fact in facts:
            violations.extend(check_content(fact.get("fact", "")))
        state["violations"] = violations
        state["policy_violation"] = len(violations) > 0

        # Record violations
        if violations:
            metrics_collector.record_violation("policy")
    else:
        # Parse Groq analysis
        try:
            import json

            analysis = json.loads(groq_result["content"])

            # Extract analysis results
            violations = analysis.get("violations", [])
            needs_more_context = analysis.get("needs_more_context", False)
            quality_score = analysis.get("quality_score", 0.5)

            # Validate facts against schema
            schema_valid = validate_facts(facts)
            state["schema_ok"] = schema_valid

            # Record schema violations
            if not schema_valid:
                metrics_collector.record_violation("schema")

            # Set state based on analysis
            state["violations"] = violations
            state["policy_violation"] = len(violations) > 0

            # Record policy violations
            if violations:
                metrics_collector.record_violation("policy")
            state["needs_more_context"] = needs_more_context
            state["outputs"]["analysis"] = analysis

            # Update context
            state[
                "context"
            ] += f" | Groq analysis: quality={quality_score}, violations={len(violations)}"

        except Exception as e:
            # Fallback if parsing fails
            state["context"] += f" | Failed to parse Groq analysis: {str(e)}"
            schema_valid = validate_facts(facts)
            state["schema_ok"] = schema_valid
            state["policy_violation"] = False

    return state


def writer(state: WorkflowState) -> WorkflowState:
    """Writer agent - produces final report using Groq LLM"""
    query = state["query"]
    facts = state["outputs"].get("facts", [])
    sources = state["outputs"].get("sources", [])
    analysis = state["outputs"].get("analysis", {})

    # Use Groq LLM to generate comprehensive report
    groq_result = generate_report_with_groq(query, facts, sources, analysis)

    if not groq_result["success"]:
        # Fallback to basic report generation
        state[
            "context"
        ] += f" | Groq report generation failed: {groq_result.get('error', 'Unknown error')}"
        metrics_collector.record_fallback()

        # Generate basic report
        if facts:
            summary = f"Market research on {query} reveals {len(facts)} key insights. "
            summary += " ".join([fact["fact"] for fact in facts[:3]])
            if len(facts) > 3:
                summary += "..."
        else:
            summary = (
                f"Limited data available for {query}. Further research recommended."
            )

        report = {
            "topic": query,
            "summary": summary,
            "references": sources,
            "timestamp": datetime.now().isoformat(),
            "facts": facts,
        }
    else:
        # Parse Groq-generated report
        try:
            import json

            report = json.loads(groq_result["content"])

            # Ensure required fields
            if "timestamp" not in report:
                report["timestamp"] = datetime.now().isoformat()
            if "facts" not in report:
                report["facts"] = facts

        except Exception as e:
            # Fallback if parsing fails
            state["context"] += f" | Failed to parse Groq report: {str(e)}"
            report = {
                "topic": query,
                "summary": f"Market research on {query} - Report generation failed",
                "references": sources,
                "timestamp": datetime.now().isoformat(),
                "facts": facts,
            }

    # Validate report
    report_valid = validate_report(report)
    state["schema_ok"] = report_valid

    # Record schema violations
    if not report_valid:
        metrics_collector.record_violation("schema")

    state["outputs"]["report"] = report
    state["context"] += f" | Generated report using Groq LLM, valid: {report_valid}"

    return state


def reviewer(state: WorkflowState) -> WorkflowState:
    """Reviewer agent - handles violations and errors"""
    if state["policy_violation"] or not state["schema_ok"]:
        # Create safe fallback report
        report = {
            "topic": state["query"],
            "summary": "Report requires manual review due to policy violations or schema issues.",
            "references": [],
            "timestamp": datetime.now().isoformat(),
            "facts": [],
        }
        state["outputs"]["report"] = report
        state["context"] += " | Report flagged for review"

    return state
