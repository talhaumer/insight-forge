"""Local-first catalog UI. Run with python gradio_app.py."""

import json
import tempfile
from pathlib import Path
import gradio as gr
from dotenv import load_dotenv
from src import catalog
from src.connectors import normalize
from src.catalog_ai import generate_suggestion

load_dotenv()
DEMO = Path(__file__).parent / "examples" / "orders_schema.json"
HEADERS = ["ID", "System", "Table", "Column", "Type", "Definition status", "Definition"]


def refresh(search=""):
    columns = catalog.list_columns(search or "")
    rows = [
        [
            c["id"],
            c["source_system"],
            c["table_name"],
            c["column_name"],
            c["metadata"]["data_type"],
            c["definition_status"],
            c["definition"],
        ]
        for c in columns
    ]
    choices = [
        (f"{c['source_system']} / {c['table_name']}.{c['column_name']}", str(c["id"]))
        for c in columns
    ]
    return rows, gr.update(choices=choices, value=None)


def import_file(path, connector="schema_csv_json"):
    if not path:
        raise gr.Error("Choose a schema CSV or JSON file first.")
    file = Path(path)
    if file.stat().st_size > catalog.MAX_UPLOAD_BYTES:
        raise gr.Error("Schema file exceeds the 2 MB limit.")
    try:
        records = normalize(connector, file.read_bytes(), file.suffix)
        result = catalog.import_schema(json.dumps(records).encode(), ".json")
    except (ValueError, UnicodeError) as exc:
        raise gr.Error(str(exc)) from exc
    return (
        f"Imported: {result['added']} new, {result['updated']} changed, {result['unchanged']} unchanged. Missing columns are retained.",
        *refresh(),
    )


def select_column(column_id):
    if not column_id:
        return (
            {},
            "",
            False,
            None,
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
        )
    c = catalog.get_column(column_id)
    suggestions = [
        (f"#{s['id']} · {s['definition'][:70]}", str(s["id"]))
        for s in c["suggestions"]
        if s["status"] == "proposed"
    ]
    rules = [
        (f"#{r['id']} · {r['name']} ({r['status']})", str(r["id"])) for r in c["rules"]
    ]
    return (
        c,
        c["definition"],
        c["definition_status"] == "approved",
        c["revision"],
        gr.update(choices=suggestions, value=None),
        gr.update(choices=rules, value=None),
    )


def save(column_id, definition, approved, revision):
    if not column_id:
        raise gr.Error("Select a column first.")
    try:
        catalog.save_definition(column_id, definition, approved, revision)
    except ValueError as exc:
        raise gr.Error(str(exc)) from exc
    return (
        "Definition saved. Refresh the catalog table to see its new status.",
        *select_column(column_id),
    )


def suggest(column_id):
    if not column_id:
        raise gr.Error("Select a column first.")
    try:
        generate_suggestion(column_id)
    except ValueError as exc:
        raise gr.Error(str(exc)) from exc
    except Exception as exc:
        raise gr.Error(
            "AI provider unavailable or returned invalid output. No definition was approved."
        ) from exc
    return (
        "Proposal stored for review. Review its rationale and each rule in the details panel.",
        *select_column(column_id),
    )


def accept(column_id, suggestion_id, revision):
    if not column_id or not suggestion_id:
        raise gr.Error("Select a column and a suggestion first.")
    c = catalog.get_column(column_id)
    if int(suggestion_id) not in {s["id"] for s in c["suggestions"]}:
        raise gr.Error("Suggestion does not belong to the selected column.")
    try:
        catalog.accept_suggestion(suggestion_id, revision)
    except ValueError as exc:
        raise gr.Error(str(exc)) from exc
    return "Definition approved. Rules require a separate review.", *select_column(
        column_id
    )


def add_rule(column_id, name, kind, specification):
    if not column_id:
        raise gr.Error("Select a column first.")
    try:
        catalog.add_rule(column_id, name, kind, specification)
    except ValueError as exc:
        raise gr.Error(str(exc)) from exc
    return (
        "Rule proposal saved. Rules are documented, not executed against data.",
        *select_column(column_id),
    )


def review_rule(column_id, rule_id, decision):
    if not column_id or not rule_id:
        raise gr.Error("Select a column and rule first.")
    c = catalog.get_column(column_id)
    if int(rule_id) not in {r["id"] for r in c["rules"]}:
        raise gr.Error("Rule does not belong to this column.")
    catalog.review_rule(rule_id, decision)
    return f"Rule {decision}.", *select_column(column_id)


def attach(column_id, path, source_name, start, end):
    if not column_id or not path:
        raise gr.Error("Select a column and an evidence file first.")
    file = Path(path)
    kind = {".sql": "sql", ".py": "python", ".txt": "text"}.get(file.suffix.lower())
    if kind is None or file.stat().st_size > catalog.MAX_UPLOAD_BYTES:
        raise gr.Error("Choose SQL, Python or text evidence up to 2 MB.")
    try:
        catalog.attach_evidence(
            column_id,
            source_name or file.name,
            file.read_text(),
            kind,
            start_line=int(start),
            end_line=int(end) or None,
        )
    except (ValueError, UnicodeError) as exc:
        raise gr.Error(str(exc)) from exc
    return (
        "Evidence attached. Reloaded definition requires review when its context changes.",
        *select_column(column_id),
    )


def export():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="insight-catalog-", delete=False
    ) as file:
        json.dump(catalog.export_catalog(), file, indent=2)
        return file.name


def create_gradio_interface():
    with gr.Blocks(title="Insight Forge · Data Catalog", theme=gr.themes.Soft()) as app:
        gr.Markdown(
            "# Insight Forge\n### Understand your columns. Keep the business meaning with the schema.\nImport schema metadata, document definitions and review quality rules. Everything is stored locally in SQLite. No database credentials are required."
        )
        with gr.Tab("1 · Import & discover"):
            gr.Markdown(
                "Start with the synthetic orders schema, or upload your own CSV/JSON metadata. This upload accepts schema records, not raw customer data."
            )
            with gr.Row():
                upload = gr.File(
                    label="Schema file · CSV or JSON · up to 2 MB",
                    file_types=[".csv", ".json"],
                    type="filepath",
                )
                with gr.Column():
                    demo_button = gr.Button(
                        "Load sample orders schema", variant="primary"
                    )
                    upload_button = gr.Button("Import schema")
            connector = gr.Dropdown(
                ["schema_csv_json", "dbt_manifest"],
                value="schema_csv_json",
                label="Connector",
            )
            status = gr.Textbox(label="Import result", interactive=False)
            search = gr.Textbox(
                label="Search columns, definitions, owners or source mappings",
                placeholder="Try net_amount or Finance",
            )
            refresh_button = gr.Button("Search / refresh")
            table = gr.Dataframe(
                headers=HEADERS,
                datatype=["number"] + ["str"] * 6,
                interactive=False,
                label="Data dictionary",
                wrap=True,
            )
            gr.Markdown(
                "Imported descriptions start as **proposed**. Schema changes preserve existing definitions and mark them for review. Re-imports are additive: absent columns are not deleted."
            )
        with gr.Tab("2 · Define & review"):
            selected = gr.Dropdown(label="Column", choices=[])
            reload_button = gr.Button("Reload selected column")
            details = gr.JSON(
                label="Metadata · declared source mapping · proposals · rules · history"
            )
            revision = gr.State(None)
            definition = gr.Textbox(
                label="Business definition",
                lines=3,
                placeholder="Explain meaning, units, exclusions and relevant business context.",
            )
            approved = gr.Checkbox(
                label="I reviewed this definition and approve it", value=False
            )
            save_button = gr.Button("Save definition", variant="primary")
            with gr.Accordion("Attach SQL or Python evidence", open=False):
                gr.Markdown(
                    "Attach the file and line range that supports this field. Files are stored as text and never executed. Declared mappings are not automatically verified. A changed attachment marks the definition and approved rules for review."
                )
                source_file = gr.File(
                    label="Evidence file",
                    file_types=[".sql", ".py", ".txt"],
                    type="filepath",
                )
                source_name = gr.Textbox(
                    label="Stable source path or label", placeholder="models/orders.sql"
                )
                start_line = gr.Number(label="First line", value=1, precision=0)
                end_line = gr.Number(
                    label="Last line (0 = end of file)", value=0, precision=0
                )
                attach_button = gr.Button("Attach evidence snapshot")
            with gr.Accordion("Optional AI assistance", open=False):
                gr.Markdown(
                    "**Generate** sends this column’s metadata, current definition and selected code excerpts to Groq. Review attached code before using AI; source files may contain sensitive text. AI proposals can be wrong; inspect the definition, rationale and rules in the details panel before accepting."
                )
                ai_button = gr.Button("Generate AI proposal")
                suggestion = gr.Dropdown(
                    label="Definition proposal to approve", choices=[]
                )
                accept_button = gr.Button("Approve selected AI definition")
            with gr.Accordion("Quality rule register", open=False):
                gr.Markdown(
                    "Store business expectations for later implementation. This prototype does not run the rules against data."
                )
                rule_name = gr.Textbox(
                    label="Rule name", placeholder="Order identifier is required"
                )
                rule_type = gr.Dropdown(
                    ["not_null", "unique", "range", "accepted_values", "custom"],
                    value="not_null",
                    label="Rule type",
                )
                rule_spec = gr.Textbox(label="Rule specification", lines=2)
                rule_add = gr.Button("Add rule proposal")
                rule_selected = gr.Dropdown(label="Rule to review", choices=[])
                rule_decision = gr.Radio(
                    ["approved", "rejected"], value="approved", label="Review decision"
                )
                rule_review = gr.Button("Save rule decision")
            edit_status = gr.Textbox(label="Review result", interactive=False)
        with gr.Tab("3 · Export"):
            gr.Markdown(
                "Export definitions, metadata, rules, AI proposals and review history as JSON. Lineage fields are declarations supplied in the schema file—not relationships discovered or verified from source code."
            )
            export_button = gr.Button("Export catalog", variant="primary")
            download = gr.File(label="Catalog JSON", interactive=False)
        edit_outputs = [
            edit_status,
            details,
            definition,
            approved,
            revision,
            suggestion,
            rule_selected,
        ]
        detail_outputs = [
            details,
            definition,
            approved,
            revision,
            suggestion,
            rule_selected,
        ]
        demo_button.click(
            lambda: import_file(str(DEMO)), outputs=[status, table, selected]
        )
        upload_button.click(
            import_file, inputs=[upload, connector], outputs=[status, table, selected]
        )
        refresh_button.click(refresh, inputs=search, outputs=[table, selected])
        search.submit(refresh, inputs=search, outputs=[table, selected])
        selected.change(select_column, inputs=selected, outputs=detail_outputs)
        reload_button.click(select_column, inputs=selected, outputs=detail_outputs)
        save_button.click(
            save,
            inputs=[selected, definition, approved, revision],
            outputs=edit_outputs,
        )
        attach_button.click(
            attach,
            inputs=[selected, source_file, source_name, start_line, end_line],
            outputs=edit_outputs,
        )
        ai_button.click(suggest, inputs=selected, outputs=edit_outputs)
        accept_button.click(
            accept, inputs=[selected, suggestion, revision], outputs=edit_outputs
        )
        rule_add.click(
            add_rule,
            inputs=[selected, rule_name, rule_type, rule_spec],
            outputs=edit_outputs,
        )
        rule_review.click(
            review_rule,
            inputs=[selected, rule_selected, rule_decision],
            outputs=edit_outputs,
        )
        export_button.click(export, outputs=download)
        app.load(refresh, outputs=[table, selected])
    return app


if __name__ == "__main__":
    create_gradio_interface().launch(
        server_name="127.0.0.1", server_port=7860, share=False
    )
