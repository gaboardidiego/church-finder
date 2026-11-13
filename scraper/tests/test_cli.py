import argparse
import io
import json
import zipfile
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from church_finder_scraper import cli
from church_finder_scraper.austria.state import connect_state, load_batches, save_batch


class ZipResponse:
    def __init__(self, value: bytes):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.value


def postcode_archive() -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr(
            "AT.txt",
            "AT\t1010\tWien\tWien\n"
            "AT\t2000\tStockerau\tNiederösterreich\n"
            "AT\t7000\tEisenstadt\tBurgenland\n"
            "AT\t9020\tKlagenfurt\tKärnten\n"
            "AT\t4020\tLinz\tOberösterreich\n"
            "AT\t5020\tSalzburg\tSalzburg\n"
            "AT\t8010\tGraz\tSteiermark\n"
            "AT\t6020\tInnsbruck\tTirol\n"
            "AT\t6900\tBregenz\tVorarlberg\n",
        )
    return payload.getvalue()


@pytest.mark.parametrize("country_args", [[], ["--country", "austria"]])
def test_dispatches_to_austria(country_args: list[str]):
    command = "services"
    handler = Mock(return_value=7)
    with patch.object(cli, "import_module", return_value=SimpleNamespace(run=handler)) as load:
        assert cli.dispatch(command, [*country_args, "--example", "value"]) == 7

    load.assert_called_once_with(cli.COUNTRY_MODULES["austria"][command])
    handler.assert_called_once()
    assert handler.call_args.args == (["--example", "value"],)
    parent = handler.call_args.kwargs["parent_parser"]
    assert parent.parse_args([]).country == "austria"


def test_rejects_unknown_country_before_loading(capsys: pytest.CaptureFixture[str]):
    with patch.object(cli, "import_module") as load, pytest.raises(SystemExit) as error:
        cli.dispatch("services", ["--country", "unknown"])
    assert error.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
    load.assert_not_called()


def test_help_includes_country_and_country_specific_options(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as error:
        cli.dispatch("services", ["--help"])
    assert error.value.code == 0
    help_text = capsys.readouterr().out
    assert "--country {austria}" in help_text
    assert "--consent-google-maps" in help_text


def test_dispatch_supports_independent_country_implementations(monkeypatch: pytest.MonkeyPatch):
    handler = Mock(return_value=0)
    monkeypatch.setitem(cli.COUNTRY_MODULES, "example", {"services": "example.services"})
    with patch.object(cli, "import_module", return_value=SimpleNamespace(run=handler)) as load:
        assert cli.dispatch("services", ["--country", "example", "--new-option"]) == 0
    load.assert_called_once_with("example.services")
    parser = argparse.ArgumentParser(parents=[handler.call_args.kwargs["parent_parser"]])
    assert parser.parse_args([]).country == "example"
    assert handler.call_args.args == (["--new-option"],)


@pytest.mark.parametrize("country_args", [[], ["--country", "austria"]])
def test_services_command_preserves_checkpoint_option(country_args: list[str], tmp_path: Path):
    checkpoint = tmp_path / "checkpoint.sqlite"
    with (
        patch("church_finder_scraper.austria.cli.urlopen") as urlopen,
        patch("church_finder_scraper.austria.cli.import_database") as importer,
        patch(
            "church_finder_scraper.austria.cli.publish_database",
            return_value=(None, (0, 0), None),
        ) as publish,
    ):
        assert (
            cli.dispatch(
                "services",
                [
                    *country_args,
                    "--consent-google-maps",
                    "--postcode",
                    "1010",
                    "--state",
                    str(checkpoint),
                ],
            )
            == 0
        )
    assert importer.call_args.args[0].state == checkpoint
    assert importer.call_args.args[0].postcodes == ["1010"]
    urlopen.assert_not_called()
    publish.assert_called_once()


def test_services_routes_vienna_and_other_postcodes_to_same_source(tmp_path: Path):
    with (
        patch("church_finder_scraper.austria.cli.import_database") as importer,
        patch(
            "church_finder_scraper.austria.cli.publish_database",
            return_value=(None, (0, 0), None),
        ),
    ):
        assert (
            cli.dispatch(
                "services",
                [
                    "--consent-google-maps",
                    "--postcode",
                    "2000",
                    "--postcode",
                    "1010",
                    "--postcode",
                    "2000",
                    "--nationwide-state",
                    str(tmp_path / "state.sqlite"),
                ],
            )
            == 0
        )

    options = importer.call_args.args[0]
    assert options.postcodes == ["1010", "2000"]
    assert options.state == tmp_path / "state.sqlite"


@pytest.mark.parametrize(
    "arguments,expected",
    [
        ([], ["1010", "2000", "4020", "5020", "6020", "6900", "7000", "8010", "9020"]),
        (["--vienna-only"], ["1010"]),
    ],
)
def test_services_selects_postcodes_from_geonames(
    arguments: list[str], expected: list[str], tmp_path: Path
):
    with (
        patch("church_finder_scraper.austria.cli.PROJECT_ROOT", tmp_path),
        patch(
            "church_finder_scraper.austria.cli.urlopen",
            return_value=ZipResponse(postcode_archive()),
        ),
        patch("church_finder_scraper.austria.cli.import_database") as importer,
        patch(
            "church_finder_scraper.austria.cli.publish_database",
            return_value=(None, (0, 0), None),
        ),
    ):
        assert cli.dispatch("services", ["--consent-google-maps", *arguments]) == 0

    assert importer.call_args.args[0].postcodes == expected


def test_services_does_not_publish_when_import_fails(tmp_path: Path):
    with (
        patch("church_finder_scraper.austria.cli.PROJECT_ROOT", tmp_path),
        patch(
            "church_finder_scraper.austria.cli.import_database",
            side_effect=RuntimeError("interrupted"),
        ),
        patch("church_finder_scraper.austria.cli.publish_database") as publish,
    ):
        assert cli.dispatch("services", ["--consent-google-maps", "--postcode", "1010"]) == 1
    publish.assert_not_called()


def test_services_default_paths_resume_and_publish_directly(tmp_path: Path):
    checkpoint = tmp_path / ".scraper-state" / "gottesdienst_at_austria.checkpoint.sqlite"
    website = tmp_path / "web/public/data/churches_vienna.database.json"
    website.parent.mkdir(parents=True)
    old = {"churches": [{"uuid": "old"}], "services": {"old": []}}
    website.write_text(json.dumps(old), encoding="utf-8")
    with closing(connect_state(checkpoint, ["1010"], False)) as db:
        save_batch(db, {"postcode": "1010", "results": []})
    with (
        patch("church_finder_scraper.austria.cli.PROJECT_ROOT", tmp_path),
        patch("church_finder_scraper.austria.importer.sync_playwright") as browser,
    ):
        assert cli.dispatch("services", ["--consent-google-maps", "--postcode", "1010"]) == 0

    browser.assert_not_called()
    assert json.loads(website.read_text()) == {"churches": [], "services": {}}
    backups = list((tmp_path / "backups").iterdir())
    assert len(backups) == 1
    assert json.loads(backups[0].read_text()) == old
    assert checkpoint.exists()
    assert not (tmp_path / "data").exists()


def test_services_warns_when_old_default_checkpoint_needs_moving(tmp_path: Path, caplog):
    checkpoint = tmp_path / "data/databases/gottesdienst_at_austria.checkpoint.sqlite"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.touch()
    with (
        patch("church_finder_scraper.austria.cli.PROJECT_ROOT", tmp_path),
        patch("church_finder_scraper.austria.cli.import_database") as importer,
        patch("church_finder_scraper.austria.cli.urlopen") as urlopen,
    ):
        assert cli.dispatch("services", ["--consent-google-maps"]) == 1
    assert "Checkpoint is still at" in caplog.text
    assert "Stop any running importer" in caplog.text
    importer.assert_not_called()
    urlopen.assert_not_called()
    assert checkpoint.exists()


def test_fresh_services_replaces_old_data_and_resumes_after_interruption(tmp_path: Path):
    checkpoint = tmp_path / "checkpoint.sqlite"
    website = tmp_path / "site.json"
    old = {"churches": [{"uuid": "old"}], "services": {"old": []}}
    website.write_text(json.dumps(old), encoding="utf-8")
    with closing(connect_state(checkpoint, ["1010", "2000", "9999"], False)) as db:
        for postcode in ("1010", "2000", "9999"):
            save_batch(db, {"postcode": postcode, "results": []})

    client = MagicMock()
    client.postcode.side_effect = [
        [
            {
                "church": {"id": "new", "name": "New church", "position": None},
                "services": [{"date": "2026-11-13", "start_time": "10:00", "language": "Unknown"}],
            }
        ],
        RuntimeError("interrupted"),
        [],
    ]
    playwright = MagicMock()
    manager = MagicMock()
    manager.__enter__.return_value = playwright
    arguments = [
        "--consent-google-maps",
        "--postcode",
        "1010",
        "--postcode",
        "2000",
        "--state",
        str(checkpoint),
        "--output",
        str(website),
    ]
    with (
        patch("church_finder_scraper.austria.cli.PROJECT_ROOT", tmp_path),
        patch("church_finder_scraper.austria.importer.sync_playwright", return_value=manager),
        patch("church_finder_scraper.austria.importer.start_session", return_value=("s", "t")),
        patch("church_finder_scraper.austria.importer.Client", return_value=client),
        patch("church_finder_scraper.austria.importer.fetch_austria_records", return_value=[]),
    ):
        assert cli.dispatch("services", [*arguments, "--fresh"]) == 1
        assert json.loads(website.read_text()) == old
        with closing(connect_state(checkpoint, ["1010", "2000"], False)) as db:
            assert [batch["postcode"] for batch in load_batches(db)] == ["1010"]
        assert cli.dispatch("services", arguments) == 0

    assert client.postcode.call_args_list == [(("1010",),), (("2000",),), (("2000",),)]
    database = json.loads(website.read_text())
    assert [church["name"] for church in database["churches"]] == ["New church"]
    assert sum(map(len, database["services"].values())) == 1
    backups = list((tmp_path / "backups").iterdir())
    assert len(backups) == 1
    assert json.loads(backups[0].read_text()) == old


def test_services_resumes_completed_checkpoint_and_publishes(tmp_path: Path):
    checkpoint = tmp_path / "checkpoint.sqlite"
    website = tmp_path / "site.json"
    with closing(connect_state(checkpoint, ["1010", "2000"], False)) as db:
        for postcode in ("1010", "2000"):
            save_batch(
                db,
                {
                    "postcode": postcode,
                    "results": [
                        {
                            "church": {
                                "id": postcode,
                                "name": f"Church {postcode}",
                                "position": {"latitude": 48.0, "longitude": 16.0},
                            },
                            "services": [
                                {
                                    "date": "2026-11-13",
                                    "start_time": "10:00",
                                    "language": "Unknown",
                                }
                            ],
                        }
                    ],
                },
            )
    with (
        patch("church_finder_scraper.austria.importer.sync_playwright") as browser,
        patch(
            "church_finder_scraper.austria.importer.fetch_austria_records",
            return_value=[
                {"latitude": 48.0, "longitude": 16.0, "website": "https://church.example"}
            ],
        ),
    ):
        assert (
            cli.dispatch(
                "services",
                [
                    "--consent-google-maps",
                    "--postcode",
                    "1010",
                    "--postcode",
                    "2000",
                    "--state",
                    str(checkpoint),
                    "--website-output",
                    str(website),
                ],
            )
            == 0
        )
    browser.assert_not_called()
    database = json.loads(website.read_text())
    assert {church["name"] for church in database["churches"]} == {"Church 1010", "Church 2000"}
    assert all(church["website"] == "https://church.example" for church in database["churches"])
    assert sum(map(len, database["services"].values())) == 2
