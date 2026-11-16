from __future__ import annotations

import json
import re
import uuid

from .config import LOG, NAMESPACE
from .regions import region_for_postcode


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
    postcodes: dict[str, tuple[set[str], set[str]]] = {}
    for batch in batches:
        for entry in batch["results"]:
            source = entry["church"]
            church_uuid = str(uuid.uuid5(NAMESPACE, source["id"]))
            churches[church_uuid] = _merge_church(source, church_uuid, churches.get(church_uuid))
            address_codes, search_codes = postcodes.setdefault(church_uuid, (set(), set()))
            address_codes.update(re.findall(r"(?<!\d)\d{4}(?!\d)", source.get("address", "")))
            if isinstance(batch.get("postcode"), str):
                search_codes.add(batch["postcode"])
            target = services.setdefault(church_uuid, {})
            for service in entry["services"]:
                key = json.dumps(service, sort_keys=True, ensure_ascii=False)
                target[key] = service

    for church_id, church in churches.items():
        if "position" not in church:
            address_codes, search_codes = postcodes[church_id]
            region = next(
                (region for code in sorted(address_codes) if (region := region_for_postcode(code))),
                None,
            ) or next(
                (region for code in sorted(search_codes) if (region := region_for_postcode(code))),
                None,
            )
            if region:
                church["region"] = region
                LOG.warning(
                    "No coordinates for church %s; using postcode region %s", church_id, region
                )
    return {
        "churches": sorted(churches.values(), key=lambda church: church["uuid"]),
        "services": {
            church_id: _sorted_services(church_services)
            for church_id, church_services in services.items()
        },
    }
