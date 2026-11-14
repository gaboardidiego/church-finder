from unittest.mock import MagicMock

import pytest

from church_finder_scraper.austria.browser import start_session


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
