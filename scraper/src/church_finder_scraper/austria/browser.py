from __future__ import annotations

import re

from .config import LOG, SOURCE


def start_session(page) -> tuple[str, str]:
    LOG.info("Opening Gottesdienst.at service search in Chromium")
    page.goto(SOURCE, wait_until="domcontentloaded", timeout=30000)
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
