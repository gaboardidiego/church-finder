"""Orchestrate a resumable diocese import and publish its database."""

from __future__ import annotations

import contextlib
import json
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from ..osm import fetch_records as fetch_osm_records
from .browser import start_session
from .client import Client
from .config import LOG, ROOT
from .database import build_database
from .publish import publish_database
from .state import completed_postcodes, connect_state, load_batches, save_batch


@dataclass(frozen=True)
class ImportOptions:
    postcodes: list[str]
    languages: bool
    interval: float
    osm_endpoint: str
    osm_timeout: int
    osm_retries: int
    osm_tolerance_meters: float
    output: Path
    website_output: Path
    state: Path


def collect_batches(db: sqlite3.Connection, options: ImportOptions, completed: set[str]) -> None:
    if len(completed) == len(options.postcodes):
        return
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            site_id, token = start_session(context.new_page())
            client = Client(context, site_id, token, options.interval)
            LOG.info("Starting diocese search for %d postcodes", len(options.postcodes))
            for postcode in options.postcodes:
                if postcode in completed:
                    LOG.info("%s: already complete in checkpoint; skipping", postcode)
                    continue
                LOG.info("%s: starting postcode search", postcode)
                result = client.postcode(postcode, options.languages)
                save_batch(
                    db,
                    {
                        "postcode": postcode,
                        "completed_at": datetime.now(UTC).isoformat(),
                        "results": result,
                    },
                )
                completed.add(postcode)
                LOG.info(
                    "%s: %d locations (%d/%d)",
                    postcode,
                    len(result),
                    len(completed),
                    len(options.postcodes),
                )
        finally:
            browser.close()


def write_database(path: Path, database: dict) -> None:
    """Replace the generated database only after it has been completely written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=path.name + ".", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(database, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def import_database(options: ImportOptions) -> None:
    with contextlib.closing(
        connect_state(options.state, options.postcodes, options.languages)
    ) as db:
        completed = completed_postcodes(db, options.postcodes)
        LOG.info(
            "Searching %d postcodes, %d already completed", len(options.postcodes), len(completed)
        )
        LOG.info("Fetching Vienna church websites and coordinates from OSM")
        osm_records = fetch_osm_records(
            options.osm_endpoint, options.osm_timeout, options.osm_retries
        )
        website_count = sum(bool(record.get("website")) for record in osm_records)
        LOG.info("Fetched %d OSM records; %d include a website", len(osm_records), website_count)
        collect_batches(db, options, completed)
        database = build_database(
            load_batches(db),
            options.postcodes,
            options.languages,
            osm_records,
            options.osm_tolerance_meters,
        )
        matched_websites = sum(bool(church.get("website")) for church in database["churches"])
        LOG.info(
            "Matched OSM websites for %d/%d diocese locations",
            matched_websites,
            len(database["churches"]),
        )
        write_database(options.output, database)
        LOG.info(
            "Wrote %d locations and %d services to %s",
            len(database["churches"]),
            sum(map(len, database["services"].values())),
            options.output,
        )
        previous, current, backup_path = publish_database(
            options.output, options.website_output, ROOT / "backups"
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
        LOG.info("Published website database to %s", options.website_output)
