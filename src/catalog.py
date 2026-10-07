"""Local metadata catalog. Uploaded metadata and AI proposals are never executable."""

import csv
import hashlib
import io
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_UPLOAD_BYTES = 2_000_000
MAX_COLUMNS = 5000


class ColumnMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source_system: str = Field(min_length=1, max_length=200)
    table_name: str = Field(min_length=1, max_length=200)
    column_name: str = Field(min_length=1, max_length=200)
    data_type: str = Field(min_length=1, max_length=200)
    nullable: bool | None = None
    description: str = Field(default="", max_length=4000)
    source_table: str = Field(default="", max_length=200)
    source_column: str = Field(default="", max_length=200)
    transformation: str = Field(default="", max_length=4000)
    owner: str = Field(default="", max_length=200)
    unit: str = Field(default="", max_length=200)
    timezone: str = Field(default="", max_length=200)

    @field_validator("nullable", mode="before")
    @classmethod
    def parse_nullable(cls, value):
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        raise ValueError("nullable must be true, false or blank")


class RuleProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    rule_type: Literal["not_null", "unique", "range", "accepted_values", "custom"]
    specification: str = Field(min_length=1, max_length=2000)


class AISuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    definition: str = Field(min_length=1, max_length=4000)
    rationale: str = Field(min_length=1, max_length=2000)
    rules: list[RuleProposal] = Field(default_factory=list, max_length=5)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection(db_path=None):
    path = Path(db_path or os.getenv("INSIGHT_CATALOG_DB", "data/catalog.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS columns (
            id INTEGER PRIMARY KEY, source_system TEXT NOT NULL, table_name TEXT NOT NULL,
            column_name TEXT NOT NULL, metadata_json TEXT NOT NULL,
            definition TEXT NOT NULL DEFAULT '', definition_status TEXT NOT NULL DEFAULT 'undocumented',
            definition_origin TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL, UNIQUE(source_system, table_name, column_name));
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY, column_id INTEGER NOT NULL REFERENCES columns(id),
            definition TEXT NOT NULL, rationale TEXT NOT NULL, model TEXT NOT NULL,
            base_revision INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'proposed', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY, column_id INTEGER NOT NULL REFERENCES columns(id),
            name TEXT NOT NULL, rule_type TEXT NOT NULL, specification TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'proposed', origin TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY, column_id INTEGER NOT NULL REFERENCES columns(id),
            source_name TEXT NOT NULL, source_kind TEXT NOT NULL, content TEXT NOT NULL,
            sha256 TEXT NOT NULL, start_line INTEGER NOT NULL, end_line INTEGER NOT NULL,
            updated_at TEXT NOT NULL, UNIQUE(column_id, source_name));
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY, column_id INTEGER REFERENCES columns(id), action TEXT NOT NULL,
            details_json TEXT NOT NULL, created_at TEXT NOT NULL);
        """)
        with db:
            yield db
    finally:
        db.close()


def audit(db, column_id, action, details):
    db.execute(
        "INSERT INTO audit(column_id, action, details_json, created_at) VALUES(?,?,?,?)",
        (column_id, action, json.dumps(details), timestamp()),
    )


def parse_schema(content: bytes, suffix: str):
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("Schema file exceeds the 2 MB limit")
    text = content.decode("utf-8-sig")
    if suffix.lower() == ".json":
        raw = json.loads(text)
        if not isinstance(raw, list):
            raise ValueError("JSON must be an array of column records")
    elif suffix.lower() == ".csv":
        raw = list(csv.DictReader(io.StringIO(text)))
    else:
        raise ValueError("Upload a .csv or .json schema file")
    if not raw or len(raw) > MAX_COLUMNS:
        raise ValueError("Provide between 1 and 5000 columns")
    rows = [ColumnMetadata.model_validate(row).model_dump() for row in raw]
    identities = [(r["source_system"], r["table_name"], r["column_name"]) for r in rows]
    if len(set(identities)) != len(rows):
        raise ValueError("Duplicate source/table/column identities in upload")
    return rows


def import_schema(content, suffix, db_path=None):
    rows = parse_schema(content, suffix)  # Validate the entire input before any write.
    counts = {"added": 0, "updated": 0, "unchanged": 0}
    digest = hashlib.sha256(content).hexdigest()
    with connection(db_path) as db:
        for item in rows:
            identity = (item["source_system"], item["table_name"], item["column_name"])
            previous = db.execute(
                "SELECT * FROM columns WHERE source_system=? AND table_name=? AND column_name=?",
                identity,
            ).fetchone()
            metadata = json.dumps(item, sort_keys=True)
            if previous is None:
                cursor = db.execute(
                    """INSERT INTO columns(source_system, table_name, column_name, metadata_json,
                    definition, definition_status, definition_origin, updated_at) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        *identity,
                        metadata,
                        item["description"],
                        "proposed" if item["description"] else "undocumented",
                        "schema_upload" if item["description"] else "",
                        timestamp(),
                    ),
                )
                audit(
                    db,
                    cursor.lastrowid,
                    "import_added",
                    {"sha256": digest, "metadata": item},
                )
                counts["added"] += 1
            elif previous["metadata_json"] == metadata:
                counts["unchanged"] += 1
            else:
                # Preserve accepted business meaning, but require review when metadata changes.
                status = "needs_review" if previous["definition"] else "undocumented"
                db.execute(
                    "UPDATE columns SET metadata_json=?, definition_status=?, revision=revision+1, updated_at=? WHERE id=?",
                    (metadata, status, timestamp(), previous["id"]),
                )
                db.execute(
                    "UPDATE rules SET status='needs_review' WHERE column_id=? AND status='approved'",
                    (previous["id"],),
                )
                audit(
                    db,
                    previous["id"],
                    "import_changed",
                    {
                        "sha256": digest,
                        "before": json.loads(previous["metadata_json"]),
                        "after": item,
                    },
                )
                counts["updated"] += 1
    return counts


def get_column(column_id, db_path=None):
    with connection(db_path) as db:
        row = db.execute(
            "SELECT * FROM columns WHERE id=?", (int(column_id),)
        ).fetchone()
        if row is None:
            raise ValueError("Column does not exist")
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json"))
        for key in ("suggestions", "rules", "evidence", "audit"):
            result[key] = [
                dict(r)
                for r in db.execute(
                    f"SELECT * FROM {key} WHERE column_id=? ORDER BY id",
                    (int(column_id),),
                )
            ]
        return result


def list_columns(search="", db_path=None):
    with connection(db_path) as db:
        rows = db.execute(
            "SELECT * FROM columns ORDER BY source_system,table_name,column_name"
        ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            if search.casefold() in json.dumps(item, ensure_ascii=False).casefold():
                results.append(item)
        return results


def save_definition(column_id, definition, approved, expected_revision, db_path=None):
    definition = definition.strip()
    if not definition or len(definition) > 4000:
        raise ValueError("Definition must contain 1–4000 characters")
    status = "approved" if approved else "proposed"
    with connection(db_path) as db:
        previous = db.execute(
            "SELECT * FROM columns WHERE id=?", (int(column_id),)
        ).fetchone()
        if previous is None or previous["revision"] != int(expected_revision):
            raise ValueError("Column changed. Reload it before saving.")
        db.execute(
            "UPDATE columns SET definition=?,definition_status=?,definition_origin=?,revision=revision+1,updated_at=? WHERE id=?",
            (definition, status, "human_review", timestamp(), int(column_id)),
        )
        audit(
            db,
            int(column_id),
            "definition_saved",
            {"before": previous["definition"], "after": definition, "status": status},
        )


def store_suggestion(column_id, suggestion, model, expected_revision, db_path=None):
    parsed = AISuggestion.model_validate(suggestion)
    with connection(db_path) as db:
        current = db.execute(
            "SELECT revision FROM columns WHERE id=?", (int(column_id),)
        ).fetchone()
        if current is None or current["revision"] != int(expected_revision):
            raise ValueError("Column changed while AI was working. Reload and retry.")
        cursor = db.execute(
            """INSERT INTO suggestions(column_id,definition,rationale,model,base_revision,created_at)
            VALUES(?,?,?,?,?,?)""",
            (
                int(column_id),
                parsed.definition,
                parsed.rationale,
                model,
                int(expected_revision),
                timestamp(),
            ),
        )
        for rule in parsed.rules:
            db.execute(
                "INSERT INTO rules(column_id,name,rule_type,specification,origin,created_at) VALUES(?,?,?,?,?,?)",
                (
                    int(column_id),
                    rule.name,
                    rule.rule_type,
                    rule.specification,
                    f"ai:{model}",
                    timestamp(),
                ),
            )
        audit(
            db,
            int(column_id),
            "ai_suggestion_stored",
            {"suggestion_id": cursor.lastrowid, "model": model},
        )
        return cursor.lastrowid


def accept_suggestion(suggestion_id, expected_revision, db_path=None):
    with connection(db_path) as db:
        suggestion = db.execute(
            "SELECT * FROM suggestions WHERE id=?", (int(suggestion_id),)
        ).fetchone()
        if suggestion is None or suggestion["status"] != "proposed":
            raise ValueError("Suggestion is not available for acceptance")
        column = db.execute(
            "SELECT * FROM columns WHERE id=?", (suggestion["column_id"],)
        ).fetchone()
        if (
            column["revision"] != int(expected_revision)
            or column["revision"] != suggestion["base_revision"]
        ):
            raise ValueError(
                "Suggestion is stale. Review current metadata and generate a new suggestion."
            )
        db.execute(
            "UPDATE columns SET definition=?,definition_status='approved',definition_origin=?,revision=revision+1,updated_at=? WHERE id=?",
            (
                suggestion["definition"],
                f"ai_reviewed:{suggestion['model']}",
                timestamp(),
                column["id"],
            ),
        )
        db.execute(
            "UPDATE suggestions SET status='accepted' WHERE id=?", (int(suggestion_id),)
        )
        audit(
            db,
            column["id"],
            "suggestion_accepted",
            {
                "before": column["definition"],
                "after": suggestion["definition"],
                "suggestion_id": int(suggestion_id),
            },
        )


def add_rule(column_id, name, rule_type, specification, db_path=None):
    rule = RuleProposal(name=name, rule_type=rule_type, specification=specification)
    with connection(db_path) as db:
        if (
            db.execute(
                "SELECT id FROM columns WHERE id=?", (int(column_id),)
            ).fetchone()
            is None
        ):
            raise ValueError("Column does not exist")
        cursor = db.execute(
            "INSERT INTO rules(column_id,name,rule_type,specification,origin,created_at) VALUES(?,?,?,?,?,?)",
            (
                int(column_id),
                rule.name,
                rule.rule_type,
                rule.specification,
                "human",
                timestamp(),
            ),
        )
        audit(
            db,
            int(column_id),
            "rule_added",
            {"rule_id": cursor.lastrowid, **rule.model_dump()},
        )
        return cursor.lastrowid


def review_rule(rule_id, status, db_path=None):
    if status not in {"approved", "rejected"}:
        raise ValueError("Choose approved or rejected")
    with connection(db_path) as db:
        row = db.execute("SELECT * FROM rules WHERE id=?", (int(rule_id),)).fetchone()
        if row is None:
            raise ValueError("Rule does not exist")
        db.execute("UPDATE rules SET status=? WHERE id=?", (status, int(rule_id)))
        audit(
            db,
            row["column_id"],
            "rule_reviewed",
            {"rule_id": int(rule_id), "before": row["status"], "after": status},
        )


def export_catalog(db_path=None):
    return {
        "format_version": 1,
        "exported_at": timestamp(),
        "columns": [
            get_column(row["id"], db_path) for row in list_columns(db_path=db_path)
        ],
    }


def attach_evidence(
    column_id,
    source_name,
    content,
    source_kind,
    start_line=1,
    end_line=None,
    db_path=None,
):
    """Store a source snapshot and selected line range; never execute or infer lineage."""
    if source_kind not in {"sql", "python", "dbt", "text"}:
        raise ValueError("Unsupported evidence kind")
    if (
        not source_name.strip()
        or len(source_name) > 400
        or len(content.encode()) > MAX_UPLOAD_BYTES
    ):
        raise ValueError("Invalid source name or evidence larger than 2 MB")
    lines = content.splitlines()
    end_line = len(lines) if end_line is None else int(end_line)
    start_line = int(start_line)
    if not 1 <= start_line <= end_line <= len(lines):
        raise ValueError("Select an existing, non-empty line range")
    digest = hashlib.sha256(content.encode()).hexdigest()
    with connection(db_path) as db:
        column = db.execute(
            "SELECT * FROM columns WHERE id=?", (int(column_id),)
        ).fetchone()
        if column is None:
            raise ValueError("Column does not exist")
        previous = db.execute(
            "SELECT * FROM evidence WHERE column_id=? AND source_name=?",
            (int(column_id), source_name),
        ).fetchone()
        if previous and (
            previous["sha256"],
            previous["start_line"],
            previous["end_line"],
        ) == (digest, start_line, end_line):
            return previous["id"]
        db.execute(
            """INSERT INTO evidence(column_id,source_name,source_kind,content,sha256,start_line,end_line,updated_at)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(column_id,source_name) DO UPDATE SET
            source_kind=excluded.source_kind,content=excluded.content,sha256=excluded.sha256,
            start_line=excluded.start_line,end_line=excluded.end_line,updated_at=excluded.updated_at""",
            (
                int(column_id),
                source_name,
                source_kind,
                content,
                digest,
                start_line,
                end_line,
                timestamp(),
            ),
        )
        db.execute(
            "UPDATE columns SET revision=revision+1, definition_status=CASE WHEN definition<>'' THEN 'needs_review' ELSE 'undocumented' END, updated_at=? WHERE id=?",
            (timestamp(), int(column_id)),
        )
        db.execute(
            "UPDATE rules SET status='needs_review' WHERE column_id=? AND status='approved'",
            (int(column_id),),
        )
        audit(
            db,
            int(column_id),
            "evidence_updated" if previous else "evidence_attached",
            {
                "source_name": source_name,
                "sha256": digest,
                "start_line": start_line,
                "end_line": end_line,
                "previous_sha256": previous["sha256"] if previous else None,
            },
        )
        return db.execute(
            "SELECT id FROM evidence WHERE column_id=? AND source_name=?",
            (int(column_id), source_name),
        ).fetchone()["id"]
