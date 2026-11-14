from __future__ import annotations

import math
import re
from datetime import datetime, time

from bs4 import BeautifulSoup

from .config import LANGUAGES, LOG


def _positions(html: str) -> dict[str, dict[str, float]]:
    pattern = (
        r"var point = new google\.maps\.LatLng\(\s*([-.\d]+)\s*,\s*([-.\d]+)\s*\);"
        r"(?:(?!var point\s*=).)*?markerId\s*=\s*[\"'](\d+)[\"']"
    )
    positions = {}
    for latitude, longitude, church_id in re.findall(pattern, html, re.S):
        position = {"latitude": float(latitude), "longitude": float(longitude)}
        if not (
            math.isfinite(position["latitude"])
            and math.isfinite(position["longitude"])
            and -90 <= position["latitude"] <= 90
            and -180 <= position["longitude"] <= 180
        ):
            raise ValueError(f"Invalid coordinates for {church_id}")
        if church_id in positions and positions[church_id] != position:
            raise ValueError(f"Ambiguous coordinates for {church_id}")
        positions[church_id] = position
    return positions


def _service_language(description: str) -> str:
    for source, target in LANGUAGES.items():
        if re.search(rf"(?<!\w){re.escape(source)}(?!\w)", description, re.I):
            return target
    return "Unknown"


def _parse_service(element, church_id: str) -> dict[str, str] | None:
    day = element.select_one(".weekday .daymonth")
    year = element.select_one(".weekday .year")
    details = element.select_one(".datum")
    clock = details.select_one("span") if details is not None else None
    if day is None or year is None or details is None or clock is None:
        raise ValueError("Malformed Gottesdienst.at service result")

    day_text = day.get_text(strip=True)
    year_text = year.get_text(strip=True)
    if not day_text and not year_text:
        LOG.warning(
            "Skipping undated Gottesdienst.at service for church %s: %s",
            church_id,
            details.get_text(" ", strip=True),
        )
        return None

    date_text = f"{day_text}{year_text}"
    if not day_text or not year_text:
        raise ValueError(
            f"Invalid Gottesdienst.at service date {date_text!r} for church {church_id}"
        )
    try:
        service_date = datetime.strptime(date_text, "%d.%m.%Y").date()
    except ValueError as error:
        raise ValueError(
            f"Invalid Gottesdienst.at service date {date_text!r} for church {church_id}"
        ) from error

    time_match = re.search(r"\b(\d{1,2}:\d{2})\b", clock.get_text(" ", strip=True))
    if time_match is None:
        raise ValueError("Invalid Gottesdienst.at service time")
    try:
        start_time = time.fromisoformat(time_match.group(1))
    except ValueError as error:
        raise ValueError("Invalid Gottesdienst.at service time") from error

    return {
        "date": service_date.isoformat(),
        "start_time": start_time.strftime("%H:%M"),
        "language": _service_language(details.get_text(" ", strip=True)),
    }


def _parse_church_result(item, positions: dict[str, dict[str, float]]) -> dict:
    marker = item.select_one(".marker")
    church_id_match = re.fullmatch(r"kirche_(\d+)", str(marker.get("id", ""))) if marker else None
    name = marker.select_one(".title") if marker else None
    address = marker.select_one(".address") if marker else None
    if church_id_match is None or name is None or address is None:
        raise ValueError("Malformed Gottesdienst.at church result")

    church_id = church_id_match.group(1)
    services = []
    for service in item.select(".gdItem"):
        parsed = _parse_service(service, church_id)
        if parsed is not None:
            services.append(parsed)
    return {
        "church": {
            "id": church_id,
            "name": name.get_text(" ", strip=True),
            "address": address.get_text(" ", strip=True),
            "position": positions.get(church_id),
        },
        "services": services,
    }


def parse_search(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one("#site_search_gottesdienste") is None:
        raise ValueError("Gottesdienst.at search form missing: consent or site layout changed")

    positions = _positions(html)
    return [
        _parse_church_result(item, positions) for item in soup.select("#gdList .resultList .item")
    ]
