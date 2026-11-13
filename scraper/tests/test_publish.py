import json
from pathlib import Path
from unittest.mock import patch

import pytest

from church_finder_scraper.austria.publish import publish_database


def test_publish_database_moves_previous_version_to_backup(tmp_path: Path):
    destination = tmp_path / "web" / "churches.json"
    backup_dir = tmp_path / "backups"
    previous = {"churches": [{"uuid": "old"}], "services": {"old": [{"date": "2026-01-01"}]}}
    current = {
        "churches": [{"uuid": "new-1"}, {"uuid": "new-2"}],
        "services": {"new-1": [{"date": "2026-01-02"}, {"date": "2026-01-03"}]},
    }
    destination.parent.mkdir(parents=True)
    destination.write_text(json.dumps(previous), encoding="utf-8")
    old_counts, new_counts, backup_path = publish_database(current, destination, backup_dir)

    assert old_counts == (1, 1)
    assert new_counts == (2, 2)
    assert backup_path is not None
    assert json.loads(backup_path.read_text(encoding="utf-8")) == previous
    assert json.loads(destination.read_text(encoding="utf-8")) == current


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

    with pytest.raises(TypeError):
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

    with (
        patch.object(Path, "replace", side_effect=OSError("disk")),
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
