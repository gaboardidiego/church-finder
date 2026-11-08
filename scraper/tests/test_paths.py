from pathlib import Path

from church_finder_scraper.paths import PROJECT_ROOT


def test_project_root_points_to_repository_not_scraper():
    assert PROJECT_ROOT == Path(__file__).resolve().parents[2]
    assert (PROJECT_ROOT / "scraper" / "pyproject.toml").is_file()
