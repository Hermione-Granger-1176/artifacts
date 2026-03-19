# Operations

## Day-to-day local workflow

Use the Makefile instead of ad hoc shell commands.

```bash
make setup      # create .venv, install Python deps, install Chromium locally
make check      # run Ruff and pytest with the 100% coverage gate
make index      # rebuild js/data.js and README auto markers
make thumbnails # regenerate WebP thumbnails when Playwright is available
make site       # assemble the clean deployable Pages payload in _site/
make generate   # run thumbnails and index together
```

Recommended workflow when changing workspace code:

1. `make setup`
2. edit files
3. `make check`
4. `make index` if metadata or README markers may have changed
5. `make thumbnails` only if you need fresh local thumbnails and Playwright is available
6. `make site` if you want to inspect the exact Pages output locally

## CI behavior

The production workflow uses the same command surface:

- `make setup-ci`
- `make lint`
- `make test`
- `make thumbnails`
- `make index`

This keeps local and CI behavior aligned and reduces workflow-specific shell logic.

`update.yml` now handles production deploys and pull request previews.

- pushes to `main` and manual runs build, generate, commit generated files when needed, prepare `_site/`, and deploy to `gh-pages`
- pull requests run the same setup, lint, test, generation, and `_site/` assembly path
- pull requests publish preview deployments under `pr-preview/pr-<number>/`
- pull requests leave the source branch untouched while preview comments provide the live preview link

## Coverage and quality gates

- `ruff` runs against `scripts/` and `tests/`
- `pytest` enforces 100% line coverage for the `scripts` package
- coverage policy is configured in `pyproject.toml`

## Thumbnail policy

- `thumbnail.webp` is the preferred generated format
- local working copies do not need checked-in thumbnails to function during development
- CI can regenerate thumbnails after push or during pull request preview builds
- the generator still tolerates legacy `thumbnail.png` when present so older generated states do not break the gallery

## Troubleshooting

- if Playwright or Chromium is unavailable locally, `make thumbnails` can fail while `make check` and `make index` still succeed
- if you want to inspect the deployable output locally, run `make site` and serve `_site/` from a static file server
- if README auto markers are removed or duplicated, `scripts/generate_index.py` fails fast instead of silently corrupting the file
- if no artifacts exist, the index generator still writes a valid empty `js/data.js`
- if generated thumbnails are intentionally removed from the working tree, `js/data.js` will emit `thumbnail: null` until CI regenerates them

See `docs/maintenance.md` for the long-term upkeep checklist.
