#!/usr/bin/env python3
"""Combine church records and their service schedules into a compact JSON file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise SystemExit(f"Cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON in {path}: {error}") from error


def parse_args() -> argparse.Namespace:
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
    return parser.parse_args()


def build_database(churches_path: Path, services_dir: Path) -> dict[str, Any]:
    churches = load_json(churches_path)
    if not isinstance(churches, list):
        raise SystemExit(f"Expected {churches_path} to contain a JSON array of churches")

    church_ids: set[str] = set()
    for index, church in enumerate(churches):
        if not isinstance(church, dict):
            raise SystemExit(f"Church at index {index} in {churches_path} is not a JSON object")
        church_id = church.get("uuid")
        if not isinstance(church_id, str) or not church_id:
            raise SystemExit(f"Church at index {index} in {churches_path} has no non-empty uuid")
        if church_id in church_ids:
            raise SystemExit(f"Duplicate church uuid in {churches_path}: {church_id}")
        church_ids.add(church_id)

    if not services_dir.is_dir():
        raise SystemExit(f"Services directory does not exist: {services_dir}")

    services_by_church: dict[str, Any] = {}
    for service_path in sorted(services_dir.rglob("services.json")):
        if not service_path.is_file():
            continue
        church_id = service_path.parent.name
        if church_id in services_by_church:
            raise SystemExit(f"Multiple services.json files found for church uuid {church_id}")

        services = load_json(service_path)
        if not isinstance(services, list):
            raise SystemExit(f"Expected {service_path} to contain a JSON array")
        services_by_church[church_id] = services

    missing_services = sorted(church_ids - services_by_church.keys())
    if missing_services:
        missing_ids = ", ".join(missing_services)
        raise SystemExit(f"No services.json found for church uuid(s): {missing_ids}")

    return {"churches": churches, "services": services_by_church}


def main() -> None:
    args = parse_args()
    churches_path = args.churches
    services_dir = args.services_dir or (
        REPOSITORY_ROOT / "data" / "services" / churches_path.stem
    )
    output_path = args.output or (
        REPOSITORY_ROOT
        / "data"
        / "databases"
        / f"{churches_path.stem}.database.json"
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


if __name__ == "__main__":
    main()
