from __future__ import annotations

from .config import RECORD_FIELDS


def make_record(element: dict) -> dict:
    tags = element.get("tags", {})
    center = element.get("center", {})
    latitude = element.get("lat", center.get("lat"))
    longitude = element.get("lon", center.get("lon"))
    osm_type = element["type"]
    osm_id = element["id"]

    record = {field: tags.get(field, "") for field in RECORD_FIELDS}
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
