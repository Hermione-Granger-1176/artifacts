# Workspace Structure

## What this repo is

This repository hosts a GitHub Pages gallery of interactive HTML artifacts.

- The root site is the gallery.
- Each artifact lives in its own folder under `apps/`.
- The repo includes Python tooling to generate gallery data and thumbnails.
- GitHub Actions deploys the site and publishes PR previews from the verified `_site/` artifact without mutating contributor branches during the main publish flow.

## Top-level layout

```text
.
|- .editorconfig          Editor settings for all file types
|- .github/actions/       Shared composite actions for workflows
|- .github/workflows/     CI/CD automation
|- assets/icons/          Logo, favicon, and web app manifest
|- assets/social/         Social share preview image for metadata cards
|- config/                Shared gallery metadata used by generators
|- apps/                  Artifact folders and generated thumbnails
|- css/                   Root gallery styles
|- docs/                  Workspace documentation
|- js/                    Root gallery logic and generated data
|- package.json           Node-based lint and unit test tooling
|- locks/                 Frozen Python dependency lock files
|- scripts/               Python generation and deploy-prep tools
|- tests/js/              Node unit tests for browser and workflow modules
|- tests/                 Python test suite for the tooling layer
|- 404.html               GitHub Pages error page
|- index.html             Root gallery entry point
|- Makefile               Stable local command interface
|- pyproject.toml         Python dependencies, tool config, and site metadata
```

## Source of truth by area

- `apps/*/index.html`: artifact implementation
- `apps/*/name.txt`, `description.txt`, `tags.txt`, `tools.txt`: artifact metadata
- `index.html`, `css/style.css`, `css/root-gallery-*.css`, `js/app.js`, `js/modules/*`: root gallery UI
- `assets/icons/*`: logo, favicon, apple touch icon, PWA manifest, and raster icons
- `assets/social/share-preview.png`: social preview image referenced by deploy-time Open Graph and Twitter metadata
- `config/gallery_metadata.json`: shared tool and tag display metadata used by generators to produce `js/gallery-config.js`
- `docs/adr/*`: accepted cross-cutting decisions about the root publishing platform
- `pyproject.toml`: Python dependency pins and workspace configuration
- `locks/requirements.lock`, `locks/requirements-dev.lock`: frozen Python dependency graphs
- `package.json`, `package-lock.json`: frozen Node tooling graph
- `scripts/prepare_site.py`: deploy-time site assembly, cache busting, canonical/share metadata injection, and site path injection
- `scripts/verify_deploy.py`: post-deploy polling and verification for published Pages URLs against cache-busted HTML and deploy metadata
- `.github/actions/verified-commit/action.yml` and `.github/actions/verified-commit/verified-commit.mjs`: shared verified commit and PR fallback logic for CI
- `.github/actions/deploy-site/action.yml` and `.github/actions/deploy-site/deploy-verified.mjs`: verified deploy logic for `gh-pages` (full site, preview deploy, and preview removal)
- `.github/workflows/update.yml`: main automation workflow for pushes, PR previews, and manual runs

## Generated and derived files

These files are outputs. Prefer changing the generator instead of editing them directly.

- `js/data.js`
- `js/gallery-config.js`
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

- Add or modify artifacts in `apps/`.
- Use `make new name=my-artifact` when you want a correct starting structure quickly.
- Use `make check-local` for the fast local gate, `make web` for browser smoke/accessibility/browser-flow tests and thumbnails, and `make check` for the full pre-ship gate.
- Update generator logic in `scripts/` when derived output behavior should change.
- Use `make validate` to catch incomplete top-level artifact directories before pushing.
- Use `make index` to refresh `js/data.js`, `js/gallery-config.js`, and README markers.
- Use `make lock` after Python dependency changes, and refresh `package-lock.json` after Node dependency changes.
- Use `make thumbnails` or CI to regenerate thumbnails.
- Use `make site` to inspect the exact deployable Pages directory locally.
- Keep workspace-level configuration in `pyproject.toml` rather than scattering URLs or constants across scripts.
