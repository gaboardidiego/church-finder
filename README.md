# Church Finder

Find church services in Vienna by day, language and location.

## Python scraper

The standalone Python tools are in [`scraper/`](scraper/). From that directory, run
`uv sync --group dev` and `uv run pytest`; see its README for CLI commands and quality checks.

## Run the website

From `web/`:

```sh
npm install
npm run dev
```

## Analytics

[View analytics](https://church-finder.goatcounter.com/).

## Generate the database

Run from the repository root. Fetch the church list, then assemble it with the matching
`data/services/churches_vienna/<uuid>/services.json` files:

```sh
uv sync --project scraper --group dev
uv run --project scraper churches-osm --format json \
  --output data/churches/churches_vienna.json
uv run --project scraper churches-build-db \
  data/churches/churches_vienna.json \
  --output data/databases/churches_vienna_filtered.database.json
```

To fetch services from the Archdiocese of Vienna instead, install its browser and run the importer:

```sh
uv sync --project scraper
uv run --project scraper playwright install chromium
uv run --project scraper churches-services \
  --consent-google-maps \
  --output data/databases/churches_vienna_filtered.database.json
```

Copy the database to the website with `npm run sync-data` from `web/`. It copies
`data/databases/churches_vienna_filtered.database.json` to `web/public/data/`.

## Check and deploy

Run from `web/`:

```sh
npm run check
npm run build
npm run deploy
```

`npm run check` runs formatting, lint, typecheck and tests. `npm run deploy` builds the site into
the repository's `docs/` directory. The `Deploy website` GitHub Actions workflow runs these checks
and updates the generated files on `main` whenever website source changes are pushed. Configure
GitHub Pages to use the `main` branch and `/docs` as its source.

Website code lives in `web/src/`. `main.ts` coordinates application state and events; `filters.ts`,
`data.ts` and `geo.ts` contain data and filtering logic; and `ui/` contains the list, map,
localization and filter-option rendering. Add tests alongside the module being changed. The
application-flow tests use the actual page markup with map and analytics dependencies mocked.

To format, lint, test, type-check and build both projects in one command, install the repository
script on your `PATH`:

```sh
mkdir -p ~/.local/bin
ln -s "$(pwd)/scripts/check-church-finder" ~/.local/bin/check-church-finder
check-church-finder
```

Run it from any directory. It formats files automatically before checking them and prints all
progress and results to the terminal; it does not create log files.

To build the website and start a local preview with the default browser, install the companion
script on your `PATH`:

```sh
ln -s "$(pwd)/scripts/start-church-finder" ~/.local/bin/start-church-finder
start-church-finder
```

It prints the site URL (`http://127.0.0.1:4173/`) and keeps the preview server running until you
press Ctrl-C. Progress and server output appear in the terminal only; no log files are created.
