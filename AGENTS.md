# AGENTS.md

Guide for humans and AI agents working on Church Finder.

## Overview

- `data/` and `scripts/`: Python data collection (churches, services). Not part of the website.
- `web/`: the static, frontend-only website (Vite + vanilla TypeScript + Leaflet/OpenStreetMap).
- Only free services are allowed: OSM tiles, Nominatim, GoatCounter, GitHub Pages. No backend.

## Commands (run inside `web/`)

| Command                | Purpose                                              |
| ---------------------- | ---------------------------------------------------- |
| `npm install`          | Install deps and set up the husky pre-commit hook    |
| `npm run dev`          | Dev server                                           |
| `npm run build`        | Typecheck + production build to `web/dist`           |
| `npm run format`       | Prettier write (`format:check` to verify)            |
| `npm run lint`         | ESLint                                               |
| `npm run typecheck`    | `tsc --noEmit`                                       |
| `npm test`             | Vitest unit tests                                    |
| `npm run check`        | Format check + lint + typecheck + tests (used in CI) |
| `npm run sync-data`    | Refresh the website's database copy (see below)      |
| `npm run deploy`       | Build locally and publish `web/dist` to `gh-pages`   |

Always run `npm run check` before finishing a change.

## Data

- The site uses its **own copy**: `web/public/data/churches_vienna.database.json`.
  Never reference `data/databases/` from the website.
- To update it, rebuild the database with `scripts/build_static_database.py`, then run `npm run sync-data`.
- Schema: `{ churches: [{ uuid, name, website, position: {latitude, longitude}, religion, denomination }], services: { [uuid]: [{ language, start_time: "HH:MM", date: "YYYY-MM-DD" }] } }`.
- Services may be empty. `src/data.ts` is defensive: invalid entries are skipped, missing names become "Unnamed church".

## Architecture (`web/src`)

- `types.ts`: shared types.
- `data.ts`: parsing/loading the database (pure, tested).
- `geo.ts`: haversine distance and formatting.
- `filters.ts`: name/date/language filtering, sorting by distance, date helpers.

- `analytics.ts`: GoatCounter wrapper; `trackEvent(name)` is a no-op without a site code.
- `ui/map.ts`: Leaflet map (markers, draggable origin pin, click-to-pin). `ui/list.ts`: result cards.
- `main.ts`: wires state, DOM events and rendering. Keep logic in pure modules and cover it with `*.test.ts`.

## Conventions

- TypeScript strict; prettier style (single quotes, 100 cols). No frameworks.
- Build DOM with `textContent`/`createElement`, never `innerHTML` with data values.
- Put new logic in pure functions with unit tests next to them.

## Analytics and privacy

- GoatCounter is cookie-less, so no consent banner. Set the public site code via `VITE_GOATCOUNTER_CODE` in `web/.env`; this is an identifier, not a secret.
- Existing events: `search_name`, `use_location`, `pin_location`, `filter_day_*`, `filter_date`, `filter_language`, `filter_denomination`, `open_website`.
- Never send the user's coordinates or search text to analytics.

## Deployment

Build and publish locally with `cd web && npm run deploy`. This pushes the contents of `web/dist` to the `gh-pages` branch; configure GitHub Pages to deploy from that branch's root. `.github/workflows/ci.yml` continues to run checks on PRs and pushes to `main`.

## Adding another city

Add its database copy under `web/public/data/`, make the data URL and the Nominatim `VIENNA_VIEWBOX` / map default center configurable, and update this file.
