import json
from pathlib import Path

import pytest

from church_finder_scraper.static_database import build_database


def test_build_database_combines_records_and_services(tmp_path: Path):
    churches = tmp_path / "churches.json"
    services_dir = tmp_path / "services"
    church_id = "church-1"
    churches.write_text(json.dumps([{"uuid": church_id, "name": "Church"}]), encoding="utf-8")
    church_services = services_dir / church_id / "services.json"
    church_services.parent.mkdir(parents=True)
    church_services.write_text(json.dumps([{"date": "2026-11-08"}]), encoding="utf-8")

    assert build_database(churches, services_dir) == {
        "churches": [{"uuid": church_id, "name": "Church"}],
        "services": {church_id: [{"date": "2026-11-08"}]},
    }


def test_build_database_rejects_missing_service_files(tmp_path: Path):
    churches = tmp_path / "churches.json"
    churches.write_text(json.dumps([{"uuid": "church-1"}]), encoding="utf-8")
    services_dir = tmp_path / "services"
    services_dir.mkdir()

    with pytest.raises(SystemExit, match="No services.json"):
        build_database(churches, services_dir)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("not json", "Invalid JSON"),
        ("{}", "JSON array of churches"),
        ("[null]", "not a JSON object"),
        ("[{}]", "no non-empty uuid"),
        ('[{"uuid":"one"},{"uuid":"one"}]', "Duplicate church uuid"),
    ],
)
def test_build_database_rejects_invalid_churches(tmp_path: Path, content: str, message: str):
    churches = tmp_path / "churches.json"
    churches.write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit, match=message):
        build_database(churches, tmp_path)


def test_build_database_rejects_duplicate_service_files(tmp_path: Path):
    churches = tmp_path / "churches.json"
    churches.write_text('[{"uuid":"one"}]', encoding="utf-8")
    for location in ("first", "second"):
        service_file = tmp_path / location / "one" / "services.json"
        service_file.parent.mkdir(parents=True)
        service_file.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit, match="Multiple services.json"):
        build_database(churches, tmp_path)
