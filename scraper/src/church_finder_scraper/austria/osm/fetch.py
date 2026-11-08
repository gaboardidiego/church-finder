from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import FALLBACK_OVERPASS_URLS, LOGGER, OVERPASS_QUERY, OVERPASS_URL
from .records import make_record


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

    unique_elements = {(element["type"], element["id"]): element for element in elements}
    LOGGER.info(
        "Removed %d duplicate feature(s); preparing %d unique record(s)",
        len(elements) - len(unique_elements),
        len(unique_elements),
    )
    records = [make_record(element) for element in unique_elements.values()]
    records.sort(key=lambda item: (str(item["name"]).casefold(), item["osm_type"], item["osm_id"]))
    return records
