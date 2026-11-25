from __future__ import annotations

import re
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .config import LOG, SOURCE


def start_session(page) -> tuple[str, str]:
    LOG.info("Opening Gottesdienst.at service search in Chromium")
    for attempt in range(3):
        try:
            page.goto(SOURCE, wait_until="domcontentloaded", timeout=60000)
            break
        except PlaywrightTimeoutError:
            if attempt == 2:
                raise
            delay = 2 ** (attempt + 1)
            LOG.warning(
                "Gottesdienst.at navigation timed out (attempt %d/3); retrying in %d seconds",
                attempt + 1,
                delay,
            )
            time.sleep(delay)
    notice = page.locator("#klaro .cookie-notice")
    if notice.is_visible(timeout=2000):
        LOG.info("Enabling only Google Maps consent needed for search results")
        page.locator("#klaro").get_by_text(re.compile("Lassen Sie mich wählen", re.I)).click()
        page.locator("#service-item-googlemaps").check(force=True)
        page.locator("#klaro .cm-modal").get_by_role(
            "button", name=re.compile("Ausgewählte akzeptieren|accept selected", re.I)
        ).click(no_wait_after=True)
        page.wait_for_timeout(1500)

    page.locator("#gd_searchForm").wait_for(state="attached", timeout=30000)
    content = page.content()
    match = re.search(
        r"gottesdienstsuche_search_popup\.siteswift\?so=all&(?:amp;)?do=all"
        r"&(?:amp;)?c=getfind&(?:amp;)?s=(\d+)&(?:amp;)?t=([a-f0-9]+)",
        content,
        re.I,
    )
    if match is None:
        raise ValueError("Gottesdienst.at search session parameters missing")
    return match.group(1), match.group(2)
