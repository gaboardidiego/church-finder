from __future__ import annotations

import logging
from copy import deepcopy
from math import degrees

import pytest

from church_finder_scraper.austria.client import Client
from church_finder_scraper.austria.database import build_database
from church_finder_scraper.austria.processing import parse_search
from church_finder_scraper.austria.websites import EARTH_RADIUS, enrich_websites

RESULT = """
<form id="site_search_gottesdienste" action="/site/search"></form>
<div id="gdList">
  <div class="resultList">
    <div class="item" id="item_95081">
      <div class="marker" id="kirche_95081">
        <div class="title">Pfarrkirche Mülln</div>
        <div class="address">5020 Salzburg, Augustinergasse 1</div>
      </div>
      <div class="gdItem">
        <div class="weekday">
          <div class="daymonth">08.11.</div>
          <div class="year">2026</div>
        </div>
        <div class="datum"><span>10:30 Uhr</span> (Heilige Messe)</div>
      </div>
      <div class="gdItem">
        <div class="weekday">
          <div class="daymonth">09.11.</div>
          <div class="year">2026</div>
        </div>
        <div class="datum"><span>19:00 Uhr</span> (Heilige Messe, Englisch)</div>
      </div>
    </div>
  </div>
</div>
<script>
var point = new google.maps.LatLng(47.805, 13.034);
markerId = "95081";
</script>
"""


def test_parse_search_parses_location_services_and_map_position():
    result = parse_search(RESULT)

    assert result == [
        {
            "church": {
                "id": "95081",
                "name": "Pfarrkirche Mülln",
                "address": "5020 Salzburg, Augustinergasse 1",
                "position": {"latitude": 47.805, "longitude": 13.034},
            },
            "services": [
                {"date": "2026-11-08", "start_time": "10:30", "language": "Unknown"},
                {"date": "2026-11-09", "start_time": "19:00", "language": "English"},
            ],
        }
    ]


def test_parse_search_accepts_no_results_but_rejects_unexpected_layout():
    assert parse_search('<form id="site_search_gottesdienste"></form>') == []
    with pytest.raises(ValueError, match="search form missing"):
        parse_search("<p>Search failed</p>")


def test_parse_search_skips_undated_service_with_warning(caplog):
    undated = RESULT.replace("08.11.", "").replace("2026", "", 1)
    caplog.set_level(logging.WARNING, logger="gottesdienst_at")

    result = parse_search(undated)

    assert result[0]["services"] == [
        {"date": "2026-11-09", "start_time": "19:00", "language": "English"}
    ]
    assert any(
        "Skipping undated Gottesdienst.at service for church 95081" in message
        and "10:30 Uhr" in message
        for message in caplog.messages
    )


@pytest.mark.parametrize(
    "day,year", [("", "2026"), ("08.11.", ""), ("08.11.2026", ""), ("31.02.", "2026")]
)
def test_parse_search_rejects_incomplete_or_invalid_dates(day, year):
    result = RESULT.replace("2026", year, 1).replace("08.11.", day)
    with pytest.raises(ValueError, match="Invalid Gottesdienst.at service date.*church 95081"):
        parse_search(result)


def test_client_queries_gottesdienst_at_by_postcode():
    class Response:
        ok = True
        status = 200

        def text(self):
            return RESULT

    class Request:
        def fetch(self, url, method, timeout, **kwargs):
            self.arguments = (url, method, timeout, kwargs)
            return Response()

    request = Request()
    result = Client(type("Context", (), {"request": request})(), "26150", "token", 0).postcode(
        "5020"
    )

    assert result[0]["church"]["name"] == "Pfarrkirche Mülln"
    assert (
        request.arguments[0]
        == "https://www.gottesdienst.at/site/gottesdienstsuche_search_popup.siteswift"
    )
    assert request.arguments[1] == "GET"
    assert request.arguments[3]["params"] == {
        "so": "all",
        "do": "all",
        "c": "getfind",
        "s": "26150",
        "t": "token",
        "d": "gd_plz:5020;bundesland:;gottesdienstart:;art:",
    }


def test_build_database_deduplicates_services_across_postcodes():
    entry = parse_search(RESULT)[0]
    database = build_database(
        [
            {"postcode": "5020", "results": [entry]},
            {"postcode": "5021", "results": [entry]},
        ]
    )

    assert len(database["churches"]) == 1
    church_id = database["churches"][0]["uuid"]
    assert database["services"][church_id] == entry["services"]


@pytest.mark.parametrize("missing_first", [False, True])
def test_build_database_merges_missing_positions(missing_first):
    complete = parse_search(RESULT)[0]
    missing = deepcopy(complete)
    missing["church"]["position"] = None
    missing["services"] = missing["services"][:1]
    entries = [missing, complete] if missing_first else [complete, missing]

    database = build_database(
        [{"postcode": str(index), "results": [entry]} for index, entry in enumerate(entries)]
    )

    assert len(database["churches"]) == 1
    church = database["churches"][0]
    assert church["position"] == complete["church"]["position"]
    assert database["services"][church["uuid"]] == complete["services"]


@pytest.mark.parametrize("field", ["name", "position"])
def test_build_database_rejects_conflicting_known_details(field):
    first = parse_search(RESULT)[0]
    second = deepcopy(first)
    second["church"][field] = (
        "Different church" if field == "name" else {"latitude": 48.0, "longitude": 13.0}
    )

    with pytest.raises(ValueError, match="Conflicting church details across postcodes: 95081"):
        build_database([{"results": [first]}, {"results": [second]}])


def test_website_enrichment_uses_merged_position_and_contact_website():
    complete = parse_search(RESULT)[0]
    missing = deepcopy(complete)
    missing["church"]["position"] = None
    database = build_database([{"results": [missing]}, {"results": [complete]}])
    enrich_websites(
        database,
        [
            {
                "latitude": 47.805,
                "longitude": 13.034,
                "website": "",
                "tags": {"contact:website": "www.pfarre.example"},
            }
        ],
    )
    assert database["churches"][0]["website"] == "https://www.pfarre.example"


@pytest.mark.parametrize(
    "records",
    [
        [{"latitude": 47.805, "longitude": 13.034, "website": "javascript:alert(1)"}],
        [
            {
                "latitude": 47.805,
                "longitude": 13.034,
                "website": "https://a.example;https://b.example",
            }
        ],
        [{"latitude": 47.807, "longitude": 13.034, "website": "https://far.example"}],
        [
            {"latitude": 47.805, "longitude": 13.034, "website": "https://a.example"},
            {"latitude": 47.805, "longitude": 13.034, "website": "https://b.example"},
        ],
        [
            {"latitude": 47.805, "longitude": 13.034, "website": ""},
            {"latitude": 47.8051, "longitude": 13.034, "website": "https://b.example"},
        ],
    ],
)
def test_website_enrichment_skips_invalid_distant_or_ambiguous_matches(records):
    database = build_database([{"results": [parse_search(RESULT)[0]]}])
    enrich_websites(database, records)
    assert "website" not in database["churches"][0]


def test_website_enrichment_accepts_duplicate_osm_features_with_the_same_website():
    database = build_database([{"results": [parse_search(RESULT)[0]]}])
    enrich_websites(
        database,
        [
            {"latitude": 47.805, "longitude": 13.034, "website": "https://a.example"},
            {"latitude": 47.805, "longitude": 13.034, "website": "https://a.example"},
        ],
    )
    assert database["churches"][0]["website"] == "https://a.example"


@pytest.mark.parametrize("distance,expected", [(49.99, True), (50.01, False)])
def test_website_enrichment_distance_cutoff(distance, expected):
    database = build_database([{"results": [parse_search(RESULT)[0]]}])
    enrich_websites(
        database,
        [
            {
                "latitude": 47.805 + degrees(distance / EARTH_RADIUS),
                "longitude": 13.034,
                "website": "https://a.example",
            }
        ],
    )
    assert ("website" in database["churches"][0]) is expected


def test_website_enrichment_handles_missing_or_invalid_coordinates():
    first = parse_search(RESULT)[0]
    second = deepcopy(first)
    second["church"]["id"] = "2"
    second["church"]["position"] = None
    database = build_database([{"results": [first, second]}])
    enrich_websites(
        database,
        [
            {"latitude": "nan", "longitude": 13.034, "website": "https://invalid.example"},
            {"latitude": 47.805, "longitude": 13.034, "website": "https://valid.example"},
        ],
    )
    assert (
        sum(church.get("website") == "https://valid.example" for church in database["churches"])
        == 1
    )
