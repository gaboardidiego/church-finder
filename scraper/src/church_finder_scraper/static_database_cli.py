"""Command-line interface for assembling the website database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .paths import PROJECT_ROOT
from .static_database import build_database


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Combine a church JSON array and all services.json files under its "
            "matching data directory into one compact static-website database."
        )
    )
    parser.add_argument(
        "churches",
        type=Path,
        help="church list JSON file (for example, small.json)",
    )
    parser.add_argument(
        "--services-dir",
        type=Path,
        help="directory containing per-church folders (default: data/services/<input-name>)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="output JSON file (default: data/databases/<input-name>.database.json)",
    )
    args = parser.parse_args()
    churches_path = args.churches
    services_dir = args.services_dir or (PROJECT_ROOT / "data" / "services" / churches_path.stem)
    output_path = args.output or (
        PROJECT_ROOT / "data" / "databases" / f"{churches_path.stem}.database.json"
    )

    database = build_database(churches_path, services_dir)
    source_paths = {churches_path.resolve()}
    source_paths.update(path.resolve() for path in services_dir.rglob("services.json"))
    if output_path.resolve() in source_paths:
        raise SystemExit(f"Output path would overwrite an input file: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(database, ensure_ascii=False, separators=(",", ":")) + "\n"
    output_path.write_text(serialized, encoding="utf-8")
    service_count = sum(len(services) for services in database["services"].values())
    print(
        f"Wrote {len(database['churches'])} churches and {service_count} services "
        f"to {output_path} ({output_path.stat().st_size} bytes)"
    )
