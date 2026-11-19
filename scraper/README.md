# Church Finder Scraper

Python tools for collecting church and service data, then preparing the website database.
Austria service imports use Gottesdienst.at for all federal states.

```sh
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check src
```

Install Playwright's browser once before importing Austrian service schedules:

```sh
uv run playwright install chromium
```

Run `uv run churches-services --help`. The command accepts `--country austria` or
`--country italy` and defaults to Austria; unsupported countries are rejected. By default, it searches Austrian
postcodes with Gottesdienst.at. `--vienna-only` restricts the search to Vienna postcodes, while
repeatable `--postcode` options select individual postcodes.

The service importer requires explicit `--consent-google-maps` consent; it enables only that
consent category. `--state` selects the Gottesdienst.at checkpoint (`--nationwide-state` is an
alias). Languages are inferred from service labels when present and otherwise recorded as
`Unknown`. Church identifiers differ from the former Vienna importer.
After collecting services, the importer fetches Christian places of worship and church buildings
across Austria from OpenStreetMap and matches websites by location within 50 metres.
It uses `website` or `contact:website`, skips ambiguous or invalid matches, and logs coverage.
Some churches have no OSM website, no usable coordinates, or no unambiguous nearby match;
proximity does not guarantee that the website belongs to the correct church. The OSM fetch runs
again even for a completed checkpoint; if it fails, publication stops and the checkpoint can
be reused to retry without searching the postcodes again.
The Austria-wide pass is rate-limited per postcode and may take tens of minutes; its checkpoint
allows an interrupted run to resume. Each postcode search logs its progress through the selected
postcodes, including those already completed in the checkpoint. A postcode returning 200 services
emits a warning because the site may have truncated that search result. Vienna searches have reached this limit,
so results may cover fewer services, locations and dates than the former Vienna source.
Searches may also return locations outside the selected postcode or Vienna.
Gottesdienst.at services with both date
fields empty are skipped with a warning because they cannot be scheduled; partially specified or
invalid dates stop the import.
If postcode results for the same Gottesdienst.at church omit coordinates in some responses,
the importer uses coordinates from another response for that church. Conflicting known coordinates
or church names still stop the import.

The church index is published to `web/public/data/churches_vienna.database.json`, whose legacy
filename is kept for URL compatibility. It includes a compact date/language index for filtering,
grouping dates by language; the website also supports older indexes with individual entries.
Full schedules are published alongside it as content-addressed `services-<state>-<hash>.json`
files, one per Austrian federal state. The frontend fetches these files as needed.
State assignments use simplified 2021 boundaries: CC BY 4.0 Flooh Perlot,
[GeoJSON/TopoJSON Austria](https://github.com/ginseng666/GeoJSON-TopoJSON-Austria),
derived from CC BY 4.0 Statistik Austria (data.statistik.gv.at). Approximate boundaries may
misclassify locations near state borders. Locations outside the boundaries use the nearest state.
When coordinates are unavailable, the address postcode, or otherwise the search postcode, is
used to approximate the state from postal ranges. Postal areas can cross state boundaries;
if neither coordinates nor a usable postcode are available, publication stops rather than
assigning an arbitrary state.

The prior index is copied to the Git-ignored `backups/` directory, and the importer logs the
church and service counts for both versions. Regional files are immutable and retained so
previous indexes and active clients continue to work; restoring an index requires its referenced
files in the output directory. Use `--output` (or its alias `--website-output`) to select a
different index path; regional files are placed alongside it.

## Code layout and extending the scraper

`austria/osm/` fetches and validates Overpass records for website enrichment.
`austria/` separates service site interaction (`browser.py` and `client.py`), parsing
and normalization (`processing.py`), checkpoint storage (`state.py`), database assembly
(`database.py`), spatial website matching (`websites.py`), and publication (`publish.py`).
`importer.py` coordinates checkpointed collection and enrichment; it does not publish the
result. Keep source-specific parsing independent of network calls and add offline tests for
new formats and failure paths.

The shared `cli.py` dispatches each scraping command using `COUNTRY_MODULES`. To add a
country, implement its commands independently in a new country package and register the
available command modules there. Each module exposes `run(argv, *, parent_parser)` and
uses the provided parent parser in its argument parser so that `--country` appears in help.
Country-specific options, data sources, and processing need not match Austria's.

Each completed postcode is committed to a SQLite checkpoint, including searches with no results.
Later runs skip saved postcodes and retry only those without a saved batch; there is no age-based
refresh. An interrupted run can be resumed with the same checkpoint and postcode selection;
incompatible selections require a new checkpoint or `--fresh`. To rerun a completed postcode,
use `--fresh` or a new checkpoint with the same selected postcodes. The default checkpoint is
`.scraper-state/gottesdienst_at_austria.checkpoint.sqlite`, distinct from both previous source
checkpoints. Existing Gottesdienst.at checkpoints can only be reused when their selected
postcodes match; former Vienna-source checkpoints cannot be reused.
To retain a checkpoint from the previous default location, stop the importer and move
`data/databases/gottesdienst_at_austria.checkpoint.sqlite` to the new default path.
If the old default checkpoint exists and the new one does not, the importer reports this
instead of silently starting a new checkpoint.
The website database is replaced only after the search completes, and publication backs up the
previous database before replacing it. The output and checkpoint must be different files.
Default output, checkpoint, and backup paths are relative to the repository root,
regardless of the current working directory.

To scrape all Austrian postcodes again from zero and replace the website database, run:

```sh
uv run churches-services --consent-google-maps --fresh
```

`--fresh` discards all saved results in the selected checkpoint, including results from a
different postcode selection. It does not merge in the old database. The existing website
database remains unchanged until the search succeeds; publication backs up the old
website database. If the run is interrupted, repeat the same command **without** `--fresh` to
resume; using `--fresh` again discards the new progress. Do not run multiple importers against
the same checkpoint at the same time.

## Italy

```sh
uv run churches-services --country italy
```

The [Ember Mass-times API](https://ember.dpgu.me/developers/api/) provides an open, paginated
directory, including its Italian churches and structured recurring Mass schedules. The importer
requests full church pages filtered by `country=IT`, with no authentication, and caches them in
`.scraper-state/ember_italy.checkpoint.sqlite` for up to one day. It requests at most one page per
second, resumes interrupted downloads, and only publishes after the complete paginated import
succeeds. `--fresh` discards the Ember checkpoint; omit it when resuming. `--interval` can increase
the delay but cannot lower it below one second. The previous `--source ember` option remains
accepted. Do not run multiple importers against the same checkpoint at the same time.

The Italy index is published independently to `web/public/data/churches_italy.database.json`,
using the same compact index grouped by language as Austria and content-addressed service files
beside it. Each import replaces the Italy index and backs up its previous version; Austria's output
is not overwritten. The website loads both indexes and displays an explicit warning if either fails.
Use `--output` and `--state` to select different
paths. A custom index and its service files must be placed in the website data directory to be
used by the website. Existing historical indexes retain their original source credit when restored.

Ember provides recurring rules, not confirmed individual events. The importer expands Mass rules,
including exceptions and additions, for 30 calendar days starting with the current local day at
each church; it does not generate confession or adoration entries. Regularly rerun the importer
to advance this window. A completed checkpoint can be reused for a day; use `--fresh` for an
immediate refresh. Languages reported as ISO codes are normalized where recognized. Churches
without structured schedules remain listed without service times; free-text schedules are not
interpreted. Closed and temporarily closed churches are excluded.

Ember's times may be old or incomplete: a sample of 10,178 Italian churches contained many last
verified in 2020 or 2021. The website displays the last verification date, or that it is unknown,
alongside each Ember church. Dates generated from a recurrence are not proof that a particular
celebration will take place; confirm with the parish. Ember asks clients to
[credit the service](https://ember.dpgu.me/developers/), and the website links to Ember when
its data is selected. The importer does not automatically refresh or schedule itself.
