# Insight Forge

**A lightweight data knowledge assistant for engineers and analysts.**

Keep field meanings, source mappings, business rules and supporting code together. Import schema metadata, attach SQL or Python evidence, review AI proposals and export an auditable data dictionary.

## The problem

An analyst asks: **“Does `net_amount` include tax, and where is it calculated?”**

The schema provides a type. The answer usually lives in a transformation file, a document or a colleague's memory. Insight Forge brings those pieces into one local catalog and distinguishes uploaded metadata, AI proposals and human-reviewed definitions.

This is an early local prototype for small data teams. It does not independently verify business truth and is not a hosted governance platform.

## Try it without credentials

Use Python 3.12:

```bash
git clone https://github.com/talhaumer/insight-forge.git
cd insight-forge
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-core.txt
python gradio_app.py
```

Windows activation: `.venv\Scripts\activate`.

Open **http://localhost:7860**, then:

1. Click **Load sample orders schema**.
2. Open **Define & review** and select `net_amount`.
3. Inspect its declared source fields and `gross_amount - discount_amount` transformation.
4. Correct or approve its business definition; add a quality rule and review it separately.
5. Attach a SQL/Python file and the line range supporting the definition.
6. Export the catalog as JSON, including evidence snapshots and edit history.

The included orders example is synthetic. Manual import, editing, approval and export do not require an LLM or database connection.

## What works today

| Capability | Implementation |
| --- | --- |
| Schema ingestion | CSV/JSON records with strict validation, duplicate checks and idempotent imports |
| dbt connector | Reads declared model/seed/snapshot columns and descriptions from `manifest.json` |
| Field dictionary | Type, nullable flag, meaning, unit, time zone and owner |
| Source mapping | User-declared source table, source columns and transformation text |
| Code evidence | SQL/Python/text snapshots with selected line ranges and SHA-256 hashes; never executed |
| AI assistance | Optional Groq suggestions using selected field metadata and attached excerpts |
| Human review | Separate proposed/approved definitions and rules; stale AI approvals rejected |
| Change handling | Re-imported metadata or reattached changed evidence marks existing definitions and approved rules for review |
| Local storage | SQLite catalog, suggestions, rule register, evidence and edit history |
| Export | JSON for downstream tools and review |
| Extension | File connector registry and callable Python API; see [connector guide](docs/CONNECTORS.md) |

**Quality rules are documented, not executed against datasets.** Source mappings are declarations, not automatically inferred or verified lineage. Code changes are noticed when evidence is reattached; there is no background watcher.

## Fit with data platforms

The catalog core is independent of a warehouse or orchestrator. File connectors normalize metadata into the same contract, so platform adapters can be added without replacing the review workflow.

| System/input | Current support |
| --- | --- |
| Generic schema CSV/JSON | Implemented |
| dbt manifest | Declared columns/descriptions implemented; dbt tests and dependency/SQL lineage extraction are not yet imported |
| SQL files | Evidence snapshots and line references; no SQL execution or dependency parser |
| Python files | Evidence snapshots and line references; no execution or inferred runtime lineage |
| PostgreSQL, MySQL, SQL Server, kdb+ | Schema exports can use the generic format; live connectors not implemented |
| Airflow, Spark, BI tools | Exported context can be attached as text; native integrations not implemented |

“All platforms” is an extension goal, not a compatibility claim for this version.

## Input format

CSV headers or JSON record keys:

| Field | Required | Meaning |
| --- | --- | --- |
| `source_system` | Yes | Stable system/project namespace |
| `table_name` | Yes | Qualified table/model name |
| `column_name` | Yes | Column identifier |
| `data_type` | Yes | Declared type, or `unknown` |
| `nullable` | No | `true`, `false` or blank/null |
| `description` | No | Imported draft business meaning |
| `source_table`, `source_column` | No | Declared upstream mapping; may list multiple columns as text |
| `transformation` | No | Calculation or business logic as text |
| `owner`, `unit`, `timezone` | No | Supplied business context; unknown values stay blank |

See [sample JSON](examples/orders_schema.json). JSON input is an array of records. The prototype limits uploads to 2 MB and 5,000 normalized columns. Unknown fields and duplicate identities are rejected before writing. Imports are additive; missing columns are retained. Imported descriptions start as **proposed**.

## Optional AI

Create `.env` with:

```dotenv
GROQ_API_KEY=your-key
INSIGHT_CATALOG_MODEL=llama-3.3-70b-versatile
INSIGHT_CATALOG_DB=data/catalog.sqlite3
```

Click **Generate AI proposal** only after reviewing the selected metadata and evidence. That action sends the column metadata, current definition and up to 12,000 characters of selected evidence excerpts to Groq. Files may contain sensitive text; the application does not automatically redact them.

AI can propose definitions and rules, but cannot automatically approve them or modify source mappings. Accepting a definition does not approve its rules. Model output is schema-validated; its business accuracy still requires a reviewer. Live Groq behavior has not been validated in this development environment.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Offline tests cover atomic imports, idempotence, schema changes, approval history, stale edits, invalid AI responses, evidence updates, adapters, exports and UI callbacks. Provider boundaries are mocked. GitHub Actions runs the suite on Python 3.12.

For a terminal workflow:

```bash
python -m src.catalog_cli import examples/orders_schema.json
python -m src.catalog_cli list --search net_amount
python -m src.catalog_cli export --output catalog.json
```

## Current boundaries

- Local single-user prototype: no authentication, named reviewer identities, role-based access or multi-user deployment support. Bind only to localhost.
- Review history records actions and changes, not a verified user identity. Back up the SQLite file to preserve catalog history.
- Evidence URLs/paths are supplied labels. File hashes identify uploaded content, not its trustworthiness.
- Schema changes conservatively invalidate review status; changes are detected only on import or evidence upload.
- No natural-language catalog Q&A, report reconciliation, database query execution or continuous monitoring yet.
- The earlier market-research experiment remains available via `python research_app.py`; see [its documentation](docs/RESEARCH_PROTOTYPE.md). Its failure handling and source validation were improved during this work. It is separate from the catalog.

## Next milestones

1. Import dbt tests and model dependencies with evidence references.
2. Add read-only database metadata adapters and supported SQL lineage parsing.
3. Answer field questions using approved definitions and linked evidence.
4. Compare two report definitions and label unverified discrepancy explanations as hypotheses.

The first product goal is a useful, reviewable data dictionary for an existing team—not autonomous governance or universal code understanding.
