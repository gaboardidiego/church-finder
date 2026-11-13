# Church Finder

Find church services across Austria by day, language and location.

## Python scraper

The standalone Python tools are in [`scraper/`](scraper/). From that directory, run
`uv sync --group dev` and `uv run pytest`; see its README for CLI commands and quality checks.
The service importer uses Gottesdienst.at throughout Austria and looks up church websites in
OpenStreetMap across Austria.

## Run the website

From `web/`:

```sh
npm install
npm run dev
```

On opening the site, the browser asks for location permission and may use GPS, Wi-Fi or network
signals to estimate a location. The map frames the selected location and up to four nearest matching
churches, even if they are far away. If no churches match the active filters, only the location is
shown. Selecting a church frames its nearest matching churches without changing the distance origin.
If location is unavailable it may retry with a cached location up to 24 hours old. If location remains
unavailable or permission is denied, use the map to drop a pin instead. No separate IP-location
service is used.

## Analytics

[View analytics](https://church-finder.goatcounter.com/).

## Generate the database

```sh
uv sync --project scraper --group dev
uv run --project scraper playwright install chromium
uv run --project scraper churches-services --consent-google-maps
```

The command collects services across Austria from Gottesdienst.at, then publishes the database
to `web/public/data/`. Its checkpoint in `.scraper-state/` can resume interrupted imports; see
[`scraper/README.md`](scraper/README.md) for options and source limitations.

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
