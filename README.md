# Church Finder

Find church services in Vienna by day, language and location. See [AGENTS.md](AGENTS.md) for development.

```sh
cd web && npm install && npm run dev
```

To publish to GitHub Pages from your local machine, create `web/.env` with your GoatCounter site code if analytics is enabled, then run:

```sh
cd web && npm run deploy
```

This builds the app locally and pushes the generated site to the `gh-pages` branch. In the repository's **Settings → Pages**, set the source to **Deploy from a branch**, then select `gh-pages` and `/(root)`. The GoatCounter site code is public, not a secret; `web/.env` is ignored by Git.
