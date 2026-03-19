# Operations

## Day-to-day local workflow

Use the Makefile instead of ad hoc shell commands.

```bash
make new name=... # scaffold a new artifact directory with placeholder files
make setup      # create .venv, install Python deps, install Chromium locally
make check      # run Ruff, pytest, and artifact validation with the 100% coverage gate
make validate   # fail fast on incomplete or invalid top-level artifact directories
make index      # rebuild js/data.js and README auto markers
make thumbnails # regenerate WebP thumbnails when Playwright is available
make site       # assemble the clean deployable Pages payload in _site/
make generate   # run thumbnails and index together
```

Recommended workflow when changing workspace code:

1. `make new name=my-artifact` if you want a scaffold instead of creating files by hand
2. `make setup`
3. edit files
4. `make check`
5. `make validate` if you changed top-level artifact directories and want an explicit structure check
6. `make index` if metadata or README markers may have changed
7. `make thumbnails` only if you need fresh local thumbnails and Playwright is available
8. `make site` if you want to inspect the exact Pages output locally

## CI behavior

The production workflow uses the same command surface:

- `make setup-ci`
- `make lint`
- `make test`
- `make validate`
- `make thumbnails`
- `make index`
- `make site`

This keeps local and CI behavior aligned and reduces workflow-specific shell logic.

`update.yml` now handles production deploys and pull request previews.

- pushes to `main` and manual runs build, generate, commit generated files when needed, prepare `_site/`, and deploy to `gh-pages`
- pull requests run the same setup, lint, test, generation, and `_site/` assembly path
- trusted pull requests publish preview deployments under `pr-preview/pr-<number>/`
- pull requests leave the source branch untouched while preview comments provide the live preview link
- preview deploys use the GitHub App token
- preview comments use the workflow token, appear as `github-actions[bot]`, and are recreated on each push so the newest preview stays at the bottom of the PR timeline
- fork-based and Dependabot PRs still run checks and site assembly, but skip preview deployment because the app token is unavailable in those contexts

## Coverage and quality gates

- `ruff` runs against `scripts/` and `tests/`
- `pytest` enforces 100% line coverage for the `scripts` package
- `make validate` fails if a top-level artifact directory is missing `index.html` or `name.txt`, has an empty `name.txt`, or uses a non-kebab-case directory name
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

See [`maintenance.md`](maintenance.md) for the long-term upkeep checklist.
