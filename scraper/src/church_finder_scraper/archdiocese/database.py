from __future__ import annotations

import json
import uuid

from .config import NAMESPACE
from .processing import match_osm_website


def build_database(
    batches: list[dict],
    postcodes: list[str],
    languages: bool,
    osm_records: list[dict],
    tolerance_meters: float,
) -> dict:
    churches, services = {}, {}
    for batch in batches:
        for entry in batch["results"]:
            source = entry["church"]
            identity = source["id"] + "\0" + source["marker_addr"]
            church_uuid = str(uuid.uuid5(NAMESPACE, identity))
            church = {
                "uuid": church_uuid,
                "name": source["name"],
                "religion": "christian",
                "denomination": "roman_catholic",
                "source_id": source["id"],
                "address": source["address"],
            }
            if source["position"] is not None:
                church["position"] = source["position"]
                osm_match = match_osm_website(source["position"], osm_records, tolerance_meters)
                if osm_match is not None:
                    church["website"] = osm_match["website"].strip()
                    church["osm_url"] = osm_match["osm_url"]
            if church_uuid in churches and churches[church_uuid] != church:
                raise ValueError(f"Conflicting church details across postcodes: {identity!r}")
            churches[church_uuid] = church
            target = services.setdefault(church_uuid, {})
            for service in entry["services"]:
                target[json.dumps(service, sort_keys=True, ensure_ascii=False)] = service
    compact_churches = [
        {
            field: church[field]
            for field in ("uuid", "name", "website", "position", "religion", "denomination")
            if field in church
        }
        for church in sorted(churches.values(), key=lambda church: church["uuid"])
    ]
    compact_services = {
        church_id: [
            {field: service[field] for field in ("language", "start_time", "date")}
            for service in sorted(
                church_services.values(),
                key=lambda service: (
                    service["date"],
                    service["start_time"],
                    service["language"],
                    service["service_type"],
                ),
            )
        ]
        for church_id, church_services in services.items()
    }
    return {"churches": compact_churches, "services": compact_services}
