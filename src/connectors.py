"""File-based connector interface. Adapters return normalized metadata, not credentials."""

import json
from .catalog import ColumnMetadata, MAX_UPLOAD_BYTES, parse_schema


def schema_records(content, suffix):
    return parse_schema(content, suffix)


def dbt_manifest_records(content, suffix=".json"):
    """Read declared dbt columns, not database state or inferred SQL column lineage."""
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("Manifest exceeds the prototype 2 MB limit")
    manifest = json.loads(content)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("nodes"), dict):
        raise ValueError("Expected a dbt manifest with a nodes object")
    records = []
    for node in manifest["nodes"].values():
        if node.get("resource_type") not in {"model", "seed", "snapshot"}:
            continue
        for name, column in (node.get("columns") or {}).items():
            meta = column.get("meta") or {}
            record = ColumnMetadata(
                source_system="dbt:"
                + str(manifest.get("metadata", {}).get("project_name") or "project"),
                table_name=node.get("relation_name") or node.get("name"),
                column_name=name,
                data_type=column.get("data_type") or "unknown",
                description=column.get("description") or "",
                owner=str(meta.get("owner") or ""),
                unit=str(meta.get("unit") or ""),
                timezone=str(meta.get("timezone") or ""),
            ).model_dump()
            records.append(record)
    if not records:
        raise ValueError("No declared columns found in dbt models, seeds or snapshots")
    return records


# Add a function here to implement another file adapter. All adapters share the catalog contract.
CONNECTORS = {"schema_csv_json": schema_records, "dbt_manifest": dbt_manifest_records}


def normalize(connector, content, suffix):
    if connector not in CONNECTORS:
        raise ValueError("Unsupported connector")
    records = CONNECTORS[connector](content, suffix)
    # Enforce common limits, identities and validation even for third-party adapters.
    return parse_schema(json.dumps(records).encode(), ".json")
