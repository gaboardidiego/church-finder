import json
from pathlib import Path

from church_finder_scraper.archdiocese.publish import publish_database


def test_publish_database_moves_previous_version_to_backup(tmp_path: Path):
    source = tmp_path / "generated.json"
    destination = tmp_path / "web" / "churches.json"
    backup_dir = tmp_path / "backups"
    previous = {"churches": [{"uuid": "old"}], "services": {"old": [{"date": "2026-01-01"}]}}
    current = {
        "churches": [{"uuid": "new-1"}, {"uuid": "new-2"}],
        "services": {"new-1": [{"date": "2026-01-02"}, {"date": "2026-01-03"}]},
    }
    destination.parent.mkdir(parents=True)
    destination.write_text(json.dumps(previous), encoding="utf-8")
    source.write_text(json.dumps(current), encoding="utf-8")

    old_counts, new_counts, backup_path = publish_database(source, destination, backup_dir)

    assert old_counts == (1, 1)
    assert new_counts == (2, 2)
    assert backup_path is not None
    assert json.loads(backup_path.read_text(encoding="utf-8")) == previous
    assert json.loads(destination.read_text(encoding="utf-8")) == current


def test_publish_database_without_previous_version(tmp_path: Path):
    source = tmp_path / "generated.json"
    destination = tmp_path / "web" / "churches.json"
    source.write_text(json.dumps({"churches": [], "services": {}}), encoding="utf-8")

    old_counts, new_counts, backup_path = publish_database(
        source, destination, tmp_path / "backups"
    )

    assert old_counts is None
    assert new_counts == (0, 0)
    assert backup_path is None
    assert destination.exists()
