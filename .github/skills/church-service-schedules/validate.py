#!/usr/bin/env python3
"""Validate church service schedule output.

Usage: validate.py <input.json> [--days N] [--timezone IANA_NAME] [--output-root DIR]

Exit code 0 when everything is valid, 1 otherwise. Problems are printed one per line.
"""
import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

KEYS = {"language", "start_time", "date"}
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
ERROR_LINE_RE = re.compile(r"^[^|]+ \| [^|]+ \| .+$")


def load_records(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("results")
    if not isinstance(data, list):
        raise ValueError("input must be a JSON array or an object with a 'results' array")
    return data


def is_valid_record(rec) -> bool:
    return isinstance(rec, dict) and all(
        isinstance(rec.get(k), str) and rec[k].strip() for k in ("uuid", "name", "website")
    )


def check_services(path: Path, today: date, last: date | None) -> tuple[list[str], int]:
    problems: list[str] = []
    try:
        services = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: not parseable ({exc})"], 0
    if not isinstance(services, list):
        return [f"{path}: must be a JSON array"], 0
    for i, svc in enumerate(services):
        where = f"{path}[{i}]"
        if not isinstance(svc, dict) or set(svc) != KEYS:
            problems.append(f"{where}: keys must be exactly {sorted(KEYS)}")
            continue
        if not isinstance(svc["language"], str) or not svc["language"].strip():
            problems.append(f"{where}: empty language")
        if not isinstance(svc["start_time"], str) or not TIME_RE.match(svc["start_time"]):
            problems.append(f"{where}: invalid start_time {svc['start_time']!r}")
        try:
            d = date.fromisoformat(svc["date"])
            if d < today or (last is not None and d > last):
                problems.append(f"{where}: date {d} outside {today}..{last or 'open end'}")
        except (TypeError, ValueError):
            problems.append(f"{where}: invalid date {svc['date']!r}")
    return problems, len(services)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--days", type=int, help="optional horizon; default: no upper limit")
    ap.add_argument("--timezone", help="IANA timezone of the churches (default: system timezone)")
    ap.add_argument("--output-root", type=Path)
    args = ap.parse_args()

    root = args.output_root or Path("data/services") / args.input.stem
    tz = ZoneInfo(args.timezone) if args.timezone else None
    today = datetime.now(tz).date()
    last = today + timedelta(days=args.days) if args.days is not None else None

    problems: list[str] = []
    needs_errors_log = False
    try:
        records = load_records(args.input)
    except (OSError, ValueError) as exc:
        print(f"input: {exc}")
        return 1

    # Invalid records get no folder; they must only be logged.
    valid = [r for r in records if is_valid_record(r)]
    if len(valid) != len(records):
        needs_errors_log = True

    for rec in valid:
        folder = root / rec["uuid"]
        if not folder.is_dir():
            problems.append(f"{folder}: missing folder")
            continue
        if not (folder / "parsing.md").is_file():
            problems.append(f"{folder}/parsing.md: missing")
        services_path = folder / "services.json"
        if not services_path.is_file():
            problems.append(f"{services_path}: missing")
            continue
        found, count = check_services(services_path, today, last)
        problems += found
        if count == 0:
            needs_errors_log = True

    errors_log = root / "errors.log"
    if errors_log.is_file():
        for n, line in enumerate(errors_log.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip() and not ERROR_LINE_RE.match(line):
                problems.append(f"{errors_log}:{n}: expected '<uuid> | <source> | <reason>'")
    elif needs_errors_log:
        problems.append(f"{errors_log}: missing but invalid records or empty schedules exist")

    for p in problems:
        print(p)
    print(f"checked {len(valid)} valid of {len(records)} records; {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
