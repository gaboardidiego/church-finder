# AGENTS.md

Project guide for Church Finder.

## Project layout

- `web/` is the static, frontend-only Vienna site, built with Vite, TypeScript and Leaflet.
- `scripts/` contains Python tools for fetching church and service data and preparing JSON databases.
- `data/` holds local generated/input data and is ignored by Git; it is not loaded by the website.
- The site uses OpenStreetMap tiles and GoatCounter analytics. It has no backend.

## Website commands

Run from `web/`:

| Command | Purpose |
| --- | --- |
| `npm install` | Install dependencies and set up the Husky hook |
| `npm run dev` | Start the Vite development server |
| `npm run check` | Run formatting check, ESLint, TypeScript and Vitest |
| `npm run build` | Typecheck and create the production build in `../docs/` |
| `npm run sync-data` | Copy the generated filtered database into `public/data/` |
| `npm run deploy` | Build the site into the repository's `docs/` directory |

Always run `npm run check` before finishing a website change. CI also runs `npm run build`. To
publish, commit the generated `docs/` files to `main` and push; configure GitHub Pages to use the
`main` branch and `/docs` as its source.

## Python data tools

The standalone Python project is in `scraper/`. Use its Astral tooling and tests when changing
that project:

```sh
uv sync --project scraper --group dev
uv run --project scraper pytest scraper/tests
uv run --project scraper ruff check scraper/
uv run --project scraper ruff format --check scraper/
uv run --project scraper ty check scraper/src
```

Its source is organized under `scraper/src/church_finder_scraper/`; see `scraper/AGENTS.md` and
`scraper/README.md` for importer consent, postcode coverage, checkpoints, request pacing, and
data limitations.

## Website data

- The website loads `web/public/data/churches_vienna.database.json`; do not load files from `data/`
  at runtime.
- `npm run sync-data` copies `data/databases/churches_vienna_filtered.database.json` to the
  website. That source is local and ignored by Git.
- `scraper/src/church_finder_scraper/static_database.py` assembles a database from a church list
  and per-church `services.json` files. The Archdiocese importer writes the website's compact
  schema directly.
- Schema: `{ churches: [{ uuid, name, website, position: { latitude, longitude }, religion, denomination }], services: { [uuid]: [{ language, start_time, date }] } }`.
- Services may be empty. `web/src/data.ts` skips unusable entries and supplies "Unnamed church"
  when a name is missing.

## Website architecture

- `web/src/types.ts`: shared TypeScript types.
- `web/src/data.ts`: data parsing and loading.
- `web/src/geo.ts`: distance calculations and formatting.
- `web/src/filters.ts`: filtering, sorting and date helpers.
- `web/src/analytics.ts`: GoatCounter initialization and events.
- `web/src/ui/map.ts` and `web/src/ui/list.ts`: map and result cards.
- `web/src/main.ts`: application state, DOM events and rendering.

Keep logic in pure functions where practical and add tests in adjacent `*.test.ts` files.

## Conventions and privacy

- Use strict TypeScript and the existing Prettier style; do not add a framework.
- Build DOM with `textContent` and `createElement`; never place data values in `innerHTML`.
- GoatCounter analytics are always enabled for `church-finder.goatcounter.com`. Never send the
  user's coordinates or search text to analytics.
- Existing events include `search_name`, `use_location`, `pin_location`, `filter_day_*`,
  `filter_date`, `filter_language`, `filter_denomination`, `open_website` and `open_google_maps`.

## City scope

The website and OSM fetcher currently target Vienna. The website data URL is in
`web/src/main.ts`, and the default map center is in `web/src/ui/map.ts`; both are currently
Vienna-specific.
