from __future__ import annotations

import argparse
import logging
import math
import re
import sqlite3
from pathlib import Path
from urllib.request import Request, urlopen

from playwright.sync_api import Error as PlaywrightError

from ..paths import PROJECT_ROOT
from .config import LOG
from .importer import ImportOptions, import_database
from .postcodes import AUSTRIAN_REGIONS, POSTCODES, candidate_postcodes
from .publish import publish_database


def parse_args(
    argv: list[str] | None = None, *, parent_parser: argparse.ArgumentParser | None = None
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Austrian church services from Gottesdienst.at",
        parents=[parent_parser] if parent_parser else [],
    )
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
        "--vienna-only", action="store_true", help="search only Vienna postcodes"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="minimum seconds between service-source requests (default: 1)",
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "web/public/data/churches_vienna.database.json",
        help="website database path to update after scraping",
    )
    output_group.add_argument(
        "--website-output",
        dest="output",
        type=Path,
        help="alias for --output",
    )
    parser.add_argument(
        "--state",
        "--nationwide-state",
        type=Path,
        default=PROJECT_ROOT / ".scraper-state/gottesdienst_at_austria.checkpoint.sqlite",
        help="Gottesdienst.at checkpoint (use a new path when postcodes change)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="discard the checkpoint and search all selected postcodes again",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if not args.consent_google_maps:
        parser.error("--consent-google-maps is required to use the site's search")
    if not math.isfinite(args.interval) or args.interval < 0.5:
        parser.error("--interval must be at least 0.5 seconds")
    if args.output.resolve() == args.state.resolve():
        parser.error("--output and --state must be different files")
    if args.postcode and any(not re.fullmatch(r"\d{4}", postcode) for postcode in args.postcode):
        parser.error("postcodes must contain exactly four digits")
    return args


def main(
    argv: list[str] | None = None, *, parent_parser: argparse.ArgumentParser | None = None
) -> int:
    args = parse_args(argv, parent_parser=parent_parser)
    default_state = PROJECT_ROOT / ".scraper-state/gottesdienst_at_austria.checkpoint.sqlite"
    previous_state = PROJECT_ROOT / "data/databases/gottesdienst_at_austria.checkpoint.sqlite"
    if args.state.resolve() == default_state.resolve() and previous_state.exists():
        if not default_state.exists():
            raise RuntimeError(
                f"Checkpoint is still at {previous_state}. Stop any running importer and move "
                f"it to {default_state}, or specify --state explicitly."
            )
    if args.postcode:
        postcodes = sorted(set(args.postcode))
    else:
        LOG.info("Downloading GeoNames postcode list from %s", POSTCODES)
        request = Request(POSTCODES, headers={"User-Agent": "church-finder/1.0 postcode importer"})
        with urlopen(request, timeout=30) as response:
            payload = response.read()
        regions = ("Wien",) if args.vienna_only else AUSTRIAN_REGIONS
        postcodes = candidate_postcodes(payload, regions)
    LOG.info("Selected %d postcodes for Gottesdienst.at", len(postcodes))
    database = import_database(
        ImportOptions(
            postcodes=postcodes,
            interval=args.interval,
            state=args.state,
            fresh=args.fresh,
        )
    )
    previous, current, backup_path = publish_database(
        database, args.output, PROJECT_ROOT / "backups"
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
    LOG.info("Published website database to %s", args.output)
    return 0


def run(
    argv: list[str] | None = None, *, parent_parser: argparse.ArgumentParser | None = None
) -> int:
    try:
        return main(argv, parent_parser=parent_parser)
    except (OSError, ValueError, RuntimeError, sqlite3.Error, PlaywrightError) as error:
        LOG.error("%s", error)
        return 1
