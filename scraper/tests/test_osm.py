import csv
import json
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

from church_finder_scraper.osm.config import FALLBACK_OVERPASS_URLS
from church_finder_scraper.osm.fetch import fetch_elements, fetch_records
from church_finder_scraper.osm.records import make_record, write_csv, write_json


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
    with patch("church_finder_scraper.osm.fetch.urlopen", return_value=Response({"elements": []})):
        assert fetch_elements("https://overpass.example", 10, 0) == []
    with patch(
        "church_finder_scraper.osm.fetch.urlopen", return_value=Response({"elements": [None]})
    ):
        try:
            fetch_elements("https://overpass.example", 10, 0)
        except RuntimeError as error:
            assert "malformed element" in str(error)
        else:
            raise AssertionError("Malformed Overpass elements must fail")


def test_fetch_records_deduplicates_and_sorts():
    element = {"type": "node", "id": 8, "lat": 48.2, "lon": 16.3, "tags": {"name": "Z"}}
    another = {"type": "node", "id": 9, "lat": 48.2, "lon": 16.3, "tags": {"name": "A"}}
    with patch(
        "church_finder_scraper.osm.fetch.fetch_elements", return_value=[element, another, element]
    ):
        records = fetch_records("https://overpass.example", 10, 0)
    assert [record["name"] for record in records] == ["A", "Z"]


def test_record_conversion_and_output_formats(tmp_path: Path):
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

    csv_path = tmp_path / "churches.csv"
    json_path = tmp_path / "churches.json"
    write_csv(csv_path, [record])
    write_json(json_path, [record], "2026-11-06T12:00:00+00:00")
    with csv_path.open(encoding="utf-8", newline="") as stream:
        csv_record = next(csv.DictReader(stream))
    assert json.loads(csv_record["tags"])["name"] == "Kirche"
    assert json.loads(json_path.read_text(encoding="utf-8"))["results"] == [record]


def test_fetch_retries_transient_errors():
    with (
        patch(
            "church_finder_scraper.osm.fetch.urlopen",
            side_effect=[URLError("unavailable"), Response({"elements": []})],
        ) as request,
        patch("church_finder_scraper.osm.fetch.time.sleep") as sleep,
    ):
        assert fetch_elements("https://overpass.example", 10, 1) == []
    assert request.call_count == 2
    sleep.assert_called_once_with(1)


def test_fetch_does_not_retry_permanent_http_error():
    error = HTTPError("https://overpass.example", 403, "forbidden", None, None)
    with (
        patch("church_finder_scraper.osm.fetch.urlopen", side_effect=error) as request,
        pytest.raises(RuntimeError, match="HTTP 403"),
    ):
        fetch_elements("https://overpass.example", 10, 2)
    assert request.call_count == 1


def test_fetch_records_falls_back_to_another_endpoint():
    with patch(
        "church_finder_scraper.osm.fetch.fetch_elements",
        side_effect=[RuntimeError("unavailable"), []],
    ) as fetch:
        assert fetch_records("https://overpass.example", 10, 0) == []
    assert [call.args[0] for call in fetch.call_args_list] == [
        "https://overpass.example",
        FALLBACK_OVERPASS_URLS[0],
    ]
