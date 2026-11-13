from __future__ import annotations

import io
import re
import zipfile

POSTCODES = "https://download.geonames.org/export/zip/AT.zip"
AUSTRIAN_REGIONS = (
    "Wien",
    "Burgenland",
    "Kärnten",
    "Niederösterreich",
    "Oberösterreich",
    "Salzburg",
    "Steiermark",
    "Tirol",
    "Vorarlberg",
)


def candidate_postcodes(payload: bytes, regions: tuple[str, ...]) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        rows = archive.read("AT.txt").decode("utf-8").splitlines()
    result = set()
    for row in rows:
        fields = row.split("\t")
        if len(fields) >= 4 and fields[3] in regions and re.fullmatch(r"\d{4}", fields[1]):
            result.add(fields[1])
    if not result:
        raise ValueError(f"GeoNames returned no postcodes for regions: {', '.join(regions)}")
    return sorted(result)
