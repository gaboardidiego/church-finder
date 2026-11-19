"""Publish a completed database and back up the previous version."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from .regions import REGIONS, region_for_position


def _database_counts(path: Path) -> tuple[int, int]:
    with path.open(encoding="utf-8") as handle:
        database = json.load(handle)
    if not isinstance(database, dict):
        raise ValueError(f"Database must be a JSON object: {path}")
    churches = database.get("churches")
    services = database.get("services")
    if not isinstance(churches, list) or not isinstance(services, dict):
        raise ValueError(f"Database must contain churches and services: {path}")
    files = database.get("service_files")
    if files is not None:
        if not isinstance(files, dict):
            raise ValueError(f"Invalid service files: {path}")
        services = {}
        for filename in files.values():
            if not isinstance(filename, str) or Path(filename).name != filename:
                raise ValueError(f"Invalid service filename: {filename}")
            with (path.parent / filename).open(encoding="utf-8") as handle:
                region = json.load(handle)
            if not isinstance(region, dict) or not isinstance(region.get("services"), dict):
                raise ValueError(f"Invalid regional services: {filename}")
            for church_id, rows in region["services"].items():
                if church_id in services:
                    raise ValueError(f"Duplicate regional services for {church_id}")
                services[church_id] = rows
    if any(not isinstance(rows, list) for rows in services.values()):
        raise ValueError(f"Database services must be arrays: {path}")
    return len(churches), sum(map(len, services.values()))


def _write_atomic(path: Path, content: str) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=path.name + ".", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"


def _split_database(database: dict, regions: set[str] | None = None) -> tuple[dict, dict[str, str]]:
    churches = database.get("churches")
    services = database.get("services")
    if not isinstance(churches, list) or not isinstance(services, dict):
        raise ValueError("Database must contain churches and services")
    regional: dict[str, dict] = {
        region: {} for region in (REGIONS.values() if regions is None else sorted(regions))
    }
    index = []
    seen = set()
    for church in churches:
        if not isinstance(church, dict):
            raise ValueError("Database churches must be objects")
        church_id = church.get("uuid")
        if not isinstance(church_id, str) or not church_id or church_id in seen:
            raise ValueError(f"Invalid or duplicate church identifier: {church_id}")
        seen.add(church_id)
        rows = services.get(church_id, [])
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"Database services must be arrays of objects: {church_id}")
        region = (
            region_for_position(church.get("position")) or church.get("region")
            if regions is None
            else church.get("region")
        )
        if region not in regional:
            raise ValueError(f"Cannot determine a valid region for church {church_id}")
        regional[region][church_id] = rows
        summary = {(row.get("date", ""), row.get("language", "")) for row in rows}
        grouped: dict[str, list[str]] = {}
        for date, language in sorted(summary):
            grouped.setdefault(language, []).append(date)
        index.append(
            {
                **church,
                "region": region,
                "service_index": grouped,
            }
        )
    if services.keys() - seen:
        raise ValueError("Database contains services for unknown churches")
    contents = {region: _json({"services": rows}) for region, rows in regional.items()}
    files = {
        region: f"services-{region}-{hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]}.json"
        for region, content in contents.items()
    }
    return {"churches": index, "services": {}, "service_files": files}, contents


def publish_database(
    database: dict, destination: Path, backup_dir: Path, *, regions: set[str] | None = None
) -> tuple[tuple[int, int] | None, tuple[int, int], Path | None]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    index, regional = _split_database(database, regions)
    previous_counts = _database_counts(destination) if destination.exists() else None
    new_counts = (len(database["churches"]), sum(map(len, database["services"].values())))
    backup_path = None
    # Immutable service files are published before the index so existing readers remain consistent.
    for region, content in regional.items():
        path = destination.parent / index["service_files"][region]
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise ValueError(f"Regional service file hash collision: {path}")
        else:
            _write_atomic(path, content)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=destination.name + ".",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(_json(index))

        if _database_counts(temporary) != new_counts:
            raise ValueError("Regional service counts do not match source database")
        if previous_counts is not None:
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
            backup_path = backup_dir / f"{destination.stem}.{timestamp}{destination.suffix}"
            shutil.copy2(destination, backup_path)

        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return previous_counts, new_counts, backup_path
