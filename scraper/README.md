# Church Finder Scraper

Standalone Python tools for collecting Vienna church and service data, then preparing the
website database.

```sh
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check src
```

Install Playwright's browser once before importing Archdiocese schedules:

```sh
uv run playwright install chromium
```

Run `uv run churches-osm --help`, `uv run churches-build-db --help`, or
`uv run churches-services --help`. The service importer requires explicit
`--consent-google-maps` consent. After a successful service import, its database is
published to `web/public/data/churches_vienna.database.json`. The prior website
database is moved to the Git-ignored `backups/` directory, and the importer logs
the church and service counts for both versions. Use `--website-output` to select
a different publication path.
