"""Offline regression tests; provider boundaries are mocked, workflow is real."""

import json
import pytest
from src import agents, graph
from src.tools import retriever, tavily_unified_client
from src.guardrails.schemas import validate_report

URL = "https://example.org/report"
FACT = {
    "fact": "The survey included 100 respondents.",
    "source": URL,
    "confidence": 0.8,
}


@pytest.fixture(autouse=True)
def providers(monkeypatch):
    monkeypatch.setattr(graph, "setup_langsmith", lambda: None)
    monkeypatch.setattr(graph, "create_tracer", lambda: None)
    monkeypatch.setattr(
        retriever,
        "tavily_search",
        lambda *a, **k: {
            "success": True,
            "search_results": [
                {"url": URL, "content": FACT["fact"], "title": "Survey"}
            ],
        },
    )
    monkeypatch.setattr(
        agents,
        "extract_facts_with_groq",
        lambda *a: {
            "success": True,
            "content": json.dumps({"facts": [FACT], "needs_more_context": False}),
        },
    )
    monkeypatch.setattr(
        agents,
        "analyze_facts_with_groq",
        lambda *a: {
            "success": True,
            "content": json.dumps({"violations": [], "needs_more_context": False}),
        },
    )
    monkeypatch.setattr(
        agents,
        "generate_report_with_groq",
        lambda *a: {
            "success": True,
            "content": json.dumps({"summary": FACT["fact"], "references": [URL]}),
        },
    )


def test_success_preserves_sources():
    result = graph.run_market_research("Survey research")
    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["facts"] == [FACT]
    assert result["references"] == [URL]
    assert validate_report(result, [URL])


@pytest.mark.parametrize(
    "response",
    [
        {"success": False, "error": "rate limited"},
        {"success": True, "search_results": []},
        {"success": True, "search_results": [{"url": "invalid", "content": "text"}]},
        {"success": True, "search_results": [{"url": URL, "content": ""}]},
    ],
)
def test_search_failure_never_becomes_research(monkeypatch, response):
    monkeypatch.setattr(retriever, "tavily_search", lambda *a, **k: response)
    monkeypatch.setattr(
        agents,
        "extract_facts_with_groq",
        lambda *a: pytest.fail("Must not call LLM without evidence"),
    )
    result = graph.run_market_research("Survey")
    assert result["success"] is False
    assert result["status"] == "unavailable"
    assert result["facts"] == result["references"] == []


def test_provider_exception(monkeypatch):
    def fail(*a, **k):
        raise RuntimeError("provider error")

    monkeypatch.setattr(retriever, "tavily_search", fail)
    assert graph.run_market_research("Survey")["status"] == "unavailable"


@pytest.mark.parametrize(
    "facts",
    [
        [],
        [{"fact": "claim", "source": "https://invented.org", "confidence": 0.9}],
        [{"fact": "claim", "source": URL, "confidence": 3}],
        [None],
    ],
)
def test_extraction_rejects_invalid_evidence(monkeypatch, facts):
    monkeypatch.setattr(
        agents,
        "extract_facts_with_groq",
        lambda *a: {"success": True, "content": json.dumps({"facts": facts})},
    )
    assert graph.run_market_research("Survey")["status"] == "needs_review"


@pytest.mark.parametrize(
    "stage",
    ["extract_facts_with_groq", "analyze_facts_with_groq", "generate_report_with_groq"],
)
def test_malformed_llm_json_cannot_succeed(monkeypatch, stage):
    monkeypatch.setattr(
        agents, stage, lambda *a: {"success": True, "content": "not JSON"}
    )
    assert graph.run_market_research("Survey")["success"] is False


@pytest.mark.parametrize(
    "report",
    [
        {"summary": "", "references": [URL]},
        {"summary": "Claim", "references": ["https://invented.org"]},
        {"summary": "Claim", "references": []},
        {
            "summary": "Claim",
            "references": [URL],
            "facts": [{**FACT, "fact": "Changed claim"}],
        },
    ],
)
def test_writer_validation_blocks_completion(monkeypatch, report):
    monkeypatch.setattr(
        agents,
        "generate_report_with_groq",
        lambda *a: {"success": True, "content": json.dumps(report)},
    )
    result = graph.run_market_research("Survey")
    assert result["success"] is False
    assert result["status"] == "needs_review"
    assert result["facts"] == []


def test_insufficient_context_blocks_writer(monkeypatch):
    monkeypatch.setattr(
        agents,
        "analyze_facts_with_groq",
        lambda *a: {
            "success": True,
            "content": json.dumps({"violations": [], "needs_more_context": True}),
        },
    )
    monkeypatch.setattr(
        agents, "generate_report_with_groq", lambda *a: pytest.fail("Must not write")
    )
    assert graph.run_market_research("Survey")["status"] == "needs_review"


def test_missing_key_is_runtime_failure(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr(tavily_unified_client, "tavily_client", None)
    monkeypatch.setattr(retriever, "tavily_search", tavily_unified_client.tavily_search)
    assert graph.run_market_research("Survey")["status"] == "unavailable"


def test_failure_metrics(monkeypatch):
    before = graph.metrics_collector.get_metrics()["workflow_stats"]["failed_runs"]
    monkeypatch.setattr(retriever, "tavily_search", lambda *a, **k: {"success": False})
    graph.run_market_research("Survey")
    assert (
        graph.metrics_collector.get_metrics()["workflow_stats"]["failed_runs"]
        == before + 1
    )


def test_empty_query():
    assert graph.run_market_research("  ")["success"] is False


def test_final_reviewer_rejects_invalid_report():
    state = {
        "query": "Survey",
        "context": "",
        "tool_error": False,
        "policy_violation": False,
        "schema_ok": True,
        "needs_more_context": False,
        "outputs": {"sources": [URL], "report": {"summary": "invalid"}},
    }
    assert agents.reviewer(state)["outputs"]["report"]["success"] is False
