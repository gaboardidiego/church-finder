from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise SystemExit(f"Cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON in {path}: {error}") from error


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
