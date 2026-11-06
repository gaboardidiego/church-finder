#!/usr/bin/env python3
"""Export Christian places of worship and church buildings in Vienna from OSM."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
FALLBACK_OVERPASS_URLS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
OVERPASS_QUERY = """[out:json][timeout:180];
area["boundary"="administrative"]["admin_level"="4"]["name"="Wien"]->.vienna;
(
  nwr["amenity"="place_of_worship"]["religion"="christian"](area.vienna);
  nwr["building"="church"](area.vienna);
);
out center tags;
"""
LOGGER = logging.getLogger("fetch_vienna_churches")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

CSV_FIELDS = (
    "osm_type",
    "osm_id",
    "name",
    "religion",
    "denomination",
    "place_of_worship",
    "operator",
    "website",
    "phone",
    "email",
    "opening_hours",
    "addr:full",
    "addr:housenumber",
    "addr:street",
    "addr:postcode",
    "addr:city",
    "latitude",
    "longitude",
    "osm_url",
    "data_source",
    "attribution",
    "tags",
)


def fetch_elements(endpoint: str, timeout: int, retries: int) -> list[dict]:
    request = Request(
        endpoint,
        data=urlencode({"data": OVERPASS_QUERY}).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "church-finder-vienna/1.0 (OpenStreetMap Overpass client)",
        },
        method="POST",
    )
    for attempt in range(retries + 1):
        try:
            LOGGER.info("Sending query to %s (attempt %d/%d)", endpoint, attempt + 1, retries + 1)
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))

            if not isinstance(payload, dict):
                raise RuntimeError("Overpass API response was not a JSON object")
            if payload.get("remark"):
                raise RuntimeError(f"Overpass API error: {payload['remark']}")
            elements = payload.get("elements")
            if not isinstance(elements, list):
                raise RuntimeError("Overpass API response did not contain an elements list")
            if any(
                not isinstance(element, dict)
                or "type" not in element
                or "id" not in element
                or not isinstance(element.get("tags", {}), dict)
                for element in elements
            ):
                raise RuntimeError("Overpass API response contained a malformed element")
            LOGGER.info("Received %d matching OSM features from %s", len(elements), endpoint)
            return elements
        except HTTPError as error:
            retryable = error.code in (429, 500, 502, 503, 504)
            message = f"HTTP {error.code}: {error.reason}"
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            retryable = True
            message = str(error)
        except RuntimeError:
            raise

        if retryable and attempt < retries:
            delay = 2**attempt
            LOGGER.warning(
                "Request to %s failed (%s); retrying in %d second(s)",
                endpoint,
                message,
                delay,
            )
            time.sleep(delay)
        else:
            raise RuntimeError(f"Request to {endpoint} failed: {message}")

    raise RuntimeError(f"Request to {endpoint} failed after retries")


def make_record(element: dict) -> dict:
    tags = element.get("tags", {})
    center = element.get("center", {})
    latitude = element.get("lat", center.get("lat"))
    longitude = element.get("lon", center.get("lon"))
    osm_type = element["type"]
    osm_id = element["id"]

    record = {field: tags.get(field, "") for field in CSV_FIELDS}
    record.update(
        {
            "osm_type": osm_type,
            "osm_id": osm_id,
            "latitude": latitude if latitude is not None else "",
            "longitude": longitude if longitude is not None else "",
            "osm_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
            "data_source": "OpenStreetMap",
            "attribution": "© OpenStreetMap contributors",
            "tags": tags,
        }
    )
    return record


def write_csv(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for record in records:
            row = record.copy()
            row["tags"] = json.dumps(record["tags"], ensure_ascii=False, sort_keys=True)
            writer.writerow(row)


def write_json(path: Path, records: list[dict], retrieved_at: str) -> None:
    document = {
        "data_source": "OpenStreetMap",
        "attribution": "© OpenStreetMap contributors",
        "retrieved_at_utc": retrieved_at,
        "results": records,
    }
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_records(endpoint: str = OVERPASS_URL, timeout: int = 200, retries: int = 2) -> list[dict]:
    """Fetch and normalize Vienna OSM records for reuse by other importers."""
    endpoints = list(dict.fromkeys((endpoint, *FALLBACK_OVERPASS_URLS)))
    for index, current_endpoint in enumerate(endpoints):
        try:
            elements = fetch_elements(current_endpoint, timeout, retries)
            break
        except RuntimeError as error:
            if index + 1 == len(endpoints):
                raise
            LOGGER.warning("%s; switching to fallback Overpass instance", error)

    unique_elements = {
        (element["type"], element["id"]): element
        for element in elements
    }
    LOGGER.info(
        "Removed %d duplicate feature(s); preparing %d unique record(s)",
        len(elements) - len(unique_elements),
        len(unique_elements),
    )
    records = [make_record(element) for element in unique_elements.values()]
    records.sort(key=lambda item: (str(item["name"]).casefold(), item["osm_type"], item["osm_id"]))
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Christian places of worship and church buildings within Vienna's "
            "administrative boundary from OpenStreetMap."
        )
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
    retrieved_at = datetime.now(timezone.utc).isoformat()
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


if __name__ == "__main__":
    raise SystemExit(main())
