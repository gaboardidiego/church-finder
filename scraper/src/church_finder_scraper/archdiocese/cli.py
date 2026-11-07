from __future__ import annotations

import argparse
import contextlib
import json
import logging
import math
import re
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from ..osm import OVERPASS_URL
from ..osm import fetch_records as fetch_osm_records
from . import __doc__ as package_description
from .browser import start_session
from .client import Client
from .config import LOG, OSM_WEBSITE_TOLERANCE_METERS, POSTCODES, ROOT
from .database import build_database
from .processing import candidate_postcodes
from .publish import publish_database
from .state import connect_state


def main() -> int:
    parser = argparse.ArgumentParser(description=package_description)
    parser.add_argument(
        "--consent-google-maps",
        action="store_true",
        help="allow the site's Google Maps consent needed for its search",
    )
    postcode_group = parser.add_mutually_exclusive_group()
    postcode_group.add_argument(
        "--postcode", action="append", help="limit to a postcode; repeatable"
    )
    postcode_group.add_argument(
        "--vienna-only",
        action="store_true",
        help="automatically search all GeoNames postcodes in Vienna",
    )
    parser.add_argument(
        "--no-languages",
        action="store_true",
        help="skip the costly language-filter searches; use Unknown",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="minimum seconds between diocese requests (default: 1)",
    )
    parser.add_argument(
        "--osm-endpoint",
        default=OVERPASS_URL,
        help="Overpass endpoint for fetching OSM church websites",
    )
    parser.add_argument(
        "--osm-timeout",
        type=int,
        default=200,
        help="Overpass request timeout in seconds (default: 200)",
    )
    parser.add_argument(
        "--osm-retries", type=int, default=2, help="Overpass retries per endpoint (default: 2)"
    )
    parser.add_argument(
        "--osm-tolerance-meters",
        type=float,
        default=OSM_WEBSITE_TOLERANCE_METERS,
        help="maximum distance for attaching an OSM website (default: 100)",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/databases/erzdioezese_wien.database.json"
    )
    parser.add_argument(
        "--website-output",
        type=Path,
        default=ROOT / "web/public/data/churches_vienna.database.json",
        help="website database path to update after scraping",
    )
    parser.add_argument(
        "--state", type=Path, default=ROOT / "data/databases/erzdioezese_wien.checkpoint.sqlite"
    )
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
    if args.output.resolve() == args.website_output.resolve():
        parser.error("--output and --website-output must be different files")
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
        LOG.info(
            "Fetched %d OSM records; %d include a website", len(osm_records), len(website_records)
        )
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
                        batch = {
                            "postcode": postcode,
                            "completed_at": datetime.now(UTC).isoformat(),
                            "results": result,
                        }
                        db.execute(
                            "INSERT INTO results VALUES (?, ?)",
                            (postcode, json.dumps(batch, ensure_ascii=False)),
                        )
                        db.commit()
                        LOG.info(
                            "%s: %d locations (%d/%d)",
                            postcode,
                            len(result),
                            len(completed) + 1,
                            len(postcodes),
                        )
                        completed.add(postcode)
                finally:
                    browser.close()
        batches = [
            json.loads(row[0]) for row in db.execute("SELECT data FROM results ORDER BY postcode")
        ]
        database = build_database(
            batches, postcodes, not args.no_languages, osm_records, args.osm_tolerance_meters
        )
        matched_websites = sum(bool(church.get("website")) for church in database["churches"])
        LOG.info(
            "Matched OSM websites for %d/%d diocese locations",
            matched_websites,
            len(database["churches"]),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=args.output.parent,
                prefix=args.output.name + ".",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                json.dump(database, handle, ensure_ascii=False, separators=(",", ":"))
                handle.write("\n")
            temporary.replace(args.output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        LOG.info(
            "Wrote %d locations and %d services to %s",
            len(database["churches"]),
            sum(map(len, database["services"].values())),
            args.output,
        )
        previous, current, backup_path = publish_database(
            args.output,
            args.website_output,
            ROOT / "backups",
        )
        if previous is None:
            LOG.info("Previous website database: none")
        else:
            LOG.info(
                "Previous website database: %d churches and %d services (backed up to %s)",
                previous[0],
                previous[1],
                backup_path,
            )
        LOG.info("New website database: %d churches and %d services", *current)
        LOG.info("Published website database to %s", args.website_output)
    return 0


def run() -> int:
    try:
        return main()
    except (OSError, ValueError, RuntimeError, sqlite3.Error, PlaywrightError) as error:
        LOG.error("%s", error)
        return 1
