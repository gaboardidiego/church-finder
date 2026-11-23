"""Read Ember's country directories and expand its Mass recurrence rules."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import sqlite3
import time
import uuid
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from datetime import time as wall_time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.parser import isoparse
from dateutil.rrule import rrulestr

from ..websites import website_url

LOG = logging.getLogger("ember")
BASE_URL = "https://ember-mass-times.dpgu.workers.dev/churches/index"
NAMESPACE = uuid.UUID("5187b4b1-f81e-4e16-bd58-c5437cbb2e95")
MAX_AGE = timedelta(days=1)
HORIZON_DAYS = 30
# Includes European microstates, dependencies, and transcontinental countries.
# Austria is imported separately from Gottesdienst.at.
EUROPE_COUNTRIES = tuple(
    "AL AD AM AX AZ BY BE BA BG HR CY CZ DK EE FO FI FR GE DE GI GR GG HU IS IE IM IT "
    "JE XK LV LI LT LU MT MD MC ME NL MK NO PL PT RO RU SM RS SK SI ES SJ SE CH TR UA GB VA".split()
)
LANGUAGES = {
    "it": "Italian",
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "la": "Latin",
    "pl": "Polish",
    "pt": "Portuguese",
    "fil": "Filipino",
    "lt": "Lithuanian",
}


class EmberClient:
    def __init__(self, interval: float) -> None:
        if not math.isfinite(interval) or interval < 1:
            raise ValueError("Request interval must be at least one second")
        self.interval = interval
        self.last_request: float | None = None

    def page(self, after: str, country: str = "IT") -> dict:
        params = {"country": country, "full": "1", "limit": "1000"}
        if after:
            params["after"] = after
        if self.last_request is not None:
            delay = self.interval - (time.monotonic() - self.last_request)
            if delay > 0:
                time.sleep(delay)
        self.last_request = time.monotonic()
        request = Request(
            BASE_URL + "?" + urlencode(params),
            headers={"User-Agent": "church-finder/1.0", "Accept": "application/json"},
        )
        with urlopen(request, timeout=60) as response:
            value = json.load(response)
        if not isinstance(value, dict):
            raise ValueError("Invalid Ember page: expected an object")
        return value


def _date(value: str) -> date:
    parsed = isoparse(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC)
    return parsed.date()


def _date_list(value: object) -> set[date]:
    if value is None or value == "":
        return set()
    if not isinstance(value, str):
        raise ValueError("Ember recurrence dates must be strings")
    try:
        return {_date(item.strip()) for item in value.split(",") if item.strip()}
    except (ValueError, OverflowError) as error:
        raise ValueError(f"Invalid Ember recurrence date: {value!r}") from error


def _rule(value: str, today: date):
    lines = value.replace("\r\n", "\n").split("\n")
    normalized = []
    for line in lines:
        if line.upper().startswith("DTSTART"):
            head, separator, raw = line.partition(":")
            if not separator or (";" in head and head.upper() != "DTSTART;VALUE=DATE"):
                raise ValueError(f"Unsupported Ember DTSTART: {line}")
            try:
                start = _date(raw)
            except (ValueError, OverflowError) as error:
                raise ValueError(f"Invalid Ember DTSTART: {line}") from error
            normalized.append(f"DTSTART:{start:%Y%m%d}T000000Z")
        else:
            parts = line.split(";")
            for index, part in enumerate(parts):
                if part.upper().startswith("UNTIL="):
                    try:
                        until = _date(part.split("=", 1)[1])
                    except (ValueError, OverflowError) as error:
                        raise ValueError(f"Invalid Ember UNTIL: {part}") from error
                    parts[index] = f"UNTIL={until:%Y%m%d}T000000Z"
                if part.upper().startswith(("BYHOUR=", "BYMINUTE=", "BYSECOND=")):
                    raise ValueError(f"Unsupported time-based Ember recurrence: {part}")
            normalized.append(";".join(parts))
    text = "\n".join(normalized)
    if not re.search(r"(?:^|[:;])FREQ=(DAILY|WEEKLY|MONTHLY|YEARLY)(?:;|$)", text, re.I):
        raise ValueError(f"Unsupported Ember recurrence: {value}")
    try:
        return rrulestr(text, dtstart=datetime.combine(today, wall_time.min, UTC), forceset=True)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"Invalid Ember recurrence: {value}") from error


def expand_mass(service: dict, today: date) -> list[dict[str, str]]:
    rule, start = service.get("rrule"), service.get("startTime")
    if (
        not isinstance(rule, str)
        or not isinstance(start, str)
        or not re.fullmatch(r"\d{2}:\d{2}", start)
    ):
        raise ValueError("Ember Mass must have a recurrence and HH:MM start time")
    try:
        wall_time.fromisoformat(start)
    except ValueError as error:
        raise ValueError(f"Invalid Ember Mass time: {start}") from error
    language = service.get("language")
    if language is not None and not isinstance(language, str):
        raise ValueError("Invalid Ember service language")
    code = (language or "").strip().lower()
    language = LANGUAGES.get(code, code or "Unknown")
    exceptions = _date_list(service.get("exdate"))
    additions = _date_list(service.get("rdate"))
    end = today + timedelta(days=HORIZON_DAYS)
    dates = set(additions)
    recurrence = _rule(rule, today)
    try:
        for index, occurrence in enumerate(
            recurrence.xafter(datetime.combine(today, wall_time.min, UTC), count=1001, inc=True)
        ):
            if occurrence.date() >= end:
                break
            if index == 1000:
                raise ValueError("Ember recurrence has too many occurrences")
            dates.add(occurrence.date())
    except (TypeError, OverflowError) as error:
        raise ValueError(f"Invalid Ember recurrence: {rule}") from error
    return [
        {"date": day.isoformat(), "start_time": start, "language": language}
        for day in sorted(dates - exceptions)
        if today <= day < end
    ]


def normalize_church(source: dict, now: datetime, country: str = "IT") -> dict | None:
    church_id, name = source.get("id"), source.get("name")
    if (
        not isinstance(church_id, str)
        or not church_id
        or not isinstance(name, str)
        or not name.strip()
    ):
        raise ValueError("Invalid Ember church identity")
    if source.get("countryCode") != country:
        raise ValueError(f"Unexpected Ember country for {church_id}: {source.get('countryCode')}")
    status = source.get("status")
    if status in ("closed", "temporarily_closed"):
        return None
    if status not in (None, "active"):
        raise ValueError(f"Unexpected Ember church status for {church_id}: {status}")
    latitude, longitude = source.get("lat"), source.get("lng")
    if (
        isinstance(latitude, bool)
        or isinstance(longitude, bool)
        or not isinstance(latitude, (int, float))
        or not isinstance(longitude, (int, float))
        or not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        raise ValueError(f"Invalid Ember coordinates for {church_id}")
    timezone = source.get("timezone")
    if not isinstance(timezone, str):
        raise ValueError(f"Missing Ember timezone for {church_id}")
    try:
        today = now.astimezone(ZoneInfo(timezone)).date()
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"Unknown Ember timezone for {church_id}: {timezone}") from error
    church_uuid = str(uuid.uuid5(NAMESPACE, church_id))
    church = {
        "uuid": church_uuid,
        "name": name.strip(),
        "position": {"latitude": latitude, "longitude": longitude},
        "religion": "christian",
        "denomination": "roman_catholic",
        "region": (
            ("italy-ember-" if country == "IT" else f"ember-{country.lower()}-")
            + hashlib.sha256(church_id.encode()).hexdigest()[:2]
        ),
        "schedule_source": "ember",
    }
    verified = source.get("lastVerifiedAt")
    if verified is not None:
        if not isinstance(verified, str):
            raise ValueError(f"Invalid Ember verification date for {church_id}")
        try:
            church["last_verified_at"] = _date(verified).isoformat()
        except (ValueError, OverflowError) as error:
            raise ValueError(f"Invalid Ember verification date for {church_id}") from error
    links = source.get("links")
    if links is not None and not isinstance(links, list):
        raise ValueError(f"Invalid Ember links for {church_id}")
    for link in links or []:
        if isinstance(link, dict) and link.get("kind") == "website":
            website = website_url(link.get("url"))
            if website:
                church["website"] = website
                break
    raw_services = source.get("services")
    if raw_services is not None and not isinstance(raw_services, list):
        raise ValueError(f"Invalid Ember services for {church_id}")
    services = set()
    for service in raw_services or []:
        if not isinstance(service, dict) or service.get("kind") not in (
            "mass",
            "confession",
            "adoration",
        ):
            raise ValueError(f"Invalid Ember service for {church_id}")
        if service["kind"] == "mass":
            for row in expand_mass(service, today):
                services.add((row["date"], row["start_time"], row["language"]))
    return {
        "church": church,
        "services": [
            {"date": day, "start_time": start, "language": language}
            for day, start, language in sorted(services)
        ],
    }


def compact_page(page: dict, after: str) -> dict:
    churches = page.get("churches")
    next_cursor = page.get("next")
    if not isinstance(churches, list) or (
        next_cursor is not None and not isinstance(next_cursor, str)
    ):
        raise ValueError("Invalid Ember directory page")
    compact = []
    previous = after
    for church in churches:
        if not isinstance(church, dict):
            raise ValueError("Invalid Ember church record")
        church_id = church.get("id")
        if not isinstance(church_id, str) or not church_id or church_id <= previous:
            raise ValueError("Ember directory page has duplicate or unordered identifiers")
        previous = church_id
        fields = (
            "id",
            "name",
            "countryCode",
            "lat",
            "lng",
            "timezone",
            "status",
            "lastVerifiedAt",
            "hasStructuredSchedule",
        )
        item = {field: church.get(field) for field in fields}
        services = church.get("services")
        if services is not None and not isinstance(services, list):
            raise ValueError(f"Invalid Ember services for {church_id}")
        if services is not None:
            if any(not isinstance(service, dict) for service in services):
                raise ValueError(f"Invalid Ember service for {church_id}")
            item["services"] = [
                {
                    field: service.get(field)
                    for field in ("kind", "rrule", "startTime", "language", "exdate", "rdate")
                }
                for service in services
            ]
        links = church.get("links")
        if links is not None and not isinstance(links, list):
            raise ValueError(f"Invalid Ember links for {church_id}")
        item["links"] = [
            {"kind": "website", "url": link.get("url")}
            for link in (links or [])
            if isinstance(link, dict) and link.get("kind") == "website"
        ]
        compact.append(item)
    if next_cursor is not None and (not next_cursor or not churches or next_cursor != previous):
        raise ValueError("Invalid Ember pagination cursor")
    return {"churches": compact, "next": next_cursor}


def import_database(
    state: Path, interval: float, *, fresh: bool = False, countries: tuple[str, ...] = ("IT",)
) -> dict:
    if (
        not countries
        or len(set(countries)) != len(countries)
        or any(country not in EUROPE_COUNTRIES for country in countries)
    ):
        raise ValueError("Invalid Ember country selection")
    client = EmberClient(interval)
    state.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(state)) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and not tables <= {"ember_pages", "ember_metadata"}:
            raise ValueError(f"Checkpoint belongs to another importer: {state}")
        db.execute("CREATE TABLE IF NOT EXISTS ember_metadata (key TEXT PRIMARY KEY, value TEXT)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS ember_pages "
            "(cursor TEXT PRIMARY KEY, fetched_at TEXT NOT NULL, data TEXT NOT NULL)"
        )
        version = db.execute("SELECT value FROM ember_metadata WHERE key='version'").fetchone()
        if version and version[0] != "1":
            raise ValueError("Unsupported Ember checkpoint version")
        db.execute("INSERT OR IGNORE INTO ember_metadata VALUES ('version', '1')")
        scope = json.dumps(countries)
        saved_scope = db.execute(
            "SELECT value FROM ember_metadata WHERE key='countries'"
        ).fetchone()
        # Checkpoints predating country selection contain Italian pages only.
        old_scope = (
            saved_scope[0]
            if saved_scope
            else (
                json.dumps(("IT",))
                if db.execute("SELECT 1 FROM ember_pages LIMIT 1").fetchone()
                else scope
            )
        )
        if old_scope != scope and not fresh:
            raise ValueError("Ember checkpoint has a different country selection; use --fresh")
        db.execute("INSERT OR REPLACE INTO ember_metadata VALUES ('countries', ?)", (scope,))
        cutoff = (datetime.now(UTC) - MAX_AGE).isoformat()
        if (
            fresh
            or db.execute(
                "SELECT 1 FROM ember_pages WHERE fetched_at < ? LIMIT 1", (cutoff,)
            ).fetchone()
        ):
            db.execute("DELETE FROM ember_pages")
        db.commit()
        pages = []
        for country in countries:
            cursor = ""
            seen: set[str] = set()
            page_number = 0
            while True:
                if cursor in seen:
                    raise ValueError("Ember pagination cursor repeated")
                seen.add(cursor)
                page_number += 1
                key = cursor if countries == ("IT",) else f"{country}:{cursor}"
                saved = db.execute(
                    "SELECT fetched_at, data FROM ember_pages WHERE cursor=?", (key,)
                ).fetchone()
                if saved:
                    fetched_at, data = saved
                    page = compact_page(json.loads(data), cursor)
                    LOG.info("Using cached Ember page %d for %s", page_number, country)
                else:
                    LOG.info("Fetching Ember page %d for %s", page_number, country)
                    page = compact_page(client.page(cursor, country), cursor)
                    fetched_at = datetime.now(UTC).isoformat()
                    db.execute(
                        "INSERT INTO ember_pages VALUES (?, ?, ?)",
                        (key, fetched_at, json.dumps(page, ensure_ascii=False)),
                    )
                    db.commit()
                pages.append((country, fetched_at, page))
                next_cursor = page["next"]
                if next_cursor is None:
                    break
                cursor = next_cursor
        cutoff = (datetime.now(UTC) - MAX_AGE).isoformat()
        if any(fetched_at < cutoff for _, fetched_at, _ in pages):
            raise ValueError("Ember checkpoint is stale; rerun to refresh it")
        now = datetime.now(UTC)
        churches, services = [], {}
        unscheduled = 0
        for country, _, page in pages:
            for record in page["churches"]:
                if not record.get("hasStructuredSchedule"):
                    unscheduled += 1
                result = normalize_church(record, now, country)
                if result is None:
                    continue
                church = result["church"]
                if church["uuid"] in services:
                    raise ValueError(f"Duplicate Ember church: {church['uuid']}")
                churches.append(church)
                services[church["uuid"]] = result["services"]
        if not churches:
            raise ValueError("Ember returned no usable churches; refusing to publish")
        LOG.info(
            "Prepared %d churches and %d Masses; %d churches have no structured schedule",
            len(churches),
            sum(map(len, services.values())),
            unscheduled,
        )
        return {"churches": churches, "services": services}
