# Church Finder Scraper

Standalone Python tools for collecting church and service data, then preparing the website
database. The currently supported country is Austria: the OSM search covers Vienna, and the
service importer covers the Archdiocese of Vienna, not all of Austria.

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
`uv run churches-services --help`. Both scraping commands accept `--country austria` and
default to Austria; unsupported countries are rejected. `churches-build-db` assembles local
files and does not scrape or select a country. The service importer requires explicit
`--consent-google-maps` consent. After a successful service import, its database is
published to `web/public/data/churches_vienna.database.json`. The prior website
database is moved to the Git-ignored `backups/` directory, and the importer logs
the church and service counts for both versions. Use `--website-output` to select
a different publication path.

## Code layout and extending the scraper

`austria/osm/` fetches, validates, and serializes Vienna Overpass records.
`static_database.py` combines existing church and service files. The Austria Archdiocese
importer in `austria/archdiocese/` separates site interaction
(`browser.py` and `client.py`), parsing and normalization (`processing.py`), checkpoint
storage (`state.py`), database assembly (`database.py`), and publication (`publish.py`).
`cli.py` validates options; `importer.py` coordinates the import. Keep source-specific
parsing independent of network calls and add offline tests for new formats and failure paths.

The shared `cli.py` dispatches each scraping command using `COUNTRY_MODULES`. To add a
country, implement its commands independently in a new country package and register the
available command modules there. Each module exposes `run(argv, *, parent_parser)` and
uses the provided parent parser in its argument parser so that `--country` appears in help.
Country-specific options, data sources, and processing need not match Austria's.

The importer commits each completed postcode to its SQLite checkpoint. An interrupted run
can be resumed with the same checkpoint and postcode/language options; incompatible options
require a new checkpoint. The generated database is replaced only after a complete write,
and publication backs up the previous database before replacing it. The generated output,
website output, and checkpoint must be different files.
The existing `--state` option selects the checkpoint file; it does not select the country.
Default input, output, checkpoint, and publication paths are relative to the repository root,
regardless of the current working directory.
