from __future__ import annotations

import math
from collections import defaultdict
from itertools import product
from urllib.parse import urlsplit

from .config import LOG
from .osm.fetch import fetch_records

AUSTRIA_OVERPASS_QUERY = """[out:json][timeout:180];
area["ISO3166-1"="AT"]["admin_level"="2"]->.austria;
(
  nwr["amenity"="place_of_worship"]["religion"="christian"](area.austria);
  nwr["building"="church"](area.austria);
);
out center tags;
"""

EARTH_RADIUS = 6_371_000
TOLERANCE_METERS = 50
AMBIGUITY_METERS = 5

Point = tuple[float, float, float]
Cell = tuple[int, int, int]
WebsiteIndex = dict[Cell, list[tuple[Point, str | None]]]


def fetch_austria_records() -> list[dict]:
    return fetch_records(query=AUSTRIA_OVERPASS_QUERY)


def _coordinates(latitude, longitude) -> Point | None:
    try:
        latitude, longitude = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return None
    if not (
        math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    ):
        return None
    lat, lon = math.radians(latitude), math.radians(longitude)
    return (
        EARTH_RADIUS * math.cos(lat) * math.cos(lon),
        EARTH_RADIUS * math.cos(lat) * math.sin(lon),
        EARTH_RADIUS * math.sin(lat),
    )


def _website(record: dict) -> str | None:
    tags = record.get("tags") or {}
    for value in (record.get("website"), tags.get("contact:website")):
        if not isinstance(value, str):
            continue
        value = value.strip()
        if not value or any(char.isspace() or char in ";,\\<>" for char in value):
            continue
        if "://" not in value:
            value = "https://" + value
        try:
            parsed = urlsplit(value)
            if (
                parsed.scheme.lower() in {"http", "https"}
                and parsed.hostname
                and "." in parsed.hostname
                and parsed.username is None
                and parsed.password is None
                and parsed.port != 0
            ):
                return value
        except ValueError:
            continue
    return None


def _cell(point: Point) -> Cell:
    return (
        math.floor(point[0] / TOLERANCE_METERS),
        math.floor(point[1] / TOLERANCE_METERS),
        math.floor(point[2] / TOLERANCE_METERS),
    )


def _index_websites(records: list[dict]) -> WebsiteIndex:
    index: WebsiteIndex = defaultdict(list)
    for record in records:
        point = _coordinates(record.get("latitude"), record.get("longitude"))
        if point is not None:
            index[_cell(point)].append((point, _website(record)))
    return index


def _match_website(point: Point, index: WebsiteIndex) -> str | None:
    cell = _cell(point)
    candidates = []
    for offset in product((-1, 0, 1), repeat=3):
        neighbor = tuple(coordinate + delta for coordinate, delta in zip(cell, offset, strict=True))
        for other, website in index.get(neighbor, ()):
            distance = math.dist(point, other)
            if distance <= TOLERANCE_METERS:
                candidates.append((distance, website))
    if not candidates:
        return None
    candidates.sort(key=lambda candidate: candidate[0])
    distance, website = candidates[0]
    if website is None or any(
        other_website != website and other_distance - distance < AMBIGUITY_METERS
        for other_distance, other_website in candidates[1:]
    ):
        return None
    return website


def enrich_websites(database: dict, records: list[dict]) -> None:
    index = _index_websites(records)
    matched = 0
    for church in database["churches"]:
        position = church.get("position")
        if position is None:
            continue
        point = _coordinates(position.get("latitude"), position.get("longitude"))
        if point is None:
            continue
        website = _match_website(point, index)
        if website is None:
            continue
        church["website"] = website
        matched += 1
    LOG.info("Matched OSM websites for %d/%d locations", matched, len(database["churches"]))
