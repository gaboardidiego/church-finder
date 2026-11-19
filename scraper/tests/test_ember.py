import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

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
        client.page("first")
    sleep.assert_called_once_with(0.75)
    assert urlopen.call_args_list[0].args[0].get_header("User-agent") == "church-finder/1.0"
    assert "after=first" in urlopen.call_args_list[1].args[0].full_url
    with pytest.raises(ValueError, match="at least one second"):
        ember.EmberClient(0.5)


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
    assert client.page.call_args_list == [(("",),), (("first",),), (("first",),)]
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
    assert client.page.call_args_list == [(("",),), (("first",),)]
    client.reset_mock()
    client.page.side_effect = [first, second]
    with patch("church_finder_scraper.italy.ember.EmberClient", return_value=client):
        ember.import_database(state, 1, fresh=True)
    assert client.page.call_args_list == [(("",),), (("first",),)]


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
