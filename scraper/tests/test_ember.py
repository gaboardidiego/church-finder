import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

import pytest

from church_finder_scraper.italy import ember


def church(church_id: str = "first", **overrides) -> dict:
    return {
        "id": church_id,
        "name": "Example church",
        "countryCode": "IT",
        "lat": 41.9,
        "lng": 12.5,
        "timezone": "Europe/Rome",
        "status": None,
        "lastVerifiedAt": "2020-08-03",
        "hasStructuredSchedule": True,
        "services": [
            {
                "kind": "mass",
                "rrule": "FREQ=WEEKLY;BYDAY=SU",
                "startTime": "09:30",
                "language": "it",
            },
            {"kind": "confession", "rrule": "FREQ=DAILY", "startTime": "10:00"},
        ],
        "links": [{"kind": "website", "url": "https://example.org"}],
        "email": "not-retained@example.org",
        **overrides,
    }


def test_expands_weekly_rules_with_exceptions_and_additions():
    rows = ember.expand_mass(
        {
            "rrule": "FREQ=WEEKLY;BYDAY=SU",
            "startTime": "09:30",
            "language": "it",
            "exdate": "2026-03-29",
            "rdate": "2026-03-30,2026-04-05",
        },
        date(2026, 3, 28),
    )
    assert [row["date"] for row in rows] == [
        "2026-03-30",
        "2026-04-05",
        "2026-04-12",
        "2026-04-19",
        "2026-04-26",
    ]
    assert all(row["start_time"] == "09:30" and row["language"] == "Italian" for row in rows)


def test_expands_finite_and_month_restricted_rules():
    assert [
        row["date"]
        for row in ember.expand_mass(
            {"rrule": "DTSTART:20261101T000000\nRRULE:FREQ=DAILY;COUNT=4", "startTime": "08:00"},
            date(2026, 11, 2),
        )
    ] == ["2026-11-02", "2026-11-03", "2026-11-04"]
    assert [
        row["date"]
        for row in ember.expand_mass(
            {"rrule": "FREQ=WEEKLY;BYDAY=MO;BYMONTH=12;UNTIL=20261214", "startTime": "08:00"},
            date(2026, 11, 18),
        )
    ] == ["2026-12-07", "2026-12-14"]


@pytest.mark.parametrize(
    "service",
    [
        {"rrule": "FREQ=HOURLY", "startTime": "09:00"},
        {"rrule": "FREQ=DAILY;BYHOUR=10", "startTime": "09:00"},
        {"rrule": "FREQ=WEEKLY;BYDAY=NOPE", "startTime": "09:00"},
        {"rrule": "FREQ=DAILY", "startTime": "25:00"},
        {"rrule": "FREQ=DAILY", "startTime": "09:00", "exdate": "bad"},
    ],
)
def test_invalid_rules_or_times_fail_explicitly(service: dict):
    with pytest.raises(ValueError):
        ember.expand_mass(service, date(2026, 11, 18))


def test_normalizes_church_and_only_mass_services():
    result = ember.normalize_church(church(), datetime(2026, 11, 18, tzinfo=UTC))
    assert result is not None
    assert result["church"]["position"] == {"latitude": 41.9, "longitude": 12.5}
    assert result["church"]["website"] == "https://example.org"
    assert result["church"]["schedule_source"] == "ember"
    assert result["church"]["last_verified_at"] == "2020-08-03"
    assert result["church"]["region"].startswith("italy-ember-")
    assert len(result["services"]) == 4
    assert all(
        row["language"] == "Italian" and row["start_time"] == "09:30" for row in result["services"]
    )
    assert ember.normalize_church(church(status="closed"), datetime.now(UTC)) is None


def test_compact_page_removes_contact_information_and_validates_cursor():
    page = ember.compact_page({"churches": [church()], "next": "first"}, "")
    assert "email" not in page["churches"][0]
    with pytest.raises(ValueError, match="pagination cursor"):
        ember.compact_page({"churches": [church()], "next": "other"}, "")
    with pytest.raises(ValueError, match="unordered"):
        ember.compact_page({"churches": [church(), church()]}, "")


def test_client_paces_requests_and_identifies_itself():
    client = ember.EmberClient(1)
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = b'{"churches":[]}'
    with (
        patch("church_finder_scraper.italy.ember.urlopen", return_value=response) as urlopen,
        patch(
            "church_finder_scraper.italy.ember.time.monotonic",
            side_effect=[10.0, 10.25, 11.0],
        ),
        patch("church_finder_scraper.italy.ember.time.sleep") as sleep,
    ):
        client.page("")
        client.page("first", "FR")
    sleep.assert_called_once_with(0.75)
    assert urlopen.call_args_list[0].args[0].get_header("User-agent") == "church-finder/1.0"
    assert "country=IT" in urlopen.call_args_list[0].args[0].full_url
    assert "after=first" in urlopen.call_args_list[1].args[0].full_url
    assert "country=FR" in urlopen.call_args_list[1].args[0].full_url
    with pytest.raises(ValueError, match="at least one second"):
        ember.EmberClient(0.5)


def test_client_retries_transient_errors_with_pacing(caplog):
    client = ember.EmberClient(3)
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = b'{"churches":[]}'
    clock = [0.0]
    request_times = []

    def sleep(delay):
        clock[0] += delay

    def request(*args, **kwargs):
        request_times.append(clock[0])
        if len(request_times) == 1:
            raise HTTPError("https://example.org", 500, "Internal Server Error", None, None)
        if len(request_times) == 2:
            raise URLError("offline")
        return response

    with (
        patch("church_finder_scraper.italy.ember.urlopen", side_effect=request) as urlopen,
        patch("church_finder_scraper.italy.ember.time.monotonic", side_effect=lambda: clock[0]),
        patch("church_finder_scraper.italy.ember.time.sleep", side_effect=sleep),
    ):
        assert client.page("cursor", "AD") == {"churches": []}
    assert request_times == [0, 3, 6]
    assert len({call.args[0].full_url for call in urlopen.call_args_list}) == 1
    assert "AD" in caplog.text and "retrying" in caplog.text


@pytest.mark.parametrize("status, attempts", [(403, 1), (500, 4), (429, 4)])
def test_client_stops_on_permanent_or_exhausted_http_errors(status, attempts):
    error = HTTPError("https://example.org", status, "failure", None, None)
    with (
        patch("church_finder_scraper.italy.ember.urlopen", side_effect=error) as urlopen,
        patch("church_finder_scraper.italy.ember.time.sleep"),
        patch("church_finder_scraper.italy.ember.time.monotonic", return_value=0),
        pytest.raises(HTTPError) as caught,
    ):
        ember.EmberClient(1).page("", "AD")
    assert caught.value.code == status
    assert urlopen.call_count == attempts


def test_checkpoint_resumes_and_refreshes_stale_pages(tmp_path: Path):
    state = tmp_path / "ember.sqlite"
    client = Mock()
    first = {"churches": [church("first")], "next": "first"}
    second = {"churches": [church("second")]}
    client.page.side_effect = [first, OSError("offline")]
    with patch("church_finder_scraper.italy.ember.EmberClient", return_value=client):
        with pytest.raises(OSError, match="offline"):
            ember.import_database(state, 1)
        client.page.side_effect = [second]
        result = ember.import_database(state, 1)
    assert len(result["churches"]) == 2
    assert client.page.call_args_list == [(("", "IT"),), (("first", "IT"),), (("first", "IT"),)]
    with sqlite3.connect(state) as db:
        cached = db.execute("SELECT data FROM ember_pages WHERE cursor='first'").fetchone()[0]
        assert "email" not in json.loads(cached)["churches"][0]
        db.execute(
            "UPDATE ember_pages SET fetched_at=?",
            ((datetime.now(UTC) - timedelta(days=2)).isoformat(),),
        )
    client.reset_mock()
    client.page.side_effect = [first, second]
    with patch("church_finder_scraper.italy.ember.EmberClient", return_value=client):
        ember.import_database(state, 1)
    assert client.page.call_args_list == [(("", "IT"),), (("first", "IT"),)]
    client.reset_mock()
    client.page.side_effect = [first, second]
    with patch("church_finder_scraper.italy.ember.EmberClient", return_value=client):
        ember.import_database(state, 1, fresh=True)
    assert client.page.call_args_list == [(("", "IT"),), (("first", "IT"),)]


def test_europe_checkpoint_resumes_per_country_and_validates_scope(tmp_path: Path):
    state = tmp_path / "europe.sqlite"
    client = Mock()
    italian = {"churches": [church("it")]}
    french = {"churches": [church("fr", countryCode="FR", timezone="Europe/Paris")]}
    client.page.side_effect = [italian, OSError("offline")]
    countries = ("IT", "FR", "DE")
    with patch("church_finder_scraper.italy.ember.EmberClient", return_value=client):
        with pytest.raises(OSError, match="offline"):
            ember.import_database(state, 1, countries=countries)
        client.page.side_effect = [french, {"churches": []}]
        result = ember.import_database(state, 1, countries=countries)
        assert client.page.call_args_list == [
            (("", "IT"),),
            (("", "FR"),),
            (("", "FR"),),
            (("", "DE"),),
        ]
        assert {item["region"].split("-")[0] for item in result["churches"]} == {"italy", "ember"}
        with pytest.raises(ValueError, match="different country selection"):
            ember.import_database(state, 1)
        client.page.side_effect = [italian]
        assert len(ember.import_database(state, 1, fresh=True)["churches"]) == 1


def test_rejects_mismatched_countries_and_empty_import(tmp_path: Path):
    with pytest.raises(ValueError, match="Unexpected Ember country"):
        ember.normalize_church(church(countryCode="AT"), datetime.now(UTC), "FR")
    client = Mock()
    client.page.return_value = {"churches": []}
    with patch("church_finder_scraper.italy.ember.EmberClient", return_value=client):
        with pytest.raises(ValueError, match="no usable churches"):
            ember.import_database(tmp_path / "empty.sqlite", 1, countries=("FR",))
        with pytest.raises(ValueError, match="country selection"):
            ember.import_database(tmp_path / "invalid.sqlite", 1, countries=("AT",))


def test_europe_cli_uses_separate_checkpoint_and_all_non_austrian_countries(tmp_path: Path):
    from church_finder_scraper import cli

    record = ember.normalize_church(
        church(countryCode="FR", timezone="Europe/Paris"), datetime(2026, 11, 18, tzinfo=UTC), "FR"
    )
    assert record is not None
    database = {
        "churches": [record["church"]],
        "services": {record["church"]["uuid"]: record["services"]},
    }
    with patch("church_finder_scraper.italy.cli.import_ember", return_value=database) as importer:
        assert (
            cli.dispatch(
                "services", ["--country", "europe", "--output", str(tmp_path / "index.json")]
            )
            == 0
        )
    assert importer.call_args.args[0].name == "ember_europe.checkpoint.sqlite"
    assert importer.call_args.kwargs["countries"] == ember.EUROPE_COUNTRIES
    assert "IT" in ember.EUROPE_COUNTRIES and "FR" in ember.EUROPE_COUNTRIES
    assert "AT" not in ember.EUROPE_COUNTRIES
    index = json.loads((tmp_path / "index.json").read_text())
    assert index["churches"][0]["region"].startswith("ember-fr-")


def test_europe_cli_keeps_previous_index_when_a_country_fails(tmp_path: Path):
    from church_finder_scraper import cli

    output = tmp_path / "index.json"
    output.write_text('{"previous":true}', encoding="utf-8")
    client = Mock()
    client.page.side_effect = [
        {"churches": [church("first", countryCode="AL")]},
        OSError("offline"),
    ]
    with patch("church_finder_scraper.italy.ember.EmberClient", return_value=client):
        assert (
            cli.dispatch(
                "services",
                [
                    "--country",
                    "europe",
                    "--state",
                    str(tmp_path / "state.sqlite"),
                    "--output",
                    str(output),
                ],
            )
            == 1
        )
    assert json.loads(output.read_text()) == {"previous": True}


@pytest.mark.parametrize("source_args", [[], ["--source", "ember"]])
def test_ember_cli_uses_its_own_checkpoint_and_publishes(tmp_path: Path, source_args: list[str]):
    from church_finder_scraper import cli

    result = ember.normalize_church(church(), datetime(2026, 11, 18, tzinfo=UTC))
    assert result is not None
    database = {
        "churches": [result["church"]],
        "services": {result["church"]["uuid"]: result["services"]},
    }
    output = tmp_path / "italy.json"
    with patch("church_finder_scraper.italy.cli.import_ember", return_value=database) as importer:
        assert (
            cli.dispatch("services", ["--country", "italy", *source_args, "--output", str(output)])
            == 0
        )
    assert importer.call_args.args[0].name == "ember_italy.checkpoint.sqlite"
    index = json.loads(output.read_text(encoding="utf-8"))
    published_church = index["churches"][0]
    assert published_church["schedule_source"] == "ember"
    assert published_church["service_index"] == {
        "Italian": ["2026-11-22", "2026-11-29", "2026-12-06", "2026-12-13"]
    }
    schedule = json.loads(
        (output.parent / index["service_files"][published_church["region"]]).read_text(
            encoding="utf-8"
        )
    )
    assert schedule["services"][published_church["uuid"]] == result["services"]
    with pytest.raises(SystemExit):
        cli.dispatch("services", ["--country", "italy", "--source", "ember", "--diocese", "rome"])
    with pytest.raises(SystemExit):
        cli.dispatch("services", ["--country", "italy", "--source", "orarimesse"])
