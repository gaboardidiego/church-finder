from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


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
