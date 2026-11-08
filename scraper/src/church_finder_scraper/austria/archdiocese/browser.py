from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from .config import LOG, SOURCE


def start_session(page):
    LOG.info("Opening diocesan Gottesdienstsuche in Chromium")
    page.goto(SOURCE, wait_until="domcontentloaded", timeout=30000)
    notice = page.locator("#klaro .cookie-notice")
    if notice.is_visible(timeout=2000):
        LOG.info("Enabling only Google Maps consent needed for search results")
        notice.get_by_role(
            "button", name=re.compile("further information|weitere information", re.I)
        ).click()
        checkbox = page.locator("#service-item-googlemaps")
        checkbox.check(force=True)
        page.locator("#klaro .cm-modal").get_by_role(
            "button", name=re.compile("accept selected|save|ausgewählte|auswahl|speichern", re.I)
        ).click(no_wait_after=True)
        page.wait_for_timeout(1500)
    LOG.info("Reading current search session parameters")
    form = page.locator("#gd_searchForm")
    form.wait_for(state="attached", timeout=30000)
    action = form.get_attribute("action")
    if not action:
        raise ValueError("Search form action missing")
    query = parse_qs(urlsplit(action).query)
    if len(query.get("s", [])) != 1 or len(query.get("t", [])) != 1:
        raise ValueError("Search session parameters missing")
    return query["s"][0], query["t"][0]
