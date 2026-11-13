from __future__ import annotations

import time
from urllib.parse import urlsplit

from .config import LOG, POPUP
from .processing import parse_search


class Client:
    def __init__(self, context, site_id: str, token: str, interval: float):
        self.context, self.site_id, self.token = context, site_id, token
        self.interval, self.last_request = interval, 0.0
        self.request_count = 0

    def request(self, postcode: str):
        for attempt in range(3):
            time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            self.request_count += 1
            LOG.info(
                "Request %d: postcode %s (attempt %d/3)",
                self.request_count,
                postcode,
                attempt + 1,
            )
            response = self.context.request.fetch(
                POPUP,
                method="GET",
                timeout=30000,
                params={
                    "so": "all",
                    "do": "all",
                    "c": "getfind",
                    "s": self.site_id,
                    "t": self.token,
                    "d": f"gd_plz:{postcode};bundesland:;gottesdienstart:;art:",
                },
            )
            LOG.info(
                "Request %d completed: HTTP %d",
                self.request_count,
                response.status,
            )
            if response.ok:
                return response
            if response.status not in {429, 500, 502, 503, 504} or attempt == 2:
                raise RuntimeError(f"GET {urlsplit(POPUP).path}: HTTP {response.status}")
            delay = 2 ** (attempt + 1)
            LOG.warning("HTTP %s, retrying in %s seconds", response.status, delay)
            time.sleep(delay)
        raise RuntimeError("Request retry limit reached")

    def postcode(self, postcode: str) -> list[dict]:
        response = self.request(postcode)
        results = parse_search(response.text())
        service_count = sum(len(entry["services"]) for entry in results)
        if service_count >= 200:
            LOG.warning(
                "%s: Gottesdienst.at returned at least 200 services; verify whether its "
                "search result limit truncated this postcode",
                postcode,
            )
        LOG.info("%s: %d locations", postcode, len(results))
        return results
