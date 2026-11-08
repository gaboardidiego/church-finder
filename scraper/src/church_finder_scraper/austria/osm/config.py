from __future__ import annotations

import logging

from ...paths import PROJECT_ROOT

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

FALLBACK_OVERPASS_URLS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

OVERPASS_QUERY = """[out:json][timeout:180];
area["boundary"="administrative"]["admin_level"="4"]["name"="Wien"]->.vienna;
(
  nwr["amenity"="place_of_worship"]["religion"="christian"](area.vienna);
  nwr["building"="church"](area.vienna);
);
out center tags;
"""

LOGGER = logging.getLogger("fetch_vienna_churches")

REPOSITORY_ROOT = PROJECT_ROOT

CSV_FIELDS = (
    "osm_type",
    "osm_id",
    "name",
    "religion",
    "denomination",
    "place_of_worship",
    "operator",
    "website",
    "phone",
    "email",
    "opening_hours",
    "addr:full",
    "addr:housenumber",
    "addr:street",
    "addr:postcode",
    "addr:city",
    "latitude",
    "longitude",
    "osm_url",
    "data_source",
    "attribution",
    "tags",
)
