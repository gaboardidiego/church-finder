import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import fetch_erzdioezese_services as importer
import fetch_vienna_churches as osm_importer


FORM = """
<form id="site_search_gottesdienste" action="/site/search">
  <select name="sprache"><option value=""></option>
    <option value="Deutsch">Deutsch</option><option value="Englisch">Englisch</option>
  </select>
</form>
"""
MARKER = """
<div class="gdList"><div class="item"><div class="marker" id="kirche_2712">
  <div class="title">Stephansdom</div><div class="address">1010 Wien, Stephanspl. 1</div>
  <div class="marker_addr">Stephanspl. 1</div>
</div></div></div>
<script>var point = new google.maps.LatLng(48.208411, 16.373471);
marker = createMarker(point, '2712', '', 'Stephansdom', htmlcontent, '');</script>
"""
EMPTY = "Für Ihre Suche wurden keine Gottsdienste gefunden."
ROW = {
    "coid": 2712, "datum": "2026-11-08", "uhrzeit": "12:00:00",
    "art": "Hl. Messe", "loc_title": "Stephansdom", "loc_adresse": "Stephanspl. 1",
}


class Response:
    def __init__(self, value):
        self.value = value
        self.ok = True
        self.status = 200

    def text(self):
        return self.value

    def json(self):
        return self.value


class FakeRequest:
    def __init__(self):
        self.language = ""

    def fetch(self, url, method, timeout, **kwargs):
        if method == "GET":
            return Response(FORM + MARKER)
        if "xhr_dates_for_coid" in url:
            return Response({"0": ROW, "html": "listing"})
        self.language = kwargs["form"]["sprache"]
        return Response(FORM + (MARKER if self.language == "Englisch" else EMPTY))


class Tests(unittest.TestCase):
    def test_osm_fetcher_shared_record_conversion(self):
        element = {"type": "node", "id": 7, "lat": 48.208411, "lon": 16.373471,
                   "tags": {"name": "Stephansdom", "website": "https://church.example"}}
        with patch.object(osm_importer, "fetch_elements", return_value=[element]) as fetch:
            records = osm_importer.fetch_records("https://overpass.example/api", 10, 0)
        fetch.assert_called_once_with("https://overpass.example/api", 10, 0)
        self.assertEqual(records[0]["website"], "https://church.example")
        self.assertEqual(records[0]["latitude"], 48.208411)
        self.assertEqual(records[0]["osm_url"], "https://www.openstreetmap.org/node/7")

    def test_geonames_postcodes_are_unique_and_restricted_to_region(self):
        content = (
            "AT\t1010\tWien\tWien\nAT\t1010\tWien\tWien\n"
            "AT\t2000\tStockerau\tNiederösterreich\nAT\t7000\tEisenstadt\tBurgenland\n"
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("AT.txt", content)
        self.assertEqual(importer.candidate_postcodes(buffer.getvalue()), ["1010", "2000"])
        self.assertEqual(
            importer.candidate_postcodes(buffer.getvalue(), ("Wien",)),
            ["1010"],
        )

    def test_parse_church_and_empty_search(self):
        churches, action, languages, _ = importer.parse_search(FORM + MARKER)
        self.assertEqual(churches[0]["id"], "2712")
        self.assertEqual(churches[0]["position"]["latitude"], 48.208411)
        self.assertEqual(languages, ["Deutsch", "Englisch"])
        self.assertTrue(action.startswith("https://www.erzdioezese-wien.at/"))
        self.assertEqual(importer.parse_search(FORM + EMPTY)[0], [])
        with self.assertRaises(ValueError):
            importer.parse_search("<p>consent required</p>")

    def test_filter_matches_language_and_retains_source_type(self):
        context = type("Context", (), {"request": FakeRequest()})()
        client = importer.Client(context, "site", "token", 0)
        results = client.postcode("1010", True)
        self.assertEqual(results[0]["services"], [{
            "date": "2026-11-08", "start_time": "12:00", "language": "English",
            "service_type": "Hl. Messe", "description": "", "service_type_details": "",
            "short_info": "",
        }])

    def test_duplicate_identity_is_not_assigned_a_speculative_language(self):
        key = importer.service_key(ROW)
        services = importer.normalize_services([ROW, ROW], {key: {"Englisch"}})
        self.assertEqual([service["language"] for service in services], ["Unknown", "Unknown"])

    def test_osm_website_requires_nearby_coordinates_and_a_website(self):
        source = {"latitude": 48.208411, "longitude": 16.373471}
        nearby = {"latitude": 48.2085, "longitude": 16.3735, "website": "https://church.example",
                  "osm_url": "https://www.openstreetmap.org/node/1"}
        self.assertIs(importer.match_osm_website(source, [nearby]), nearby)
        self.assertIsNone(importer.match_osm_website(
            source, [{**nearby, "latitude": 48.21}], 100))
        self.assertIsNone(importer.match_osm_website(
            source, [{key: value for key, value in nearby.items() if key != "website"}]))
        self.assertIsNone(importer.match_osm_website(source, [
            {**nearby, "latitude": 48.20842},
            {**nearby, "osm_url": "https://www.openstreetmap.org/node/2",
             "latitude": source["latitude"], "longitude": source["longitude"]},
        ]))

    def test_malformed_service_and_nonzero_seconds_fail(self):
        with self.assertRaises(ValueError):
            importer.parse_services({"0": {**ROW, "uhrzeit": "12:00:01"}, "html": ""}, "2712")
        with self.assertRaises(ValueError):
            importer.parse_services({"0": {**ROW, "coid": 1}, "html": ""}, "2712")
        with self.assertRaises(ValueError):
            importer.parse_services({}, "2712")

    def test_database_and_checkpoint_configuration(self):
        church = importer.parse_search(FORM + MARKER)[0][0]
        batch = {"postcode": "1010", "completed_at": "2026-11-06T12:00:00+00:00",
                 "results": [{"church": church, "services": importer.normalize_services([ROW], {})}]}
        website = {"latitude": 48.208411, "longitude": 16.373471,
                   "website": "https://church.example",
                   "osm_url": "https://www.openstreetmap.org/node/1"}
        database = importer.build_database([batch, batch], ["1010"], False, [website], 100)
        self.assertEqual(len(database["churches"]), 1)
        self.assertEqual(database["churches"][0]["website"], "https://church.example")
        church_record = database["churches"][0]
        self.assertEqual(set(database), {"churches", "services"})
        self.assertEqual(set(church_record), {
            "uuid", "name", "website", "position", "religion", "denomination",
        })
        self.assertEqual(church_record["position"], {
            "latitude": 48.208411, "longitude": 16.373471,
        })
        self.assertEqual(database["services"], {
            church_record["uuid"]: [{
                "language": "Unknown", "start_time": "12:00", "date": "2026-11-08",
            }],
        })
        json.dumps(database)
        without_website = importer.build_database([batch], ["1010"], False, [], 100)
        self.assertNotIn("website", without_website["churches"][0])
        without_position = {**church, "position": None}
        no_position_batch = {**batch, "results": [{
            "church": without_position, "services": [],
        }]}
        no_position_database = importer.build_database(
            [no_position_batch], ["1010"], False, [], 100,
        )
        self.assertEqual(set(no_position_database["churches"][0]), {
            "uuid", "name", "religion", "denomination",
        })
        self.assertEqual(no_position_database["services"][no_position_database["churches"][0]["uuid"]], [])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.sqlite"
            db = importer.connect_state(path, ["1010"], True)
            db.close()
            with self.assertRaises(ValueError):
                importer.connect_state(path, ["1010"], False)


if __name__ == "__main__":
    unittest.main()
