"""Checkpoint storage for postcode searches."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


def connect_state(
    path: Path, postcodes: list[str], languages: bool, *, fresh: bool = False
) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    if fresh:
        db.execute("BEGIN IMMEDIATE")
    db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS results (postcode TEXT PRIMARY KEY, data TEXT NOT NULL)")
    if fresh:
        db.execute("DELETE FROM results")
        db.execute("DELETE FROM metadata")
    config = json.dumps({"version": 2, "postcodes": postcodes, "languages": languages})
    fingerprint = hashlib.sha256(config.encode()).hexdigest()
    stored = db.execute("SELECT value FROM metadata WHERE key='fingerprint'").fetchone()
    if stored and stored[0] != fingerprint:
        db.close()
        raise ValueError("Checkpoint options differ; use a new --state path")
    source = db.execute("SELECT value FROM metadata WHERE key='source'").fetchone()
    if source and source[0] != "gottesdienst_at":
        db.close()
        raise ValueError("Checkpoint belongs to another source; use a new --state path")
    if source is None:
        for (data,) in db.execute("SELECT data FROM results"):
            batch = json.loads(data)
            for entry in batch["results"]:
                if "marker_addr" in entry["church"]:
                    db.close()
                    raise ValueError(
                        "Checkpoint belongs to the former Vienna source; use a new --state path"
                    )
        db.execute("INSERT INTO metadata VALUES ('source', 'gottesdienst_at')")
    db.execute("INSERT OR IGNORE INTO metadata VALUES ('fingerprint', ?)", (fingerprint,))
    db.commit()
    return db


def completed_postcodes(db: sqlite3.Connection, postcodes: list[str]) -> set[str]:
    completed = {row[0] for row in db.execute("SELECT postcode FROM results")}
    if completed - set(postcodes):
        raise ValueError("Checkpoint contains unexpected postcodes")
    return completed


def save_batch(db: sqlite3.Connection, batch: dict) -> None:
    db.execute(
        "INSERT INTO results VALUES (?, ?)",
        (batch["postcode"], json.dumps(batch, ensure_ascii=False)),
    )
    db.commit()


def load_batches(db: sqlite3.Connection) -> list[dict]:
    return [json.loads(row[0]) for row in db.execute("SELECT data FROM results ORDER BY postcode")]
