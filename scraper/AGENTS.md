# Scraper Project Guide

- `src/church_finder_scraper/cli.py` dispatches scraping commands by `--country`.
- `src/church_finder_scraper/austria/osm/` handles OpenStreetMap requests and record
  normalization for website enrichment.
- `austria/` imports service listings for Austrian postcodes, including Vienna,
  enriches websites using Austrian OSM data, and contains the importer CLI, checkpoint storage
  and publication logic.
- Keep parsing and transformation logic independently testable. Put tests in `tests/`.
- Use Astral's Ruff for linting and formatting and ty for type checking.
- Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and
  `uv run ty check src` before completing scraper changes.
