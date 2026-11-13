from __future__ import annotations

import logging

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

FALLBACK_OVERPASS_URLS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

LOGGER = logging.getLogger("fetch_austria_churches")

RECORD_FIELDS = (
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
