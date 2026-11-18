from __future__ import annotations

import argparse
import logging
import math
import sqlite3
from pathlib import Path

from ..austria.publish import publish_database
from ..paths import PROJECT_ROOT
from .ember import LOG
from .ember import import_database as import_ember


def main(
    argv: list[str] | None = None, *, parent_parser: argparse.ArgumentParser | None = None
) -> int:
    parser = argparse.ArgumentParser(
        description="Import Italian church services from Ember",
        parents=[parent_parser] if parent_parser else [],
    )
    parser.add_argument(
        "--source",
        choices=("ember",),
        default="ember",
        help="Italy data source (default: ember); each import replaces the Italy index",
    )
    parser.add_argument(
        "--interval", type=float, default=1.0, help="seconds between requests (minimum: 1)"
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=PROJECT_ROOT / ".scraper-state/ember_italy.checkpoint.sqlite",
        help="Ember checkpoint path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "web/public/data/churches_italy.database.json",
        help="Italy website database path",
    )
    parser.add_argument("--fresh", action="store_true", help="discard cached API pages")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if not math.isfinite(args.interval) or args.interval < 1:
        parser.error("--interval must be at least 1 second")
    if args.state.resolve() == args.output.resolve():
        parser.error("--output and --state must be different files")
    LOG.info("Importing Ember; the output replaces the previous Italy index")
    database = import_ember(args.state, args.interval, fresh=args.fresh)
    regions = {church["region"] for church in database["churches"]}
    previous, current, backup = publish_database(
        database, args.output, PROJECT_ROOT / "backups", regions=regions
    )
    LOG.info("Published %d churches and %d services to %s", *current, args.output)
    if previous is not None:
        LOG.info("Backed up %d churches and %d services to %s", *previous, backup)
    return 0


def run(
    argv: list[str] | None = None, *, parent_parser: argparse.ArgumentParser | None = None
) -> int:
    try:
        return main(argv, parent_parser=parent_parser)
    except (OSError, ValueError, sqlite3.Error) as error:
        LOG.error("%s", error)
        return 1
