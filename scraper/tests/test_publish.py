import json
from pathlib import Path
from unittest.mock import patch

import pytest

from church_finder_scraper.austria.publish import publish_database
from church_finder_scraper.austria.regions import region_for_position


def test_publish_database_moves_previous_version_to_backup(tmp_path: Path):
    destination = tmp_path / "web" / "churches.json"
    backup_dir = tmp_path / "backups"
    previous = {"churches": [{"uuid": "old"}], "services": {"old": [{"date": "2026-01-01"}]}}
    current = {
        "churches": [
            {"uuid": "new-1", "region": "wien"},
            {"uuid": "new-2", "region": "wien"},
        ],
        "services": {"new-1": [{"date": "2026-01-02"}, {"date": "2026-01-03"}]},
    }
    destination.parent.mkdir(parents=True)
    destination.write_text(json.dumps(previous), encoding="utf-8")
    old_counts, new_counts, backup_path = publish_database(current, destination, backup_dir)

    assert old_counts == (1, 1)
    assert new_counts == (2, 2)
    assert backup_path is not None
    assert json.loads(backup_path.read_text(encoding="utf-8")) == previous
    index = json.loads(destination.read_text(encoding="utf-8"))
    assert index["services"] == {}
    assert index["churches"][0]["service_index"] == [
        {"date": "2026-01-02", "language": ""},
        {"date": "2026-01-03", "language": ""},
    ]
    regional = json.loads(
        (destination.parent / index["service_files"]["wien"]).read_text(encoding="utf-8")
    )
    assert regional["services"]["new-1"] == current["services"]["new-1"]


def test_publish_database_without_previous_version(tmp_path: Path):
    destination = tmp_path / "web" / "churches.json"

    old_counts, new_counts, backup_path = publish_database(
        {"churches": [], "services": {}}, destination, tmp_path / "backups"
    )

    assert old_counts is None
    assert new_counts == (0, 0)
    assert backup_path is None
    assert destination.exists()


def test_publish_preserves_previous_database_after_backup_failure(tmp_path: Path):
    destination = tmp_path / "published.json"
    destination.write_text('{"churches":[{}],"services":{}}', encoding="utf-8")
    previous = destination.read_bytes()

    with (
        patch(
            "church_finder_scraper.austria.publish.shutil.copy2",
            side_effect=OSError("disk"),
        ),
        pytest.raises(OSError, match="disk"),
    ):
        publish_database({"churches": [], "services": {}}, destination, tmp_path / "backups")
    assert destination.read_bytes() == previous
    assert not list(tmp_path.glob("published.json.*"))


def test_publish_preserves_previous_database_on_serialization_failure(tmp_path: Path):
    destination = tmp_path / "published.json"
    destination.write_text('{"churches":[{}],"services":{}}', encoding="utf-8")
    previous = destination.read_bytes()

    with pytest.raises(ValueError, match="churches must be objects"):
        publish_database(
            {"churches": [object()], "services": {}}, destination, tmp_path / "backups"
        )
    assert destination.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [destination]


def test_publish_preserves_previous_database_on_replace_failure(tmp_path: Path):
    destination = tmp_path / "published.json"
    destination.write_text('{"churches":[{}],"services":{}}', encoding="utf-8")
    previous = destination.read_bytes()
    backup_dir = tmp_path / "backups"

    def replace(src: Path, dst: Path):
        if dst == destination:
            raise OSError("disk")
        return src.rename(dst)

    with (
        patch.object(Path, "replace", autospec=True, side_effect=replace),
        pytest.raises(OSError, match="disk"),
    ):
        publish_database({"churches": [], "services": {}}, destination, backup_dir)
    assert destination.read_bytes() == previous
    assert [path.read_bytes() for path in backup_dir.iterdir()] == [previous]
    assert not list(tmp_path.glob("published.json.*"))


def test_publish_rejects_invalid_database_before_backup(tmp_path: Path):
    destination = tmp_path / "published.json"
    destination.write_text('{"churches":[{}],"services":{}}', encoding="utf-8")
    previous = destination.read_bytes()

    with pytest.raises(ValueError, match="churches and services"):
        publish_database({"churches": []}, destination, tmp_path / "backups")
    assert destination.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.parametrize(
    ("latitude", "longitude", "expected"),
    [
        (48.2082, 16.3738, "wien"),
        (47.8457, 16.5233, "burgenland"),
        (46.6247, 14.3053, "kaernten"),
        (48.2035, 15.6279, "niederoesterreich"),
        (48.3069, 14.2858, "oberoesterreich"),
        (47.8095, 13.0550, "salzburg"),
        (47.0707, 15.4395, "steiermark"),
        (47.2692, 11.4041, "tirol"),
        (47.5031, 9.7471, "vorarlberg"),
        (47.7222695, 12.9146354, "salzburg"),
        (48.4584763, 13.4309002, "oberoesterreich"),
        (47.46588525, 9.59841591, "vorarlberg"),
        (47.415745, 11.211982, "tirol"),
    ],
)
def test_assigns_regions(latitude: float, longitude: float, expected: str):
    assert region_for_position({"latitude": latitude, "longitude": longitude}) == expected


def test_region_files_and_summaries_keep_all_services_and_survive_republication(tmp_path: Path):
    destination = tmp_path / "index.json"
    database = {
        "churches": [
            {"uuid": "vienna", "position": {"latitude": 48.2082, "longitude": 16.3738}},
            {"uuid": "graz", "position": {"latitude": 47.0707, "longitude": 15.4395}},
        ],
        "services": {
            "vienna": [
                {"date": "2026-01-01", "language": "German", "start_time": "09:00"},
                {"date": "2026-01-01", "language": "German", "start_time": "10:00"},
            ],
            "graz": [{"date": "2026-01-02", "language": "English", "start_time": "11:00"}],
        },
    }
    assert publish_database(database, destination, tmp_path / "backups")[1] == (2, 3)
    index = json.loads(destination.read_text(encoding="utf-8"))
    assert len(index["service_files"]) == 9
    assert index["churches"][0]["region"] == "wien"
    assert index["churches"][0]["service_index"] == [{"date": "2026-01-01", "language": "German"}]
    vienna_file = destination.parent / index["service_files"]["wien"]
    assert json.loads(vienna_file.read_text(encoding="utf-8"))["services"] == {
        "vienna": database["services"]["vienna"]
    }
    database["services"]["vienna"].append(
        {"date": "2026-01-03", "language": "English", "start_time": "12:00"}
    )
    old_counts, new_counts, backup = publish_database(database, destination, tmp_path / "backups")
    assert old_counts == (2, 3)
    assert new_counts == (2, 4)
    assert backup is not None
    assert json.loads(backup.read_text(encoding="utf-8")) == index
    assert vienna_file.exists()
    assert json.loads(destination.read_text(encoding="utf-8"))["service_files"]["wien"] != (
        vienna_file.name
    )


def test_missing_position_without_postcode_region_stops_publication(tmp_path: Path):
    with pytest.raises(ValueError, match="Cannot determine a valid region"):
        publish_database(
            {"churches": [{"uuid": "unknown"}], "services": {}},
            tmp_path / "index.json",
            tmp_path / "backups",
        )
