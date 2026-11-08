from __future__ import annotations

import csv
import json
from pathlib import Path

from .config import CSV_FIELDS


def make_record(element: dict) -> dict:
    tags = element.get("tags", {})
    center = element.get("center", {})
    latitude = element.get("lat", center.get("lat"))
    longitude = element.get("lon", center.get("lon"))
    osm_type = element["type"]
    osm_id = element["id"]

    record = {field: tags.get(field, "") for field in CSV_FIELDS}
    record.update(
        {
            "osm_type": osm_type,
            "osm_id": osm_id,
            "latitude": latitude if latitude is not None else "",
            "longitude": longitude if longitude is not None else "",
            "osm_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
            "data_source": "OpenStreetMap",
            "attribution": "© OpenStreetMap contributors",
            "tags": tags,
        }
    )
    return record


def write_csv(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for record in records:
            row = record.copy()
            row["tags"] = json.dumps(record["tags"], ensure_ascii=False, sort_keys=True)
            writer.writerow(row)


def write_json(path: Path, records: list[dict], retrieved_at: str) -> None:
    document = {
        "data_source": "OpenStreetMap",
        "attribution": "© OpenStreetMap contributors",
        "retrieved_at_utc": retrieved_at,
        "results": records,
    }
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
