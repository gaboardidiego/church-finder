from __future__ import annotations

import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path


def _database_counts(path: Path) -> tuple[int, int]:
    with path.open(encoding="utf-8") as handle:
        database = json.load(handle)
    if not isinstance(database, dict):
        raise ValueError(f"Database must be a JSON object: {path}")
    churches = database.get("churches")
    services = database.get("services")
    if not isinstance(churches, list) or not isinstance(services, dict):
        raise ValueError(f"Database must contain churches and services: {path}")
    if any(not isinstance(rows, list) for rows in services.values()):
        raise ValueError(f"Database services must be arrays: {path}")
    return len(churches), sum(map(len, services.values()))


def publish_database(
    source: Path, destination: Path, backup_dir: Path
) -> tuple[tuple[int, int] | None, tuple[int, int], Path | None]:
    new_counts = _database_counts(source)
    previous_counts = _database_counts(destination) if destination.exists() else None
    backup_path = None

    destination.parent.mkdir(parents=True, exist_ok=True)
    if previous_counts is not None:
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        backup_path = backup_dir / f"{destination.stem}.{timestamp}{destination.suffix}"
        destination.replace(backup_path)

    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=destination.name + ".",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
        shutil.copy2(source, temporary)
        temporary.replace(destination)
    except Exception:
        if backup_path is not None:
            destination.unlink(missing_ok=True)
            backup_path.replace(destination)
        raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return previous_counts, new_counts, backup_path
