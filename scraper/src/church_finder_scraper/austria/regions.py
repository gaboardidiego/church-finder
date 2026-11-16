"""Assign locations to Austrian federal states using local boundary data."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

REGIONS = {
    "1": "burgenland",
    "2": "kaernten",
    "3": "niederoesterreich",
    "4": "oberoesterreich",
    "5": "salzburg",
    "6": "steiermark",
    "7": "tirol",
    "8": "vorarlberg",
    "9": "wien",
}


@lru_cache(maxsize=1)
def _boundaries() -> list[dict]:
    path = Path(__file__).parent / "data" / "austria-states.geojson"
    return json.loads(path.read_text(encoding="utf-8"))["features"]


def _inside_ring(x: float, y: float, ring: list) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:], strict=False):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _distance_to_ring(x: float, y: float, ring: list) -> float:
    scale = math.cos(math.radians(y))
    x *= scale
    best = math.inf
    for (x1, y1), (x2, y2) in zip(ring, ring[1:], strict=False):
        x1 *= scale
        x2 *= scale
        dx, dy = x2 - x1, y2 - y1
        length = dx * dx + dy * dy
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / length)) if length else 0
        best = min(best, (x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2)
    return best


def region_for_position(position: object) -> str | None:
    if not isinstance(position, dict):
        return None
    latitude = position.get("latitude")
    longitude = position.get("longitude")
    if (
        not isinstance(latitude, (int, float))
        or not isinstance(longitude, (int, float))
        or not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or abs(latitude) > 90
        or abs(longitude) > 180
    ):
        return None
    for feature in _boundaries():
        region = REGIONS[feature["properties"]["iso"]]
        for polygon in feature["geometry"]["coordinates"]:
            if _inside_ring(longitude, latitude, polygon[0]) and not any(
                _inside_ring(longitude, latitude, hole) for hole in polygon[1:]
            ):
                return region
    return min(
        (_distance_to_ring(longitude, latitude, ring), REGIONS[feature["properties"]["iso"]])
        for feature in _boundaries()
        for polygon in feature["geometry"]["coordinates"]
        for ring in polygon
    )[1]


def region_for_postcode(postcode: str) -> str | None:
    if len(postcode) != 4 or not postcode.isascii() or not postcode.isdigit():
        return None
    code = int(postcode)
    if 9900 <= code <= 9999 or 6000 <= code <= 6699:
        return "tirol"
    if 6700 <= code <= 6999:
        return "vorarlberg"
    return {
        "1": "wien",
        "2": "niederoesterreich",
        "3": "niederoesterreich",
        "4": "oberoesterreich",
        "5": "salzburg",
        "7": "burgenland",
        "8": "steiermark",
        "9": "kaernten",
    }.get(postcode[0])
