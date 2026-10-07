# Connector architecture

Insight Forge is a local Python application with an adapter interface. It is not yet an installable marketplace extension for every data platform.

## File adapter contract

`src/connectors.py` exposes a `CONNECTORS` registry. Each adapter implements:

```python
def adapter(content: bytes, suffix: str) -> list[dict]:
    # Read metadata without executing SQL, Python or uploaded templates.
    # Return records conforming to catalog.ColumnMetadata.
    ...
```

Register a name in `CONNECTORS`, then call `normalize(name, content, suffix)`. Normalization applies the shared limits, duplicate checks and schema validation. `catalog.import_schema()` persists the resulting records. The UI and CLI both use this path.

Implemented adapters:

- `schema_csv_json`: native schema records.
- `dbt_manifest`: declared columns from models, seeds and snapshots. Relation names identify models; undocumented column types are `unknown`. Column `meta.owner`, `meta.unit` and `meta.timezone` are optional context. No database connection is made. The adapter does not currently import tests or derive dependencies.

## Integrating a platform

A connector should emit observed metadata, preserving unknown fields rather than guessing. Suggested definitions belong in `store_suggestion`, never in approved fields. Live connectors should use metadata-only/read-only permissions, but none are implemented yet.

Call the core from an existing Python pipeline:

```python
import json
from src.connectors import normalize
from src.catalog import import_schema

with open('manifest.json', 'rb') as file:
    columns = normalize('dbt_manifest', file.read(), '.json')
summary = import_schema(json.dumps(columns).encode(), '.json')
```

## Evidence is separate from metadata

`catalog.attach_evidence(column_id, source_name, content, source_kind, start_line, end_line)` stores a full text snapshot with selected line references and a SHA-256 hash. Supported kinds are SQL, Python, dbt and text. The UI accepts SQL/Python/text files. No uploaded code is executed, parsed into asserted lineage or treated as instructions.

Changed metadata or evidence increments a field revision. Saving against a stale revision fails. AI proposals are bound to their base revision and cannot be approved after that context changes. Definitions and approved rules are marked for review when new evidence is attached or changed.

## Roadmap for native connectors

Implement adapters independently for PostgreSQL/MySQL/SQL Server metadata, dbt tests and model dependencies, Airflow DAG metadata, Spark plans and BI semantic definitions. Python runtime lineage requires instrumentation or explicit declarations; a source file alone cannot establish every data flow.
