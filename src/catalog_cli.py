"""Small platform-neutral entry point for metadata import and export."""

import argparse
import json
from pathlib import Path
from . import catalog
from .connectors import CONNECTORS, normalize


def main():
    parser = argparse.ArgumentParser(description="Insight Forge local metadata catalog")
    parser.add_argument("--db", default=None, help="SQLite catalog path")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("import")
    ingest.add_argument("file", type=Path)
    ingest.add_argument("--connector", choices=CONNECTORS, default="schema_csv_json")
    browse = commands.add_parser("list")
    browse.add_argument("--search", default="")
    export = commands.add_parser("export")
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "import":
        if args.file.stat().st_size > catalog.MAX_UPLOAD_BYTES:
            parser.error("Input exceeds 2 MB limit")
        rows = normalize(args.connector, args.file.read_bytes(), args.file.suffix)
        result = catalog.import_schema(json.dumps(rows).encode(), ".json", args.db)
    elif args.command == "list":
        result = catalog.list_columns(args.search, args.db)
    else:
        result = catalog.export_catalog(args.db)
        # Avoid silently replacing a previous export.
        with args.output.open("x") as file:
            json.dump(result, file, indent=2)
        result = {"exported": str(args.output), "columns": len(result["columns"])}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
