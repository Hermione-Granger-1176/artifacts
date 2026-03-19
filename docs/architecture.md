# Architecture

## System shape

The deployed product is a static site with a generated data layer.

- `index.html` is the root shell for the gallery
- `css/style.css` styles the root gallery
- `js/app.js` renders the gallery experience in the browser
- `js/data.js` is generated metadata consumed by `js/app.js`
- `apps/*/index.html` pages are standalone artifacts and are linked from the gallery

## Runtime flow

At runtime, the root site works like this:

1. `index.html` loads the stylesheet and the two JavaScript files
2. `js/data.js` defines `window.ARTIFACTS_DATA`
3. `js/app.js` reads that array and builds the card grid, filters, search, and pagination UI
4. clicking a card opens details and links out to the artifact page in `apps/`

The gallery does not inspect artifact HTML directly in the browser. It depends on generated metadata.

## Build flow

### Metadata generation

`scripts/generate_index.py` is responsible for the gallery data layer.

- scans `apps/` for valid artifact folders
- reads `name.txt`, `description.txt`, `tags.txt`, and `tools.txt`
- resolves thumbnails with a preferred order of `thumbnail.webp` then `thumbnail.png`
- writes `js/data.js`
- updates README auto markers such as site URL, counts, and badges

### Thumbnail generation

`scripts/generate_thumbnails.py` is responsible for thumbnails.

- opens each artifact page in Playwright
- captures a screenshot in memory
- resizes and writes a WebP thumbnail
- removes legacy PNG thumbnails after successful WebP generation

## Configuration strategy

The repo now centralizes more workspace-level configuration in `pyproject.toml`.

- `[project]`: pinned Python dependencies
- `[project.optional-dependencies]`: dev tooling such as `pytest`, `pytest-cov`, and `ruff`
- `[tool.pytest.ini_options]`: test and coverage policy
- `[tool.ruff.*]`: lint policy
- `[tool.artifacts]`: canonical site URL and related workspace metadata

This reduces hardcoded values in scripts and keeps deployment-sensitive values in one place.

## Deployment flow

`.github/workflows/update.yml` is the main production workflow.

1. bootstrap the toolchain with `make setup-ci`
2. run linting and tests before generation
3. generate thumbnails and gallery data
4. stage generated additions and deletions
5. create a verified commit through the GitHub GraphQL API, or open a PR if branch protection blocks direct commit
6. apply deploy-time cache-busting query strings to root assets
7. upload and deploy the site to GitHub Pages

## Compatibility notes

The target steady state is WebP thumbnails. The index generator keeps temporary PNG fallback support so the site remains stable during migration windows or older branch checkouts.
