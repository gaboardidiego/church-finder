from __future__ import annotations

import json
import uuid

from .config import NAMESPACE


def build_database(batches: list[dict]) -> dict:
    churches, services = {}, {}
    for batch in batches:
        for entry in batch["results"]:
            source = entry["church"]
            church_uuid = str(uuid.uuid5(NAMESPACE, source["id"]))
            church = {
                "uuid": church_uuid,
                "name": source["name"],
                "religion": "christian",
                "denomination": "roman_catholic",
            }
            if source["position"] is not None:
                church["position"] = source["position"]
            previous = churches.get(church_uuid)
            if previous is not None:
                if previous["name"] != church["name"] or (
                    "position" in previous
                    and "position" in church
                    and previous["position"] != church["position"]
                ):
                    raise ValueError(f"Conflicting church details across postcodes: {source['id']}")
                if "position" not in church and "position" in previous:
                    church["position"] = previous["position"]
            churches[church_uuid] = church
            target = services.setdefault(church_uuid, {})
            for service in entry["services"]:
                key = json.dumps(service, sort_keys=True, ensure_ascii=False)
                target[key] = service

    return {
        "churches": [
            church for church in sorted(churches.values(), key=lambda church: church["uuid"])
        ],
        "services": {
            church_id: [
                {field: service[field] for field in ("language", "start_time", "date")}
                for service in sorted(
                    church_services.values(),
                    key=lambda service: (
                        service["date"],
                        service["start_time"],
                        service["language"],
                    ),
                )
            ]
            for church_id, church_services in services.items()
        },
    }
