import argparse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from church_finder_scraper import cli


@pytest.mark.parametrize("command", ["osm", "services"])
@pytest.mark.parametrize("country_args", [[], ["--country", "austria"]])
def test_dispatches_to_austria(command: str, country_args: list[str]):
    handler = Mock(return_value=7)
    with patch.object(cli, "import_module", return_value=SimpleNamespace(run=handler)) as load:
        assert cli.dispatch(command, [*country_args, "--example", "value"]) == 7

    load.assert_called_once_with(cli.COUNTRY_MODULES["austria"][command])
    handler.assert_called_once()
    assert handler.call_args.args == (["--example", "value"],)
    parent = handler.call_args.kwargs["parent_parser"]
    assert parent.parse_args([]).country == "austria"


@pytest.mark.parametrize("command", ["osm", "services"])
def test_rejects_unknown_country_before_loading(command: str, capsys: pytest.CaptureFixture[str]):
    with patch.object(cli, "import_module") as load, pytest.raises(SystemExit) as error:
        cli.dispatch(command, ["--country", "unknown"])
    assert error.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
    load.assert_not_called()


@pytest.mark.parametrize("command", ["osm", "services"])
def test_help_includes_country_and_country_specific_options(
    command: str, capsys: pytest.CaptureFixture[str]
):
    with pytest.raises(SystemExit) as error:
        cli.dispatch(command, ["--help"])
    assert error.value.code == 0
    help_text = capsys.readouterr().out
    assert "--country {austria}" in help_text
    assert ("--format" if command == "osm" else "--consent-google-maps") in help_text


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
def test_osm_command_runs_austria_implementation(country_args: list[str], tmp_path: Path):
    output = tmp_path / "churches.json"
    with patch("church_finder_scraper.austria.osm.cli.fetch_records", return_value=[]) as fetch:
        assert (
            cli.dispatch("osm", [*country_args, "--format", "json", "--output", str(output)]) == 0
        )
    fetch.assert_called_once()
    assert output.exists()


@pytest.mark.parametrize("country_args", [[], ["--country", "austria"]])
def test_services_command_preserves_checkpoint_option(country_args: list[str], tmp_path: Path):
    checkpoint = tmp_path / "checkpoint.sqlite"
    with patch("church_finder_scraper.austria.archdiocese.cli.import_database") as importer:
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
