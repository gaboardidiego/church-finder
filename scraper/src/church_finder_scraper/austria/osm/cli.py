from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path

from .config import LOGGER, OVERPASS_URL, REPOSITORY_ROOT
from .fetch import fetch_records
from .records import write_csv, write_json


def parse_args(
    argv: list[str] | None = None, *, parent_parser: argparse.ArgumentParser | None = None
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        parents=[parent_parser] if parent_parser else [],
        description=(
            "Fetch Christian places of worship and church buildings within Vienna's "
            "administrative boundary from OpenStreetMap."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("csv", "json"),
        default="csv",
        help="output format (default: csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="output file (default: data/churches/churches_vienna.<format>)",
    )
    parser.add_argument(
        "--endpoint",
        default=OVERPASS_URL,
        help="Overpass API endpoint (useful for an alternate instance)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=200,
        help="HTTP request timeout in seconds (default: 200)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="retries per Overpass instance for transient failures (default: 2)",
    )
    return parser.parse_args(argv)


def run(
    argv: list[str] | None = None, *, parent_parser: argparse.ArgumentParser | None = None
) -> int:
    args = parse_args(argv, parent_parser=parent_parser)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    if args.timeout <= 0:
        LOGGER.error("--timeout must be a positive number")
        return 2
    if args.retries < 0:
        LOGGER.error("--retries cannot be negative")
        return 2

    output_path = args.output or (
        REPOSITORY_ROOT / "data" / "churches" / f"churches_vienna.{args.format}"
    )
    retrieved_at = datetime.now(UTC).isoformat()
    LOGGER.info("Starting Vienna church search using OpenStreetMap Overpass")
    LOGGER.info("Searching Vienna for Christian places of worship and church buildings")
    try:
        records = fetch_records(args.endpoint, args.timeout, args.retries)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        LOGGER.info("Writing %s output to %s", args.format.upper(), output_path)
        if args.format == "csv":
            write_csv(output_path, records)
        else:
            write_json(output_path, records, retrieved_at)
    except (RuntimeError, OSError) as error:
        LOGGER.error("%s", error)
        return 1

    LOGGER.info("Finished successfully: wrote %d feature(s) to %s", len(records), output_path)
    return 0
