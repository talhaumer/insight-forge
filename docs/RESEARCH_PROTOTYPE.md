# Insight Forge

**Source-traceable research pipeline for analysts.**

Insight Forge turns a research question into structured findings and a downloadable JSON report. It combines web-search ingestion, LLM-assisted extraction, data-quality checks and workflow orchestration. This is a portfolio prototype for demonstrating data engineering and analyst workflows; it is not a production service or an automated fact checker.

## Business use case

An analyst researching a market needs to collect external information, record where findings came from and distinguish usable results from failed research. Insight Forge provides a repeatable workflow for that task, with source URLs attached to each finding and explicit failure states.

Example questions include adoption trends, competitor product changes and industry research. Results require human review before business decisions.

## What this project demonstrates

| Area | Implemented behavior |
| --- | --- |
| API ingestion | Tavily direct API search; filters results without usable content and HTTP(S) source URLs |
| Data transformation | Groq-assisted structured extraction; deduplication by finding text and source |
| Data quality | Pydantic checks, source membership checks and final report validation |
| Orchestration | LangGraph routes failures and insufficient context to review |
| Analyst output | Gradio report, cited findings, retrieved evidence excerpts and JSON download |
| Reliability | Explicit completion states and offline regression tests with mocked provider boundaries |

## Data flow

1. **Ingest:** retrieve search results from Tavily. No results or provider failure stops research.
2. **Extract:** send up to five results to Groq. Every extracted finding must reference a URL from those results.
3. **Analyze:** assess the structured findings. Invalid analysis, flagged content or insufficient context stops publication.
4. **Write:** generate a summary using the accepted findings. The writer cannot replace the facts or introduce references outside their source set.
5. **Review:** validate every final report before returning it. The report includes the retrieved excerpts for inspection.

Source membership proves that a URL appeared in the retrieved evidence; it does **not** prove that a claim accurately represents the page. Confidence values are model estimates, not calibrated probabilities. Summaries can still contain mistakes.

## Run locally

Use Python 3.12. From the repository root:

```bash
git clone https://github.com/talhaumer/insight-forge.git
cd insight-forge
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-core.txt
cp .env.example .env
```

On Windows, activate with `.venv\Scripts\activate`.

Set `TAVILY_API_KEY` and `GROQ_API_KEY` in `.env`. LangSmith tracing is optional. Keep credentials out of Git.

```bash
python gradio_app.py
```

Open `http://localhost:7860`. Use `python main.py` for the existing command-line examples (each example may consume provider quota).

The original `requirements.txt` is retained as a historical environment snapshot. `requirements-core.txt` is the focused runtime dependency list; it is not a complete transitive lockfile.

## Test without API keys

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Tests exercise the real LangGraph workflow with mocked search and LLM responses. They cover valid output, empty evidence, provider failures, missing credentials, malformed JSON, unknown sources, invalid final reports and failure metrics. They do not verify live provider availability or answer accuracy.

## Output contract

| Status | Success | Meaning |
| --- | --- | --- |
| `completed` | `true` | Required structure and source checks passed; human factual review still needed |
| `unavailable` | `false` | Search, analysis or workflow could not complete |
| `needs_review` | `false` | Extracted facts/report failed checks or evidence was insufficient |

All responses contain `topic`, `summary`, `facts`, `references`, `timestamp`, `success`, `status` and `error`. Completed responses also contain `evidence`: the retrieved URL, title and excerpt records used for extraction. Failure responses contain empty facts and references. No mock or model-only research is substituted when search fails.

## Scope and limitations

- Tavily integration uses its **direct Python API**. Legacy functions with `_mcp` names are compatibility aliases; an MCP transport is not implemented.
- Keyword moderation is basic filtering, not enterprise security or a comprehensive privacy control.
- There is no warehouse, scheduled ingestion, SQL analysis layer or cross-run dataset persistence yet.
- Metrics are held in a shared in-memory collector, so concurrent runs do not have isolated metrics.
- Token counts are estimates. Trace examples under `artifacts/` are illustrative fixtures, not benchmark results.
- No live-provider benchmark, performance claim or production-readiness claim is made.

## Next development phase

To strengthen the data engineering and analytics use case:

1. Store runs, sources and findings in a versioned relational schema.
2. Add SQL queries for source coverage, data-quality failures and research trends.
3. Add incremental refresh, reproducible evaluation datasets and measured cost/latency.
4. Present a documented analyst case study with reviewed outputs and a dashboard.

These are planned capabilities, not features available today.
