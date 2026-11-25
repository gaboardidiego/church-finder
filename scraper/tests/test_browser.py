from unittest.mock import MagicMock, call

import pytest
from playwright.sync_api import Error, TimeoutError

from church_finder_scraper.austria.browser import start_session
from church_finder_scraper.austria.config import SOURCE


@pytest.mark.parametrize("consent_visible", [False, True])
def test_start_session_extracts_parameters_and_only_enables_google_maps(consent_visible):
    page = MagicMock()
    notice = MagicMock()
    klaro = MagicMock()
    modal = MagicMock()
    google_maps = MagicMock()
    search_form = MagicMock()
    page.locator.side_effect = {
        "#klaro .cookie-notice": notice,
        "#klaro": klaro,
        "#klaro .cm-modal": modal,
        "#service-item-googlemaps": google_maps,
        "#gd_searchForm": search_form,
    }.get
    notice.is_visible.return_value = consent_visible
    page.content.return_value = (
        "gottesdienstsuche_search_popup.siteswift?so=all&amp;do=all"
        "&amp;c=getfind&amp;s=123&amp;t=abc123"
    )

    assert start_session(page) == ("123", "abc123")
    search_form.wait_for.assert_called_once_with(state="attached", timeout=30000)
    if consent_visible:
        google_maps.check.assert_called_once_with(force=True)
        klaro.get_by_text.assert_called_once()
        modal.get_by_role.return_value.click.assert_called_once_with(no_wait_after=True)
    else:
        google_maps.check.assert_not_called()
        klaro.get_by_text.assert_not_called()


def test_start_session_rejects_missing_parameters():
    page = MagicMock()
    page.locator.return_value.is_visible.return_value = False
    page.content.return_value = "<html></html>"

    with pytest.raises(ValueError, match="session parameters missing"):
        start_session(page)


def test_start_session_retries_navigation_timeouts(monkeypatch, caplog):
    page = MagicMock()
    page.goto.side_effect = [TimeoutError("slow"), TimeoutError("slow"), None]
    page.locator.return_value.is_visible.return_value = False
    page.content.return_value = (
        "gottesdienstsuche_search_popup.siteswift?so=all&do=all&c=getfind&s=123&t=abc123"
    )
    delays = []
    monkeypatch.setattr("church_finder_scraper.austria.browser.time.sleep", delays.append)

    assert start_session(page) == ("123", "abc123")
    assert (
        page.goto.call_args_list
        == [
            call(SOURCE, wait_until="domcontentloaded", timeout=60000),
        ]
        * 3
    )
    assert delays == [2, 4]
    assert "retrying" in caplog.text


def test_start_session_raises_after_navigation_timeout_retries(monkeypatch):
    page = MagicMock()
    page.goto.side_effect = TimeoutError("slow")
    monkeypatch.setattr("church_finder_scraper.austria.browser.time.sleep", lambda _: None)

    with pytest.raises(TimeoutError, match="slow"):
        start_session(page)
    assert page.goto.call_count == 3
    page.locator.assert_not_called()


def test_start_session_does_not_retry_other_navigation_errors():
    page = MagicMock()
    page.goto.side_effect = Error("navigation failed")

    with pytest.raises(Error, match="navigation failed"):
        start_session(page)
    assert page.goto.call_count == 1
