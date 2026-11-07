from __future__ import annotations

import time
from typing import Any, TypedDict
from urllib.parse import urlsplit

from .config import LOG, POPUP, SOURCE
from .processing import normalize_services, parse_search, parse_services, service_key


class ServiceEntry(TypedDict):
    church: dict[str, Any]
    rows: list[dict[str, Any]]
    matches: dict[str, set[str]]


class Client:
    def __init__(self, context, site_id: str, token: str, interval: float):
        self.context, self.site_id, self.token = context, site_id, token
        self.interval, self.last_request = interval, 0.0
        self.request_count = 0

    def request(self, method: str, url: str, **kwargs):
        for attempt in range(3):
            time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            self.request_count += 1
            started = time.monotonic()
            LOG.info(
                "Request %d: %s %s (attempt %d/3)",
                self.request_count,
                method,
                urlsplit(url).path,
                attempt + 1,
            )
            response = self.context.request.fetch(url, method=method, timeout=30000, **kwargs)
            elapsed = time.monotonic() - started
            LOG.info(
                "Request %d completed: HTTP %d in %.1f seconds",
                self.request_count,
                response.status,
                elapsed,
            )
            if response.ok:
                return response
            if response.status not in {429, 500, 502, 503, 504} or attempt == 2:
                raise RuntimeError(f"{method} {urlsplit(url).path}: HTTP {response.status}")
            delay = 2 ** (attempt + 1)
            LOG.warning("HTTP %s, retrying in %s seconds", response.status, delay)
            time.sleep(delay)
        raise RuntimeError("Request retry limit reached")

    def postcode(self, postcode: str, use_languages: bool) -> list[dict]:
        params = {
            "do": "all",
            "c": "getfind",
            "s": self.site_id,
            "t": self.token,
            "d": f"gd_plz:{postcode};gd_search_type:plz",
        }
        html = self.request("GET", POPUP, params=params).text()
        churches, action, languages, defaults = parse_search(html)
        if not churches:
            return []
        action_url = urlsplit(action)
        if action_url.scheme != "https" or action_url.netloc != urlsplit(SOURCE).netloc:
            raise ValueError("Unexpected search form host")
        dates_url = POPUP + (
            f"?so=site_gottesdienstsuche_search_popup&do=site_gottesdienstsuche_search_popup"
            f"&c=xhr_dates_for_coid&s={self.site_id}&t={self.token}"
        )
        records: dict[tuple[str, str], ServiceEntry] = {}
        for index, church in enumerate(churches, start=1):
            identity = (church["id"], church["marker_addr"])
            if identity in records:
                raise ValueError(f"Duplicate church result: {identity}")
            LOG.info(
                "%s: fetching services for church %d/%d: %s (%s)",
                postcode,
                index,
                len(churches),
                church["name"],
                church["id"],
            )
            response = self.request(
                "POST",
                dates_url,
                form={
                    "coid": church["id"],
                    "addr": church["marker_addr"],
                },
            )
            records[identity] = {
                "church": church,
                "rows": parse_services(response.json(), church["id"]),
                "matches": {},
            }
        if use_languages:
            for language_index, language in enumerate(languages, start=1):
                LOG.info(
                    "%s: checking language %d/%d: %s",
                    postcode,
                    language_index,
                    len(languages),
                    language,
                )
                form = {**defaults, "gd_plz": postcode, "sprache": language}
                filtered_html = self.request("POST", action, form=form).text()
                filtered, _, _, _ = parse_search(filtered_html)
                LOG.info(
                    "%s: language %s matched %d church result(s)", postcode, language, len(filtered)
                )
                for church in filtered:
                    identity = (church["id"], church["marker_addr"])
                    if identity not in records:
                        raise ValueError(f"Filtered search returned an unknown church: {identity}")
                    data = self.request(
                        "POST",
                        dates_url,
                        form={
                            "coid": church["id"],
                            "addr": church["marker_addr"],
                        },
                    ).json()
                    rows = parse_services(data, church["id"])
                    entry = records[identity]
                    baseline = {service_key(row) for row in entry["rows"]}
                    filtered_counts = {}
                    for row in rows:
                        key = service_key(row)
                        filtered_counts[key] = filtered_counts.get(key, 0) + 1
                    for row in rows:
                        key = service_key(row)
                        if key not in baseline:
                            raise ValueError(f"Filtered service not in baseline for {identity}")
                        if filtered_counts[key] == 1:
                            entry["matches"].setdefault(key, set()).add(language)
        return [
            {
                "church": entry["church"],
                "services": normalize_services(entry["rows"], entry["matches"]),
            }
            for entry in records.values()
        ]
