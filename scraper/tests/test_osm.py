import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs

import pytest

from church_finder_scraper.austria.osm.config import FALLBACK_OVERPASS_URLS
from church_finder_scraper.austria.osm.fetch import fetch_elements, fetch_records
from church_finder_scraper.austria.osm.records import make_record
from church_finder_scraper.austria.websites import AUSTRIA_OVERPASS_QUERY, fetch_austria_records


class Response:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.value).encode()


def test_fetch_elements_validates_response_shape():
    with patch(
        "church_finder_scraper.austria.osm.fetch.urlopen", return_value=Response({"elements": []})
    ):
        assert fetch_elements("https://overpass.example", 10, 0, query=AUSTRIA_OVERPASS_QUERY) == []
    with patch(
        "church_finder_scraper.austria.osm.fetch.urlopen",
        return_value=Response({"elements": [None]}),
    ):
        try:
            fetch_elements("https://overpass.example", 10, 0, query=AUSTRIA_OVERPASS_QUERY)
        except RuntimeError as error:
            assert "malformed element" in str(error)
        else:
            raise AssertionError("Malformed Overpass elements must fail")


def test_fetch_records_deduplicates_and_sorts():
    element = {"type": "node", "id": 8, "lat": 48.2, "lon": 16.3, "tags": {"name": "Z"}}
    another = {"type": "node", "id": 9, "lat": 48.2, "lon": 16.3, "tags": {"name": "A"}}
    with patch(
        "church_finder_scraper.austria.osm.fetch.fetch_elements",
        return_value=[element, another, element],
    ):
        records = fetch_records("https://overpass.example", 10, 0, query=AUSTRIA_OVERPASS_QUERY)
    assert [record["name"] for record in records] == ["A", "Z"]


def test_record_conversion():
    record = make_record(
        {
            "type": "way",
            "id": 42,
            "center": {"lat": 48.2, "lon": 16.3},
            "tags": {"name": "Kirche", "website": "https://church.example"},
        }
    )
    assert record["latitude"] == 48.2
    assert record["osm_url"] == "https://www.openstreetmap.org/way/42"

    assert record["tags"]["name"] == "Kirche"
    assert record["website"] == "https://church.example"


def test_fetch_retries_transient_errors():
    with (
        patch(
            "church_finder_scraper.austria.osm.fetch.urlopen",
            side_effect=[URLError("unavailable"), Response({"elements": []})],
        ) as request,
        patch("church_finder_scraper.austria.osm.fetch.time.sleep") as sleep,
    ):
        assert fetch_elements("https://overpass.example", 10, 1, query=AUSTRIA_OVERPASS_QUERY) == []
    assert request.call_count == 2
    sleep.assert_called_once_with(1)


def test_fetch_does_not_retry_permanent_http_error():
    error = HTTPError("https://overpass.example", 403, "forbidden", None, None)
    with (
        patch("church_finder_scraper.austria.osm.fetch.urlopen", side_effect=error) as request,
        pytest.raises(RuntimeError, match="HTTP 403"),
    ):
        fetch_elements("https://overpass.example", 10, 2, query=AUSTRIA_OVERPASS_QUERY)
    assert request.call_count == 1


def test_fetch_records_falls_back_to_another_endpoint():
    with patch(
        "church_finder_scraper.austria.osm.fetch.fetch_elements",
        side_effect=[RuntimeError("unavailable"), []],
    ) as fetch:
        assert fetch_records("https://overpass.example", 10, 0, query=AUSTRIA_OVERPASS_QUERY) == []
    assert [call.args[0] for call in fetch.call_args_list] == [
        "https://overpass.example",
        FALLBACK_OVERPASS_URLS[0],
    ]


def test_austria_websites_use_nationwide_query():
    with patch("church_finder_scraper.austria.websites.fetch_records", return_value=[]) as fetch:
        assert fetch_austria_records() == []
    fetch.assert_called_once_with(query=AUSTRIA_OVERPASS_QUERY)
    assert '["ISO3166-1"="AT"]' in AUSTRIA_OVERPASS_QUERY
    assert "area.austria" in AUSTRIA_OVERPASS_QUERY


def test_fetch_elements_sends_the_selected_query():
    with patch(
        "church_finder_scraper.austria.osm.fetch.urlopen",
        return_value=Response({"elements": []}),
    ) as urlopen:
        fetch_elements("https://overpass.example", 10, 0, query=AUSTRIA_OVERPASS_QUERY)
    request = urlopen.call_args.args[0]
    assert parse_qs(request.data.decode())["data"] == [AUSTRIA_OVERPASS_QUERY]
