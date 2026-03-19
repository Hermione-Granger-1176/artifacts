# Workspace Structure

## What this repo is

This repository hosts a GitHub Pages gallery of interactive HTML artifacts.

- the root site is the gallery
- each artifact lives in its own folder under `apps/`
- the repo includes Python tooling to generate gallery data and thumbnails
- GitHub Actions deploys the site, publishes PR previews, and commits generated outputs back on non-PR runs when needed

## Top-level layout

```text
.
|- .github/actions/       Shared composite actions for workflows
|- .github/workflows/     CI/CD automation
|- apps/                  Artifact folders and CI-generated thumbnails
|- css/                   Root gallery styles
|- docs/                  Workspace documentation
|- js/                    Root gallery logic and generated data
|- scripts/               Python generation and deploy-prep tools
|- tests/                 Python test suite for the tooling layer
|- 404.html               GitHub Pages error page
|- index.html             Root gallery entry point
|- Makefile               Stable local command interface
|- pyproject.toml         Python dependencies, tool config, and site metadata
```

## Source of truth by area

- `apps/*/index.html`: artifact implementation
- `apps/*/name.txt`, `description.txt`, `tags.txt`, `tools.txt`: artifact metadata
- `index.html`, `css/style.css`, `js/app.js`: root gallery UI
- `pyproject.toml`: Python dependency pins and workspace configuration
- `scripts/prepare_site.py`: deploy-time site assembly, cache busting, and site path injection
- `.github/actions/verified-commit/action.yml`: shared verified commit and PR fallback logic for CI
- `.github/workflows/update.yml`: main automation workflow for pushes, PR previews, and manual runs

## Generated and derived files

These files are outputs. Prefer changing the generator instead of editing them directly.

- `js/data.js`
- README auto-marked values such as site URL, total count, and badges
- `apps/*/thumbnail.webp`
- `_site/` when `make site` or CI prepares the deployable Pages payload

The website is the canonical artifact catalog. `README.md` intentionally keeps only a high-level snapshot instead of listing every artifact.

## Artifact folder contract

Each artifact directory under `apps/` is expected to contain:

- `index.html`: required entry point
- `name.txt`: required display name
- `description.txt`: optional short description
- `tags.txt`: optional tags, one per line
- `tools.txt`: optional AI tools, one per line
- `thumbnail.webp`: preferred generated thumbnail when present

The generator still recognizes `thumbnail.png` as a temporary compatibility fallback so older branches or previously generated states do not break the root gallery.

## Editing rules

- add or modify artifacts in `apps/`
- use `make new name=my-artifact` when you want a correct starting structure quickly
- update generator logic in `scripts/` when derived output behavior should change
- use `make validate` to catch incomplete top-level artifact directories before pushing
- use `make index` to refresh `js/data.js` and README markers
- use `make thumbnails` or CI to regenerate thumbnails
- use `make site` to inspect the exact deployable Pages directory locally
- keep workspace-level configuration in `pyproject.toml` rather than scattering URLs or constants across scripts
