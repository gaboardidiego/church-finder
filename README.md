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
the repository's `docs/` directory. Commit the generated files to `main` and push to publish them
with GitHub Pages. Configure GitHub Pages to use the `main` branch and `/docs` as its source.
