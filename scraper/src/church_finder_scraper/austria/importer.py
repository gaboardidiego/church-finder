from __future__ import annotations

import contextlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from .browser import start_session
from .client import Client
from .config import LOG
from .database import build_database
from .state import completed_postcodes, connect_state, load_batches, save_batch
from .websites import enrich_websites, fetch_austria_records


@dataclass(frozen=True)
class ImportOptions:
    postcodes: list[str]
    interval: float
    state: Path
    fresh: bool = False


def _collect_postcodes(db: sqlite3.Connection, options: ImportOptions, completed: set[str]) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            site_id, token = start_session(context.new_page())
            client = Client(context, site_id, token, options.interval)
            for postcode in options.postcodes:
                if postcode in completed:
                    LOG.info("%s: already complete in checkpoint; skipping", postcode)
                    continue
                LOG.info(
                    "Processing postcode %s (%d/%d)",
                    postcode,
                    len(completed) + 1,
                    len(options.postcodes),
                )
                results = client.postcode(postcode)
                save_batch(
                    db,
                    {
                        "postcode": postcode,
                        "completed_at": datetime.now(UTC).isoformat(),
                        "results": results,
                    },
                )
                completed.add(postcode)
        finally:
            browser.close()


def import_database(options: ImportOptions) -> dict:
    if options.fresh:
        LOG.info("Starting fresh: discarding checkpoint data in %s", options.state)
    with contextlib.closing(
        connect_state(options.state, options.postcodes, False, fresh=options.fresh)
    ) as db:
        completed = completed_postcodes(db, options.postcodes)
        LOG.info(
            "Searching Gottesdienst.at for %d postcodes, %d already completed",
            len(options.postcodes),
            len(completed),
        )
        if len(completed) != len(options.postcodes):
            _collect_postcodes(db, options, completed)
        database = build_database(load_batches(db))

    if database["churches"]:
        LOG.info("Fetching Austrian church locations and websites from OpenStreetMap")
        enrich_websites(database, fetch_austria_records())
    LOG.info(
        "Prepared %d locations and %d services",
        len(database["churches"]),
        sum(map(len, database["services"].values())),
    )
    return database
