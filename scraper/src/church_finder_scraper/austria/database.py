from __future__ import annotations

import json
import uuid

from .config import NAMESPACE


def _merge_church(source: dict, church_uuid: str, previous: dict | None) -> dict:
    church = {
        "uuid": church_uuid,
        "name": source["name"],
        "religion": "christian",
        "denomination": "roman_catholic",
    }
    if source["position"] is not None:
        church["position"] = source["position"]
    if previous is not None:
        if previous["name"] != church["name"] or (
            "position" in previous
            and "position" in church
            and previous["position"] != church["position"]
        ):
            raise ValueError(f"Conflicting church details across postcodes: {source['id']}")
        if "position" not in church and "position" in previous:
            church["position"] = previous["position"]
    return church


def _sorted_services(church_services: dict) -> list[dict]:
    return [
        {field: service[field] for field in ("language", "start_time", "date")}
        for service in sorted(
            church_services.values(),
            key=lambda service: (service["date"], service["start_time"], service["language"]),
        )
    ]


def build_database(batches: list[dict]) -> dict:
    churches, services = {}, {}
    for batch in batches:
        for entry in batch["results"]:
            source = entry["church"]
            church_uuid = str(uuid.uuid5(NAMESPACE, source["id"]))
            churches[church_uuid] = _merge_church(source, church_uuid, churches.get(church_uuid))
            target = services.setdefault(church_uuid, {})
            for service in entry["services"]:
                key = json.dumps(service, sort_keys=True, ensure_ascii=False)
                target[key] = service

    return {
        "churches": sorted(churches.values(), key=lambda church: church["uuid"]),
        "services": {
            church_id: _sorted_services(church_services)
            for church_id, church_services in services.items()
        },
    }
