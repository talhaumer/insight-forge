"""Research stages with explicit failure results and traceable sources."""

import json
from datetime import datetime, timezone
from .state import WorkflowState
from .tools.retriever import retrieve_market_data, deduplicate_facts
from .tools.groq_llm import (
    extract_facts_with_groq,
    analyze_facts_with_groq,
    generate_report_with_groq,
)
from .guardrails.schemas import validate_facts, validate_report
from .guardrails.moderation import check_content
from .fallbacks import create_fallback_response


def parse_object(content):
    text = content.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def market_researcher(state: WorkflowState) -> WorkflowState:
    result = retrieve_market_data(state["query"])
    state["tools_used"].append("tavily_direct_api")
    if not result["success"]:
        state["tool_error"] = True
        state["context"] = result["error"]
        return state
    # Extraction sees at most five results; only those URLs can support its facts.
    evidence = result["search_results"][:5]
    sources = list(dict.fromkeys(item["url"] for item in evidence))
    state["outputs"]["sources"] = sources
    state["outputs"]["evidence"] = evidence
    extracted = extract_facts_with_groq(state["query"], evidence)
    try:
        if not extracted.get("success"):
            raise ValueError("Fact extraction unavailable")
        parsed = parse_object(extracted["content"])
        facts = parsed.get("facts")
        if not validate_facts(facts, sources):
            raise ValueError("No valid facts tied to retrieved source URLs")
        state["outputs"]["facts"] = deduplicate_facts(facts)
        state["needs_more_context"] = bool(parsed.get("needs_more_context", False))
    except (ValueError, TypeError, KeyError, AttributeError):
        state["schema_ok"] = False
        state["context"] = "Fact extraction failed or returned unsupported sources"
    return state


def analyst(state: WorkflowState) -> WorkflowState:
    facts = state["outputs"]["facts"]
    violations = [
        violation for fact in facts for violation in check_content(fact["fact"])
    ]
    state["violations"] = violations
    state["policy_violation"] = bool(violations)
    result = analyze_facts_with_groq(facts, state["query"])
    try:
        if not result.get("success"):
            raise ValueError("Analysis unavailable")
        analysis = parse_object(result["content"])
        reported = analysis.get("violations")
        needs_context = analysis.get("needs_more_context")
        if not isinstance(reported, list) or not all(
            isinstance(x, str) for x in reported
        ):
            raise ValueError("Invalid violations")
        if not isinstance(needs_context, bool):
            raise ValueError("Invalid context flag")
        state["violations"].extend(reported)
        state["policy_violation"] = bool(state["violations"])
        state["needs_more_context"] = state["needs_more_context"] or needs_context
        state["outputs"]["analysis"] = analysis
    except (ValueError, TypeError, KeyError, AttributeError):
        state["tool_error"] = True
        state["context"] = "Analysis unavailable or malformed"
    return state


def writer(state: WorkflowState) -> WorkflowState:
    facts = state["outputs"]["facts"]
    sources = list(dict.fromkeys(fact["source"] for fact in facts))
    result = generate_report_with_groq(
        state["query"], facts, sources, state["outputs"].get("analysis", {})
    )
    try:
        if not result.get("success"):
            raise ValueError("Report generation unavailable")
        report = parse_object(result["content"])
        # The writer may summarize, but must not replace evidence or invent citations.
        if "facts" in report and report["facts"] != facts:
            raise ValueError("Writer changed the evidence")
        if not isinstance(report.get("references"), list) or set(
            report["references"]
        ) != set(sources):
            raise ValueError("Writer references do not match evidence")
        report["topic"] = state["query"]
        report["facts"] = facts
        report["timestamp"] = datetime.now(timezone.utc).isoformat()
        # Discard unvalidated extra claims such as recommendations/key_insights.
        report = {
            key: report[key]
            for key in ("topic", "summary", "references", "timestamp", "facts")
        }
        if not validate_report(report, state["outputs"]["sources"]):
            raise ValueError("Invalid final report")
        report.update(success=True, status="completed", error=None)
        state["outputs"]["report"] = report
    except (ValueError, TypeError, KeyError, AttributeError):
        state["schema_ok"] = False
        state["context"] = "Report generation failed validation"
    return state


def reviewer(state: WorkflowState) -> WorkflowState:
    report = state["outputs"].get("report")
    blocked = (
        state["tool_error"]
        or state["policy_violation"]
        or not state["schema_ok"]
        or state["needs_more_context"]
    )
    if blocked or not validate_report(report, state["outputs"].get("sources", [])):
        status = "unavailable" if state["tool_error"] else "needs_review"
        state["outputs"]["report"] = create_fallback_response(
            state["query"],
            state["context"] or "Insufficient evidence or report requires review",
            status=status,
        )
    else:
        report["evidence"] = state["outputs"].get("evidence", [])
    return state
