import json
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from church_finder_scraper.archdiocese.cli import parse_args
from church_finder_scraper.archdiocese.importer import (
    ImportOptions,
    import_database,
    write_database,
)
from church_finder_scraper.archdiocese.state import (
    completed_postcodes,
    connect_state,
    load_batches,
    save_batch,
)


@pytest.fixture
def options(tmp_path: Path) -> ImportOptions:
    return ImportOptions(
        postcodes=["1010", "1020"],
        languages=False,
        interval=0.5,
        osm_endpoint="https://overpass.example",
        osm_timeout=10,
        osm_retries=0,
        osm_tolerance_meters=50,
        output=tmp_path / "generated.json",
        website_output=tmp_path / "published.json",
        state=tmp_path / "checkpoint.sqlite",
    )


def test_import_resumes_after_failure_and_publishes(options: ImportOptions):
    browser = MagicMock()
    playwright = MagicMock()
    playwright.chromium.launch.return_value = browser
    manager = MagicMock()
    manager.__enter__.return_value = playwright
    client = MagicMock()
    client.postcode.side_effect = [[], RuntimeError("interrupted"), []]

    with (
        patch("church_finder_scraper.archdiocese.importer.sync_playwright", return_value=manager),
        patch("church_finder_scraper.archdiocese.importer.start_session", return_value=("s", "t")),
        patch("church_finder_scraper.archdiocese.importer.Client", return_value=client),
        patch("church_finder_scraper.archdiocese.importer.fetch_osm_records", return_value=[]),
    ):
        with pytest.raises(RuntimeError, match="interrupted"):
            import_database(options)
        assert not options.output.exists()
        assert not options.website_output.exists()
        with closing(connect_state(options.state, options.postcodes, options.languages)) as db:
            assert completed_postcodes(db, options.postcodes) == {"1010"}
            assert [batch["postcode"] for batch in load_batches(db)] == ["1010"]
        import_database(options)

    assert client.postcode.call_args_list == [
        (("1010", False),),
        (("1020", False),),
        (("1020", False),),
    ]
    assert browser.close.call_count == 2
    assert json.loads(options.output.read_text()) == {"churches": [], "services": {}}
    assert options.website_output.read_bytes() == options.output.read_bytes()


def test_completed_checkpoint_does_not_launch_browser(options: ImportOptions):
    with closing(connect_state(options.state, options.postcodes, options.languages)) as db:
        for postcode in options.postcodes:
            save_batch(db, {"postcode": postcode, "results": []})
    with (
        patch("church_finder_scraper.archdiocese.importer.sync_playwright") as playwright,
        patch("church_finder_scraper.archdiocese.importer.fetch_osm_records", return_value=[]),
    ):
        import_database(options)
    playwright.assert_not_called()
    assert options.website_output.exists()


def test_checkpoint_rejects_unexpected_postcodes(options: ImportOptions):
    with closing(connect_state(options.state, options.postcodes, options.languages)) as db:
        save_batch(db, {"postcode": "9999", "results": []})
        with pytest.raises(ValueError, match="unexpected postcodes"):
            completed_postcodes(db, options.postcodes)


def test_write_database_preserves_previous_file_on_serialization_failure(tmp_path: Path):
    output = tmp_path / "database.json"
    output.write_text("previous", encoding="utf-8")
    with pytest.raises(TypeError):
        write_database(output, {"invalid": object()})
    assert output.read_text(encoding="utf-8") == "previous"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--consent-google-maps", "--interval", "nan"],
        ["--consent-google-maps", "--postcode", "abc"],
        ["--consent-google-maps", "--output", "same", "--state", "same"],
        ["--consent-google-maps", "--output", "same", "--website-output", "same"],
        ["--consent-google-maps", "--state", "same", "--website-output", "same"],
    ],
)
def test_cli_rejects_invalid_options(arguments: list[str]):
    with patch("sys.argv", ["churches-services", *arguments]), pytest.raises(SystemExit) as error:
        parse_args()
    assert error.value.code == 2
