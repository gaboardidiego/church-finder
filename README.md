# Church Finder

Find church services in Vienna by day, language and location.

## Run the website

From `web/`:

```sh
npm install
npm run dev
```

## Generate the database

Run from the repository root. Fetch the church list, then assemble it with the matching
`data/services/churches_vienna/<uuid>/services.json` files:

```sh
uv sync --project scripts --group dev
uv run --project scripts python scripts/fetch_vienna_churches.py --format json
uv run --project scripts python scripts/build_static_database.py \
  data/churches/churches_vienna.json \
  --output data/databases/churches_vienna_filtered.database.json
```

To fetch services from the Archdiocese of Vienna instead, install its browser and run the importer:

```sh
uv sync --project scripts
uv run --project scripts python -m playwright install chromium
uv run --project scripts python scripts/fetch_erzdioezese_services.py \
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
`dist/` for local use; it does not publish to GitHub Pages or make any changes to the live website.
