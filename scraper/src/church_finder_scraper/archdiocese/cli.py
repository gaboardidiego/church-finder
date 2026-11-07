from __future__ import annotations

import argparse
import logging
import math
import re
import sqlite3
from pathlib import Path
from urllib.request import Request, urlopen

from playwright.sync_api import Error as PlaywrightError

from ..osm import OVERPASS_URL
from . import __doc__ as package_description
from .config import LOG, OSM_WEBSITE_TOLERANCE_METERS, POSTCODES, ROOT
from .importer import ImportOptions, import_database
from .processing import candidate_postcodes


def parse_args() -> argparse.Namespace:
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
        help=(
            "maximum distance for attaching an OSM website "
            f"(default: {OSM_WEBSITE_TOLERANCE_METERS})"
        ),
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
    if args.state.resolve() == args.website_output.resolve():
        parser.error("--state and --website-output must be different files")
    if args.postcode:
        postcodes = sorted(set(args.postcode))
        if any(not re.fullmatch(r"\d{4}", postcode) for postcode in postcodes):
            parser.error("postcodes must contain exactly four digits")
    return args


def main() -> int:
    args = parse_args()
    if args.postcode:
        postcodes = sorted(set(args.postcode))
    else:
        LOG.info("Downloading GeoNames postcode list from %s", POSTCODES)
        request = Request(POSTCODES, headers={"User-Agent": "church-finder/1.0 postcode importer"})
        with urlopen(request, timeout=30) as response:
            regions = ("Wien",) if args.vienna_only else ("Wien", "Niederösterreich")
            postcodes = candidate_postcodes(response.read(), regions)
        LOG.info("Loaded %d candidate postcodes", len(postcodes))
    import_database(
        ImportOptions(
            postcodes=postcodes,
            languages=not args.no_languages,
            interval=args.interval,
            osm_endpoint=args.osm_endpoint,
            osm_timeout=args.osm_timeout,
            osm_retries=args.osm_retries,
            osm_tolerance_meters=args.osm_tolerance_meters,
            output=args.output,
            website_output=args.website_output,
            state=args.state,
        )
    )
    return 0


def run() -> int:
    try:
        return main()
    except (OSError, ValueError, RuntimeError, sqlite3.Error, PlaywrightError) as error:
        LOG.error("%s", error)
        return 1
