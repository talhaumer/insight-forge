import json
import pytest
from src import catalog

RECORD = {
    "source_system": "demo",
    "table_name": "orders",
    "column_name": "amount",
    "data_type": "decimal(18,2)",
    "nullable": False,
    "description": "Net order amount",
    "source_table": "raw.orders",
    "source_column": "gross, discount",
    "transformation": "gross - discount",
    "owner": "Finance",
}


@pytest.fixture
def db(tmp_path):
    return tmp_path / "catalog.sqlite3"


def ingest(db, rows=None):
    return catalog.import_schema(json.dumps(rows or [RECORD]).encode(), ".json", db)


def first(db):
    return catalog.get_column(catalog.list_columns(db_path=db)[0]["id"], db)


def test_persistent_import_and_source_mapping(db):
    assert ingest(db) == {"added": 1, "updated": 0, "unchanged": 0}
    result = first(db)
    assert result["definition_status"] == "proposed"
    assert result["metadata"]["transformation"] == "gross - discount"
    assert result["metadata"]["source_table"] == "raw.orders"
    assert len(catalog.list_columns("Finance", db)) == 1
    assert len(result["audit"]) == 1


def test_idempotent_import(db):
    ingest(db)
    assert ingest(db)["unchanged"] == 1
    assert len(first(db)["audit"]) == 1


def test_atomic_invalid_import(db):
    with pytest.raises(ValueError):
        ingest(db, [RECORD, {**RECORD, "column_name": "bad", "nullable": "maybe"}])
    assert catalog.list_columns(db_path=db) == []


def test_duplicate_identity_rejected(db):
    with pytest.raises(ValueError, match="Duplicate"):
        ingest(db, [RECORD, RECORD])
    assert catalog.list_columns(db_path=db) == []


def test_csv_nullability():
    text = b"source_system,table_name,column_name,data_type,nullable\ndemo,orders,id,bigint,false\ndemo,orders,optional,text,\n"
    rows = catalog.parse_schema(text, ".csv")
    assert rows[0]["nullable"] is False
    assert rows[1]["nullable"] is None


@pytest.mark.parametrize(
    "content,suffix",
    [(b"{}", ".json"), (b"[]", ".json"), (b"[]", ".sql"), (b"x" * 2000001, ".csv")],
)
def test_invalid_upload(content, suffix):
    with pytest.raises(ValueError):
        catalog.parse_schema(content, suffix)


def test_approval_and_audit(db):
    ingest(db)
    c = first(db)
    catalog.save_definition(
        c["id"], "Net amount excluding tax", True, c["revision"], db
    )
    result = first(db)
    assert result["definition_status"] == "approved"
    assert result["definition_origin"] == "human_review"
    assert result["revision"] == 2
    assert (
        json.loads(result["audit"][-1]["details_json"])["before"]
        == RECORD["description"]
    )


def test_stale_save_rejected(db):
    ingest(db)
    c = first(db)
    catalog.save_definition(c["id"], "Reviewed meaning", True, 1, db)
    with pytest.raises(ValueError, match="changed"):
        catalog.save_definition(c["id"], "Stale edit", True, 1, db)
    assert first(db)["definition"] == "Reviewed meaning"


def test_schema_change_preserves_definition_and_flags_review(db):
    ingest(db)
    c = first(db)
    catalog.save_definition(c["id"], "Reviewed meaning", True, 1, db)
    rule_id = catalog.add_rule(
        c["id"], "Required", "not_null", "amount must be non-null", db
    )
    catalog.review_rule(rule_id, "approved", db)
    assert ingest(db, [{**RECORD, "data_type": "float"}])["updated"] == 1
    c = first(db)
    assert c["definition"] == "Reviewed meaning"
    assert c["definition_status"] == "needs_review"
    assert c["rules"][0]["status"] == "needs_review"


def test_ai_proposal_does_not_overwrite_or_approve(db):
    ingest(db)
    c = first(db)
    sid = catalog.store_suggestion(
        c["id"],
        {
            "definition": "Suggested meaning",
            "rationale": "Based on field name",
            "rules": [
                {
                    "name": "Required",
                    "rule_type": "not_null",
                    "specification": "No null values",
                }
            ],
        },
        "test-model",
        1,
        db,
    )
    c = first(db)
    assert c["definition"] == RECORD["description"]
    assert c["suggestions"][0]["status"] == "proposed"
    assert c["rules"][0]["status"] == "proposed"
    catalog.accept_suggestion(sid, 1, db)
    c = first(db)
    assert c["definition"] == "Suggested meaning"
    assert c["definition_status"] == "approved"
    assert c["rules"][0]["status"] == "proposed"


def test_stale_ai_proposal_cannot_be_accepted(db):
    ingest(db)
    c = first(db)
    sid = catalog.store_suggestion(
        c["id"],
        {"definition": "Guess", "rationale": "Test", "rules": []},
        "test",
        1,
        db,
    )
    ingest(db, [{**RECORD, "data_type": "float"}])
    with pytest.raises(ValueError, match="stale"):
        catalog.accept_suggestion(sid, first(db)["revision"], db)


def test_failed_ai_schema_does_not_store_partial_rules(db):
    ingest(db)
    with pytest.raises(ValueError):
        catalog.store_suggestion(
            first(db)["id"],
            {
                "definition": "Guess",
                "rationale": "Test",
                "rules": [
                    {
                        "name": "bad",
                        "rule_type": "execute_sql",
                        "specification": "DROP TABLE columns",
                    }
                ],
            },
            "test",
            1,
            db,
        )
    assert first(db)["suggestions"] == first(db)["rules"] == []


def test_sql_like_metadata_is_only_text(db):
    ingest(db, [{**RECORD, "table_name": "orders'; DROP TABLE columns;--"}])
    assert len(catalog.list_columns(db_path=db)) == 1


def test_export_contains_review_history(db):
    ingest(db)
    result = catalog.export_catalog(db)
    assert result["format_version"] == 1
    assert result["columns"][0]["metadata"]["column_name"] == "amount"
    assert result["columns"][0]["audit"][0]["action"] == "import_added"


def test_missing_ai_key_does_not_write(db, monkeypatch):
    from src.catalog_ai import generate_suggestion

    ingest(db)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        generate_suggestion(first(db)["id"], db)
    assert first(db)["suggestions"] == []


def test_evidence_change_invalidates_review(db):
    ingest(db)
    cid = first(db)["id"]
    eid = catalog.attach_evidence(
        cid,
        "models/orders.sql",
        "select gross - discount as amount\nfrom orders",
        "sql",
        1,
        1,
        db,
    )
    c = first(db)
    assert c["evidence"][0]["start_line"] == 1
    assert c["definition_status"] == "needs_review"
    catalog.save_definition(cid, "Reviewed net amount", True, c["revision"], db)
    revision = first(db)["revision"]
    assert (
        catalog.attach_evidence(
            cid,
            "models/orders.sql",
            "select gross - discount as amount\nfrom orders",
            "sql",
            1,
            1,
            db,
        )
        == eid
    )
    assert first(db)["revision"] == revision
    catalog.attach_evidence(
        cid, "models/orders.sql", "select gross as amount\nfrom orders", "sql", 1, 1, db
    )
    c = first(db)
    assert c["definition_status"] == "needs_review"
    assert c["evidence"][0]["sha256"]
    assert c["definition"] == "Reviewed net amount"


def test_invalid_evidence_does_not_write(db):
    ingest(db)
    with pytest.raises(ValueError):
        catalog.attach_evidence(first(db)["id"], "test.py", "x = 1", "python", 2, 3, db)
    assert first(db)["evidence"] == []


def test_dbt_connector():
    from src.connectors import normalize

    manifest = {
        "metadata": {"project_name": "sales"},
        "nodes": {
            "model.sales.orders": {
                "resource_type": "model",
                "name": "orders",
                "relation_name": "analytics.orders",
                "columns": {
                    "amount": {
                        "description": "Net amount",
                        "data_type": "decimal",
                        "meta": {"unit": "USD"},
                    }
                },
            },
            "test.sales.unique": {
                "resource_type": "test",
                "name": "unique",
                "columns": {},
            },
        },
    }
    rows = normalize("dbt_manifest", json.dumps(manifest).encode(), ".json")
    assert len(rows) == 1
    assert rows[0]["source_system"] == "dbt:sales"
    assert rows[0]["unit"] == "USD"
    assert rows[0]["source_column"] == ""  # No invented lineage.


def test_connector_rejects_unsupported_input():
    from src.connectors import normalize

    with pytest.raises(ValueError):
        normalize("unknown_platform", b"[]", ".json")
