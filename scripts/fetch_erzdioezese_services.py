#!/usr/bin/env python3
"""Export the Vienna archdiocese's postcode-search results to a JSON database."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import logging
import math
import re
import sqlite3
import sys
import tempfile
import time
import uuid
import zipfile
from datetime import date, datetime, time as local_time, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright
from fetch_vienna_churches import OVERPASS_URL, fetch_records as fetch_osm_records

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://www.erzdioezese-wien.at/site/gottesdienstsuche"
POSTCODES = "https://download.geonames.org/export/zip/AT.zip"
POPUP = "https://www.erzdioezese-wien.at/site/cust_edwnews_gottesdienste_search_popup.siteswift"
NAMESPACE = uuid.UUID("cc91fc06-05af-4f90-bd7d-5df3a8b0462f")
LOG = logging.getLogger("erzdioezese")
LANGUAGES = {
    "Deutsch": "German", "Englisch": "English", "Latein": "Latin",
    "Französisch": "French", "Spanisch": "Spanish", "Polnisch": "Polish",
    "Italienisch": "Italian", "Kroatisch": "Croatian", "Ukrainisch": "Ukrainian",
    "Rumänisch": "Romanian", "Ungarisch": "Hungarian", "Portugiesisch": "Portuguese",
    "Akan-sprachige Gemeinde": "Akan", "Albanisch": "Albanian", "Arabisch": "Arabic",
    "Armenisch": "Armenian", "Bengalisch": "Bengali", "Bulgarisch": "Bulgarian",
    "Chinesisch": "Chinese", "Hindi": "Hindi", "Igbo": "Igbo", "Indonesisch": "Indonesian",
    "Japanisch": "Japanese", "Kirchenslawisch": "Church Slavonic", "Koreanisch": "Korean",
    "Malayalam": "Malayalam", "Niederländisch": "Dutch", "Norwegisch": "Norwegian",
    "Russisch": "Russian", "Schwedisch": "Swedish", "Slowenisch": "Slovenian",
    "Slowakisch": "Slovak", "Swahili": "Swahili", "Tagalog": "Tagalog",
    "Tamilisch": "Tamil", "Tschechisch": "Czech", "Vietnamesisch": "Vietnamese",
}
OSM_WEBSITE_TOLERANCE_METERS = 50


def distance_meters(first: dict, second: dict) -> float | None:
    try:
        lat1, lon1 = float(first["latitude"]), float(first["longitude"])
        lat2, lon2 = float(second["latitude"]), float(second["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (lat1, lon1, lat2, lon2)):
        return None
    if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90 and -180 <= lon1 <= 180 and -180 <= lon2 <= 180):
        return None
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    delta_lat = lat2 - lat1
    delta_lon = math.radians(lon2 - lon1)
    haversine = (math.sin(delta_lat / 2) ** 2
                 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2)
    return 6_371_000 * 2 * math.asin(math.sqrt(min(1, haversine)))


def match_osm_website(position: dict | None, osm_records: list[dict],
                      tolerance_meters: float = OSM_WEBSITE_TOLERANCE_METERS) -> dict | None:
    if position is None or tolerance_meters < 0:
        return None
    candidates = []
    for record in osm_records:
        distance = distance_meters(position, {
            "latitude": record.get("latitude"),
            "longitude": record.get("longitude"),
        })
        if distance is not None and distance <= tolerance_meters:
            candidates.append((distance, record))
    candidates.sort(key=lambda candidate: candidate[0])
    if not candidates:
        return None
    if len(candidates) > 1 and candidates[1][0] - candidates[0][0] < 5:
        LOG.warning(
            "OSM website match is ambiguous (nearest features %.1f m and %.1f m away)",
            candidates[0][0], candidates[1][0],
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
            marker.select_one(".title"), marker.select_one(".address"),
            marker.select_one(".marker_addr"),
        )
        if not match or name is None or address is None or marker_addr is None:
            raise ValueError("Malformed church search result")
        results.append({
            "id": match.group(1), "name": name.get_text(" ", strip=True),
            "address": address.get_text(" ", strip=True),
            "marker_addr": marker_addr.get_text(" ", strip=True),
        })
    if not results and "Für Ihre Suche wurden keine Gottsdienste gefunden" not in soup.get_text(" ", strip=True):
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
    languages = [str(option.get("value")) for option in select.select("option[value]")
                 if option.get("value")]
    defaults = {"gd_plz": "", "gd_search_type": "plz", "wochentag": "",
                "sprache": "", "festtag": "", "art": "", "date_begin": "",
                "time_begin": ""}
    return results, urljoin(POPUP, str(form["action"])), languages, defaults


def service_key(row: dict) -> str:
    fields = ("coid", "datum", "uhrzeit", "art", "art_erweitert", "kurzinfo",
              "beschreibung", "loc_title", "loc_adresse", "loc_plz", "loc_ort")
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
        if (not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day)
                or not isinstance(start, str) or not re.fullmatch(r"\d{2}:\d{2}(?::\d{2})?", start)):
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
            result.append({
                "date": row["datum"], "start_time": row["uhrzeit"][:5],
                "language": LANGUAGES.get(language, language),
                "service_type": row.get("art", ""), "description": row.get("beschreibung", ""),
                "service_type_details": row.get("art_erweitert", ""),
                "short_info": row.get("kurzinfo", ""),
            })
    return result


class Client:
    def __init__(self, context, site_id: str, token: str, interval: float):
        self.context, self.site_id, self.token = context, site_id, token
        self.interval, self.last_request = interval, 0.0
        self.request_count = 0

    def request(self, method: str, url: str, **kwargs):
        for attempt in range(3):
            time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            self.request_count += 1
            started = time.monotonic()
            LOG.info("Request %d: %s %s (attempt %d/3)", self.request_count, method,
                     urlsplit(url).path, attempt + 1)
            response = self.context.request.fetch(url, method=method, timeout=30000, **kwargs)
            elapsed = time.monotonic() - started
            LOG.info("Request %d completed: HTTP %d in %.1f seconds",
                     self.request_count, response.status, elapsed)
            if response.ok:
                return response
            if response.status not in {429, 500, 502, 503, 504} or attempt == 2:
                raise RuntimeError(f"{method} {urlsplit(url).path}: HTTP {response.status}")
            delay = 2 ** (attempt + 1)
            LOG.warning("HTTP %s, retrying in %s seconds", response.status, delay)
            time.sleep(delay)
        raise RuntimeError("Request retry limit reached")

    def postcode(self, postcode: str, use_languages: bool) -> list[dict]:
        params = {"do": "all", "c": "getfind", "s": self.site_id, "t": self.token,
                  "d": f"gd_plz:{postcode};gd_search_type:plz"}
        html = self.request("GET", POPUP, params=params).text()
        churches, action, languages, defaults = parse_search(html)
        if not churches:
            return []
        action_url = urlsplit(action)
        if action_url.scheme != "https" or action_url.netloc != urlsplit(SOURCE).netloc:
            raise ValueError("Unexpected search form host")
        dates_url = POPUP + (
            f"?so=site_gottesdienstsuche_search_popup&do=site_gottesdienstsuche_search_popup"
            f"&c=xhr_dates_for_coid&s={self.site_id}&t={self.token}"
        )
        records = {}
        for index, church in enumerate(churches, start=1):
            identity = (church["id"], church["marker_addr"])
            if identity in records:
                raise ValueError(f"Duplicate church result: {identity}")
            LOG.info("%s: fetching services for church %d/%d: %s (%s)",
                     postcode, index, len(churches), church["name"], church["id"])
            response = self.request("POST", dates_url, form={
                "coid": church["id"], "addr": church["marker_addr"],
            })
            records[identity] = {"church": church, "rows": parse_services(response.json(), church["id"]),
                                 "matches": {}}
        if use_languages:
            for language_index, language in enumerate(languages, start=1):
                LOG.info("%s: checking language %d/%d: %s", postcode,
                         language_index, len(languages), language)
                form = {**defaults, "gd_plz": postcode, "sprache": language}
                filtered_html = self.request("POST", action, form=form).text()
                filtered, _, _, _ = parse_search(filtered_html)
                LOG.info("%s: language %s matched %d church result(s)",
                         postcode, language, len(filtered))
                for church in filtered:
                    identity = (church["id"], church["marker_addr"])
                    if identity not in records:
                        raise ValueError(f"Filtered search returned an unknown church: {identity}")
                    data = self.request("POST", dates_url, form={
                        "coid": church["id"], "addr": church["marker_addr"],
                    }).json()
                    rows = parse_services(data, church["id"])
                    entry = records[identity]
                    baseline = {service_key(row) for row in entry["rows"]}
                    filtered_counts = {}
                    for row in rows:
                        key = service_key(row)
                        filtered_counts[key] = filtered_counts.get(key, 0) + 1
                    for row in rows:
                        key = service_key(row)
                        if key not in baseline:
                            raise ValueError(f"Filtered service not in baseline for {identity}")
                        if filtered_counts[key] == 1:
                            entry["matches"].setdefault(key, set()).add(language)
        return [
            {"church": entry["church"],
             "services": normalize_services(entry["rows"], entry["matches"])}
            for entry in records.values()
        ]


def build_database(batches: list[dict], postcodes: list[str], languages: bool,
                   osm_records: list[dict], tolerance_meters: float) -> dict:
    churches, services = {}, {}
    for batch in batches:
        for entry in batch["results"]:
            source = entry["church"]
            identity = source["id"] + "\0" + source["marker_addr"]
            church_uuid = str(uuid.uuid5(NAMESPACE, identity))
            church = {"uuid": church_uuid, "name": source["name"],
                      "religion": "christian", "denomination": "roman_catholic",
                      "source_id": source["id"], "address": source["address"]}
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
        {field: church[field] for field in (
            "uuid", "name", "website", "position", "religion", "denomination"
        ) if field in church}
        for church in sorted(churches.values(), key=lambda church: church["uuid"])
    ]
    compact_services = {
        church_id: [
            {field: service[field] for field in ("language", "start_time", "date")}
            for service in sorted(
                church_services.values(),
                key=lambda service: (
                    service["date"], service["start_time"], service["language"],
                    service["service_type"],
                ),
            )
        ]
        for church_id, church_services in services.items()
    }
    return {"churches": compact_churches, "services": compact_services}


def connect_state(path: Path, postcodes: list[str], languages: bool) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS results (postcode TEXT PRIMARY KEY, data TEXT NOT NULL)")
    config = json.dumps({"version": 2, "postcodes": postcodes, "languages": languages})
    fingerprint = hashlib.sha256(config.encode()).hexdigest()
    stored = db.execute("SELECT value FROM metadata WHERE key='fingerprint'").fetchone()
    if stored and stored[0] != fingerprint:
        db.close()
        raise ValueError("Checkpoint options differ; use a new --state path")
    db.execute("INSERT OR IGNORE INTO metadata VALUES ('fingerprint', ?)", (fingerprint,))
    db.commit()
    return db


def start_session(page):
    LOG.info("Opening diocesan Gottesdienstsuche in Chromium")
    page.goto(SOURCE, wait_until="domcontentloaded", timeout=30000)
    notice = page.locator("#klaro .cookie-notice")
    if notice.is_visible(timeout=2000):
        LOG.info("Enabling only Google Maps consent needed for search results")
        notice.get_by_role("button", name=re.compile("further information|weitere information", re.I)).click()
        checkbox = page.locator("#service-item-googlemaps")
        checkbox.check(force=True)
        page.locator("#klaro .cm-modal").get_by_role(
            "button", name=re.compile("accept selected|save|ausgewählte|auswahl|speichern", re.I)
        ).click(no_wait_after=True)
        page.wait_for_timeout(1500)
    LOG.info("Reading current search session parameters")
    form = page.locator("#gd_searchForm")
    form.wait_for(state="attached", timeout=30000)
    action = form.get_attribute("action")
    if not action:
        raise ValueError("Search form action missing")
    query = parse_qs(urlsplit(action).query)
    if len(query.get("s", [])) != 1 or len(query.get("t", [])) != 1:
        raise ValueError("Search session parameters missing")
    return query["s"][0], query["t"][0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consent-google-maps", action="store_true",
                        help="allow the site's Google Maps consent needed for its search")
    postcode_group = parser.add_mutually_exclusive_group()
    postcode_group.add_argument("--postcode", action="append",
                                help="limit to a postcode; repeatable")
    postcode_group.add_argument("--vienna-only", action="store_true",
                                help="automatically search all GeoNames postcodes in Vienna")
    parser.add_argument("--no-languages", action="store_true",
                        help="skip the costly language-filter searches; use Unknown")
    parser.add_argument("--interval", type=float, default=1.0,
                        help="minimum seconds between diocese requests (default: 1)")
    parser.add_argument("--osm-endpoint", default=OVERPASS_URL,
                        help="Overpass endpoint for fetching OSM church websites")
    parser.add_argument("--osm-timeout", type=int, default=200,
                        help="Overpass request timeout in seconds (default: 200)")
    parser.add_argument("--osm-retries", type=int, default=2,
                        help="Overpass retries per endpoint (default: 2)")
    parser.add_argument("--osm-tolerance-meters", type=float,
                        default=OSM_WEBSITE_TOLERANCE_METERS,
                        help="maximum distance for attaching an OSM website (default: 100)")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/databases/erzdioezese_wien.database.json")
    parser.add_argument("--state", type=Path,
                        default=ROOT / "data/databases/erzdioezese_wien.checkpoint.sqlite")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if not args.consent_google_maps:
        parser.error("--consent-google-maps is required to use the site's search")
    if not math.isfinite(args.interval) or args.interval < 0.5:
        parser.error("--interval must be at least 0.5 seconds")
    if not math.isfinite(args.osm_tolerance_meters) or args.osm_tolerance_meters < 0:
        parser.error("--osm-tolerance-meters cannot be negative")
    if args.osm_timeout <= 0 or args.osm_retries < 0:
        parser.error("--osm-timeout must be positive and --osm-retries cannot be negative")
    if args.output.resolve() == args.state.resolve():
        parser.error("--output and --state must be different files")
    if args.postcode:
        postcodes = sorted(set(args.postcode))
        if any(not re.fullmatch(r"\d{4}", postcode) for postcode in postcodes):
            parser.error("postcodes must contain exactly four digits")
    else:
        LOG.info("Downloading GeoNames postcode list from %s", POSTCODES)
        request = Request(POSTCODES, headers={"User-Agent": "church-finder/1.0 postcode importer"})
        with urlopen(request, timeout=30) as response:
            regions = ("Wien",) if args.vienna_only else ("Wien", "Niederösterreich")
            postcodes = candidate_postcodes(response.read(), regions)
        LOG.info("Loaded %d candidate postcodes", len(postcodes))
    with contextlib.closing(connect_state(args.state, postcodes, not args.no_languages)) as db:
        completed = {row[0] for row in db.execute("SELECT postcode FROM results")}
        if completed - set(postcodes):
            raise ValueError("Checkpoint contains unexpected postcodes")
        LOG.info("Searching %d postcodes, %d already completed", len(postcodes), len(completed))
        LOG.info("Fetching Vienna church websites and coordinates from OSM")
        osm_records = fetch_osm_records(args.osm_endpoint, args.osm_timeout, args.osm_retries)
        website_records = [record for record in osm_records if record.get("website")]
        LOG.info("Fetched %d OSM records; %d include a website",
                 len(osm_records), len(website_records))
        if len(completed) < len(postcodes):
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    context = browser.new_context()
                    page = context.new_page()
                    site_id, token = start_session(page)
                    client = Client(context, site_id, token, args.interval)
                    LOG.info("Starting diocese search for %d postcodes", len(postcodes))
                    for postcode in postcodes:
                        if postcode in completed:
                            LOG.info("%s: already complete in checkpoint; skipping", postcode)
                            continue
                        LOG.info("%s: starting postcode search", postcode)
                        result = client.postcode(postcode, not args.no_languages)
                        batch = {"postcode": postcode,
                                 "completed_at": datetime.now(timezone.utc).isoformat(),
                                 "results": result}
                        db.execute("INSERT INTO results VALUES (?, ?)",
                                   (postcode, json.dumps(batch, ensure_ascii=False)))
                        db.commit()
                        LOG.info("%s: %d locations (%d/%d)", postcode, len(result),
                                 len(completed) + 1, len(postcodes))
                        completed.add(postcode)
                finally:
                    browser.close()
        batches = [json.loads(row[0]) for row in db.execute(
            "SELECT data FROM results ORDER BY postcode")]
        database = build_database(batches, postcodes, not args.no_languages,
                                  osm_records, args.osm_tolerance_meters)
        matched_websites = sum(bool(church.get("website")) for church in database["churches"])
        LOG.info("Matched OSM websites for %d/%d diocese locations",
                 matched_websites, len(database["churches"]))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent,
                                             prefix=args.output.name + ".", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(database, handle, ensure_ascii=False, separators=(",", ":"))
                handle.write("\n")
            temporary.replace(args.output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        LOG.info("Wrote %d locations and %d services to %s", len(database["churches"]),
                 sum(map(len, database["services"].values())), args.output)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, sqlite3.Error, PlaywrightError) as error:
        LOG.error("%s", error)
        sys.exit(1)
