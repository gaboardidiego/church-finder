import logging
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from church_finder_scraper.austria.cli import parse_args
from church_finder_scraper.austria.importer import ImportOptions, import_database
from church_finder_scraper.austria.state import (
    completed_postcodes,
    connect_state,
    load_batches,
    save_batch,
)


@pytest.fixture
def options(tmp_path: Path) -> ImportOptions:
    return ImportOptions(
        postcodes=["1010", "2000"],
        interval=0.5,
        state=tmp_path / "checkpoint.sqlite",
    )


def test_import_resumes_after_failure(options: ImportOptions, caplog):
    caplog.set_level(logging.INFO, logger="gottesdienst_at")
    browser = MagicMock()
    playwright = MagicMock()
    playwright.chromium.launch.return_value = browser
    manager = MagicMock()
    manager.__enter__.return_value = playwright
    client = MagicMock()
    client.postcode.side_effect = [[], RuntimeError("interrupted"), []]

    with (
        patch(
            "church_finder_scraper.austria.importer.sync_playwright",
            return_value=manager,
        ),
        patch(
            "church_finder_scraper.austria.importer.start_session",
            return_value=("s", "t"),
        ),
        patch("church_finder_scraper.austria.importer.Client", return_value=client),
    ):
        with pytest.raises(RuntimeError, match="interrupted"):
            import_database(options)
        with closing(connect_state(options.state, options.postcodes, False)) as db:
            assert completed_postcodes(db, options.postcodes) == {"1010"}
            assert [batch["postcode"] for batch in load_batches(db)] == ["1010"]
        database = import_database(options)

    assert client.postcode.call_args_list == [(("1010",),), (("2000",),), (("2000",),)]
    assert browser.close.call_count == 2
    assert database == {"churches": [], "services": {}}
    assert "Searching Gottesdienst.at for 2 postcodes, 1 already completed" in caplog.messages
    assert [
        message for message in caplog.messages if message.startswith("Processing postcode")
    ] == [
        "Processing postcode 1010 (1/2)",
        "Processing postcode 2000 (2/2)",
        "Processing postcode 2000 (2/2)",
    ]


def test_progress_counts_completed_postcodes_regardless_of_order(options: ImportOptions, caplog):
    caplog.set_level(logging.INFO, logger="gottesdienst_at")
    with closing(connect_state(options.state, options.postcodes, False)) as db:
        save_batch(db, {"postcode": "2000", "results": []})
    client = MagicMock()
    client.postcode.return_value = []
    with (
        patch("church_finder_scraper.austria.importer.sync_playwright"),
        patch(
            "church_finder_scraper.austria.importer.start_session",
            return_value=("s", "t"),
        ),
        patch("church_finder_scraper.austria.importer.Client", return_value=client),
    ):
        import_database(options)

    client.postcode.assert_called_once_with("1010")
    assert "Processing postcode 1010 (2/2)" in caplog.messages
    assert "2000: already complete in checkpoint; skipping" in caplog.messages


def test_completed_checkpoint_does_not_launch_browser(options: ImportOptions):
    with closing(connect_state(options.state, options.postcodes, False)) as db:
        for postcode in options.postcodes:
            save_batch(db, {"postcode": postcode, "results": []})
    with patch("church_finder_scraper.austria.importer.sync_playwright") as browser:
        database = import_database(options)
    browser.assert_not_called()
    assert database == {"churches": [], "services": {}}


def test_osm_failure_preserves_checkpoint(options: ImportOptions):
    with closing(connect_state(options.state, options.postcodes, False)) as db:
        for postcode in options.postcodes:
            save_batch(
                db,
                {
                    "postcode": postcode,
                    "results": [
                        {
                            "church": {
                                "id": postcode,
                                "name": "Church",
                                "position": {"latitude": 47.8, "longitude": 13.0},
                            },
                            "services": [],
                        }
                    ],
                },
            )
    with (
        patch(
            "church_finder_scraper.austria.importer.fetch_austria_records",
            side_effect=RuntimeError("Overpass unavailable"),
        ),
        pytest.raises(RuntimeError, match="Overpass unavailable"),
    ):
        import_database(options)
    with closing(connect_state(options.state, options.postcodes, False)) as db:
        assert completed_postcodes(db, options.postcodes) == set(options.postcodes)


def test_checkpoint_rejects_unexpected_postcodes(options: ImportOptions):
    with closing(connect_state(options.state, options.postcodes, False)) as db:
        save_batch(db, {"postcode": "9999", "results": []})
        with pytest.raises(ValueError, match="unexpected postcodes"):
            completed_postcodes(db, options.postcodes)


def test_checkpoint_rejects_changed_postcodes(options: ImportOptions):
    with closing(connect_state(options.state, options.postcodes, False)):
        pass
    with pytest.raises(ValueError, match="Checkpoint options differ"):
        connect_state(options.state, ["1010"], False)


def test_legacy_vienna_checkpoint_is_rejected_before_starting_browser(options: ImportOptions):
    with closing(connect_state(options.state, options.postcodes, False)) as db:
        db.execute("DELETE FROM metadata WHERE key='source'")
        save_batch(
            db,
            {"postcode": "1010", "results": [{"church": {"marker_addr": "Vienna"}}]},
        )
    with (
        patch("church_finder_scraper.austria.importer.sync_playwright") as browser,
        pytest.raises(ValueError, match="former Vienna source"),
    ):
        import_database(options)
    browser.assert_not_called()


def test_legacy_gottesdienst_checkpoint_is_reused(options: ImportOptions):
    with closing(connect_state(options.state, options.postcodes, False)) as db:
        db.execute("DELETE FROM metadata WHERE key='source'")
        save_batch(db, {"postcode": "1010", "results": []})
    with closing(connect_state(options.state, options.postcodes, False)) as db:
        assert completed_postcodes(db, options.postcodes) == {"1010"}
        assert db.execute("SELECT value FROM metadata WHERE key='source'").fetchone() == (
            "gottesdienst_at",
        )


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--consent-google-maps", "--interval", "nan"],
        ["--consent-google-maps", "--postcode", "abc"],
        ["--consent-google-maps", "--output", "same", "--state", "same"],
        ["--consent-google-maps", "--output", "same", "--website-output", "same"],
        ["--consent-google-maps", "--state", "same", "--website-output", "same"],
        ["--consent-google-maps", "--postcode", "1010", "--vienna-only"],
    ],
)
def test_cli_rejects_invalid_options(arguments: list[str]):
    with pytest.raises(SystemExit) as error:
        parse_args(arguments)
    assert error.value.code == 2
