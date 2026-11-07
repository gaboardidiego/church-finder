# Scraper Project Guide

- `src/church_finder_scraper/osm/` handles OpenStreetMap requests, record normalization,
  serialization, and its command-line interface.
- `static_database.py` validates and assembles church/service data; `static_database_cli.py`
  handles command-line paths and writing.
- `archdiocese/` separates site interaction, parsing/normalization, checkpoint state, database
  assembly, and the importer CLI.
- Keep parsing and transformation logic independently testable. Put tests in `tests/`.
- Use Astral's Ruff for linting and formatting and ty for type checking.
- Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and
  `uv run ty check src` before completing scraper changes.
