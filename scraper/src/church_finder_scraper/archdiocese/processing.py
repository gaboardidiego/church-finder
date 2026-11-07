from __future__ import annotations

import io
import json
import math
import re
import zipfile
from datetime import date
from datetime import time as local_time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .config import LANGUAGES, LOG, OSM_WEBSITE_TOLERANCE_METERS, POPUP


def distance_meters(first: dict, second: dict) -> float | None:
    try:
        lat1, lon1 = float(first["latitude"]), float(first["longitude"])
        lat2, lon2 = float(second["latitude"]), float(second["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (lat1, lon1, lat2, lon2)):
        return None
    if not (
        -90 <= lat1 <= 90 and -90 <= lat2 <= 90 and -180 <= lon1 <= 180 and -180 <= lon2 <= 180
    ):
        return None
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    delta_lat = lat2 - lat1
    delta_lon = math.radians(lon2 - lon1)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 6_371_000 * 2 * math.asin(math.sqrt(min(1, haversine)))


def match_osm_website(
    position: dict | None,
    osm_records: list[dict],
    tolerance_meters: float = OSM_WEBSITE_TOLERANCE_METERS,
) -> dict | None:
    if position is None or tolerance_meters < 0:
        return None
    candidates = []
    for record in osm_records:
        distance = distance_meters(
            position,
            {
                "latitude": record.get("latitude"),
                "longitude": record.get("longitude"),
            },
        )
        if distance is not None and distance <= tolerance_meters:
            candidates.append((distance, record))
    candidates.sort(key=lambda candidate: candidate[0])
    if not candidates:
        return None
    if len(candidates) > 1 and candidates[1][0] - candidates[0][0] < 5:
        LOG.warning(
            "OSM website match is ambiguous (nearest features %.1f m and %.1f m away)",
            candidates[0][0],
            candidates[1][0],
        )
        return None
    website = candidates[0][1].get("website")
    return candidates[0][1] if isinstance(website, str) and website.strip() else None


def candidate_postcodes(
    payload: bytes,
    regions: tuple[str, ...] = ("Wien", "Niederösterreich"),
) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        rows = archive.read("AT.txt").decode("utf-8").splitlines()
    result = set()
    for row in rows:
        fields = row.split("\t")
        if len(fields) >= 4 and fields[3] in regions:
            if re.fullmatch(r"\d{4}", fields[1]):
                result.add(fields[1])
    if not result:
        raise ValueError("GeoNames returned no Vienna or Lower Austria postcodes")
    return sorted(result)


def parse_search(html: str) -> tuple[list[dict], str, list[str], dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one("#site_search_gottesdienste")
    if form is None or not form.get("action"):
        raise ValueError("Search form missing: consent, session, or site layout may have changed")
    results = []
    for marker in soup.select(".gdList .item .marker"):
        match = re.fullmatch(r"kirche_(\d+)", str(marker.get("id", "")))
        name, address, marker_addr = (
            marker.select_one(".title"),
            marker.select_one(".address"),
            marker.select_one(".marker_addr"),
        )
        if not match or name is None or address is None or marker_addr is None:
            raise ValueError("Malformed church search result")
        results.append(
            {
                "id": match.group(1),
                "name": name.get_text(" ", strip=True),
                "address": address.get_text(" ", strip=True),
                "marker_addr": marker_addr.get_text(" ", strip=True),
            }
        )
    if not results and "Für Ihre Suche wurden keine Gottsdienste gefunden" not in soup.get_text(
        " ", strip=True
    ):
        raise ValueError("Search returned neither churches nor the expected no-results message")
    coordinates = re.findall(
        r"new google\.maps\.LatLng\(\s*([-.\d]+)\s*,\s*([-.\d]+)\s*\)"
        r"\s*;\s*marker\s*=\s*createMarker\(\s*point\s*,\s*['\"](\d+)['\"]",
        html,
    )
    by_id = {}
    for lat, lon, church_id in coordinates:
        position = {"latitude": float(lat), "longitude": float(lon)}
        if not (-90 <= position["latitude"] <= 90 and -180 <= position["longitude"] <= 180):
            raise ValueError(f"Invalid coordinates for {church_id}")
        if church_id in by_id and by_id[church_id] != position:
            raise ValueError(f"Ambiguous coordinates for {church_id}")
        by_id[church_id] = position
    for item in results:
        item["position"] = by_id.get(item["id"])
    select = form.select_one('select[name="sprache"]')
    if select is None:
        raise ValueError("Language selector missing from search results")
    languages = [
        str(option.get("value")) for option in select.select("option[value]") if option.get("value")
    ]
    defaults = {
        "gd_plz": "",
        "gd_search_type": "plz",
        "wochentag": "",
        "sprache": "",
        "festtag": "",
        "art": "",
        "date_begin": "",
        "time_begin": "",
    }
    return results, urljoin(POPUP, str(form["action"])), languages, defaults


def service_key(row: dict) -> str:
    fields = (
        "coid",
        "datum",
        "uhrzeit",
        "art",
        "art_erweitert",
        "kurzinfo",
        "beschreibung",
        "loc_title",
        "loc_adresse",
        "loc_plz",
        "loc_ort",
    )
    return json.dumps([row.get(field, "") for field in fields], ensure_ascii=False)


def parse_services(payload: object, church_id: str) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("html"), str):
        raise ValueError("Malformed service response")
    rows = []
    for key, row in payload.items():
        if not str(key).isdigit():
            continue
        if not isinstance(row, dict) or str(row.get("coid")) != church_id:
            raise ValueError(f"Unexpected service church for {church_id}")
        day, start = row.get("datum"), row.get("uhrzeit")
        if (
            not isinstance(day, str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day)
            or not isinstance(start, str)
            or not re.fullmatch(r"\d{2}:\d{2}(?::\d{2})?", start)
        ):
            raise ValueError(f"Invalid date or time for {church_id}")
        date.fromisoformat(day)
        parsed = local_time.fromisoformat(start)
        if parsed.tzinfo is not None or parsed.second or parsed.microsecond:
            raise ValueError(f"Unsupported service time {start} for {church_id}")
        rows.append(row)
    return rows


def normalize_services(rows: list[dict], language_matches: dict[str, set[str]]) -> list[dict]:
    counts: dict[str, int] = {}
    for row in rows:
        key = service_key(row)
        counts[key] = counts.get(key, 0) + 1
    result = []
    for row in rows:
        key = service_key(row)
        languages = language_matches.get(key, set()) if counts[key] == 1 else set()
        for language in sorted(languages) if languages else ["Unknown"]:
            result.append(
                {
                    "date": row["datum"],
                    "start_time": row["uhrzeit"][:5],
                    "language": LANGUAGES.get(language, language),
                    "service_type": row.get("art", ""),
                    "description": row.get("beschreibung", ""),
                    "service_type_details": row.get("art_erweitert", ""),
                    "short_info": row.get("kurzinfo", ""),
                }
            )
    return result
