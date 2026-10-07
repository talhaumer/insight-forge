import json
from pathlib import Path
import pytest


def test_ui_import_review_rule_and_export(tmp_path, monkeypatch):
    monkeypatch.setenv("INSIGHT_CATALOG_DB", str(tmp_path / "catalog.sqlite3"))
    # UI construction test is offline; do not initialize proxy-only transports.
    monkeypatch.setenv("GRADIO_ANALYTICS_ENABLED", "False")
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        monkeypatch.delenv(key, raising=False)
    import gradio_app as ui
    from src import catalog

    app = ui.create_gradio_interface()
    assert app.config["title"] == "Insight Forge · Data Catalog"
    message, rows, _ = ui.import_file(str(ui.DEMO))
    assert len(rows) == 6
    column_id = str(rows[0][0])
    details, definition, _, revision, _, _ = ui.select_column(column_id)
    result = ui.save(column_id, "Reviewed definition", True, revision)
    assert result[1]["definition_status"] == "approved"
    ui.add_rule(column_id, "Required", "not_null", "Value must not be null")
    rule_id = catalog.get_column(column_id)["rules"][0]["id"]
    ui.review_rule(column_id, str(rule_id), "approved")
    exported = Path(ui.export())
    try:
        payload = json.loads(exported.read_text())
        assert len(payload["columns"]) == 6
        assert any(c["definition"] == "Reviewed definition" for c in payload["columns"])
    finally:
        exported.unlink()
    app.close()
