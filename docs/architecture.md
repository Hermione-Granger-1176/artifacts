# Architecture

## System shape

The deployed product is a static site with a generated data layer.

- `index.html` is the root shell for the gallery
- `css/style.css` is the root gallery stylesheet entry point and imports the modular `css/root-gallery-*.css` files
- `js/app.js` bootstraps runtime validation and gallery initialization in the browser
- `js/modules/*` split the gallery logic into config validation, runtime diagnostics, catalog helpers, render helpers, book-scene motion helpers, and the main gallery orchestrator
- `js/gallery-config.js` is generated shared display metadata consumed by the frontend modules
- `js/data.js` is generated artifact metadata consumed by the frontend modules
- `apps/*/index.html` pages are standalone artifacts and are linked from the gallery

## Runtime flow

At runtime, the root site works like this:

1. `index.html` loads the stylesheet and the generated/runtime JavaScript files.
2. `js/gallery-config.js` defines `window.ARTIFACTS_CONFIG`.
3. `js/data.js` defines `window.ARTIFACTS_DATA`.
4. `js/app.js` creates the runtime, installs global error handling, validates generated bootstrap data, and calls `initializeGalleryApp`.
5. `js/modules/gallery-app.js` restores URL-synced search, multi-select filter, and sort state, then manages theme persistence, detail overlays, keyboard shortcuts, card rendering, and pagination.
6. `js/modules/book-scene.js` starts the book cover intro animation and animates 3D page turns during pagination.
7. Clicking a card opens details and links out to the artifact page in `apps/`.

The gallery does not inspect artifact HTML directly in the browser. It depends on generated metadata.

## Build flow

### Metadata generation

`scripts/generate_index.py` is responsible for the gallery data layer.

- Scans `apps/` for valid artifact folders.
- Reads `name.txt`, `description.txt`, `tags.txt`, and `tools.txt`.
- Resolves thumbnails with a preferred order of `thumbnail.webp` then `thumbnail.png`.
- Writes `js/gallery-config.js`.
- Writes `js/data.js`.
- Updates README auto markers such as site URL, counts, and badges.

### Thumbnail generation

`scripts/generate_thumbnails.py` is responsible for thumbnails.

- Opens each artifact page in Playwright.
- Captures a screenshot in memory.
- Resizes and writes a WebP thumbnail.
- Removes legacy PNG thumbnails after successful WebP generation.

### Deployable site assembly

`scripts/prepare_site.py` builds the clean Pages payload.

- Copies only the files needed for the static site into `_site/`.
- Applies cache-busting query strings to root assets.
- Injects canonical, Open Graph, and Twitter share metadata using the configured site URL and social preview image.
- Injects the configured site path into `404.html` and the web app manifest.
- Writes `deploy-metadata.json` with the exact deploy commit SHA, site path, and cache-busting version.
- Writes `.nojekyll` for branch-based Pages deployments.

## Configuration strategy

The repo now centralizes more workspace-level configuration in `pyproject.toml`.

- `[project]`: pinned Python dependencies.
- `[project.optional-dependencies]`: dev tooling such as `pytest`, `pytest-cov`, and `ruff`.
- `locks/requirements.lock` and `locks/requirements-dev.lock`: frozen Python dependency resolution used by `make setup`.
- `package-lock.json`: frozen Node dependency resolution used by `npm ci`.
- `[tool.pytest.ini_options]`: test and coverage policy.
- `[tool.ruff.*]`: lint policy.
- `[tool.artifacts]`: canonical site URL and related workspace metadata.

This reduces hardcoded values in scripts and keeps deployment-sensitive values in one place.

## Deployment flow

`.github/workflows/update.yml` is the main automation workflow for pushes, PR previews, and manual runs.

The rationale for the strict verified-artifact publish path lives in [ADR 0001](adr/0001-root-publishing-platform.md).

1. The `verify` job bootstraps with `make setup-ci`, then runs `make check`, which bundles local lint/test/audit/validation work, browser smoke/accessibility/browser-flow tests, strict thumbnail generation, content generation, and deployable site assembly.
2. `secret-scan` runs Gitleaks against the full commit history in parallel.
3. `dependency-review` checks manifest and lockfile changes on pull requests.
4. The `publish` job runs after `verify` and `secret-scan` succeed and `dependency-review` either succeeds or is skipped (push events skip it).
5. The publish path downloads the exact `_site/` artifact produced in `verify` instead of rebuilding during deployment.
6. For pushes to `main` and manual runs, it deploys that verified `_site/` artifact to the root of the `gh-pages` branch using a verified commit via the GraphQL API (`deploy-verified.mjs`), preserving the `pr-preview/` directory.
7. For trusted PRs, it deploys the verified `_site/` artifact to `gh-pages/pr-preview/pr-<number>/` via `deploy-verified.mjs` with `DEPLOY_SUBDIR`, without writing generated outputs back to the source branch.
8. It polls the published root or preview URL until it serves both the expected cache-busted asset reference and the expected `deploy-metadata.json` commit SHA.
9. It then runs `tests/test_frontend_live.py` against the published preview or production URL in Playwright, capturing failure artifacts when browser-only regressions appear after deploy.
10. It recreates the sticky preview link comment so the newest preview stays at the bottom of the PR timeline.
11. On PR close, it removes the preview from `gh-pages` via `deploy-verified.mjs` with `REMOVE_SUBDIR` and deletes the comment.

All jobs have explicit `timeout-minutes` limits (verify: 15, secret-scan: 5, dependency-review: 5, publish: 30, cleanup-preview: 5, repo-settings audit: 10) to guard against hung builds.

Two GitHub App tokens are minted by the shared `ci-setup` action: the primary app token (Hermione1176, `APP_ID`) remains available for other trusted workflow operations, while the escalation app token (Harry1176, `ESCALATION_APP_ID`) handles all write operations in this publish path including preview deploys, preview cleanup, and main site deploys. Fork and Dependabot PRs still build `_site/`, but skip deployment because the tokens are unavailable.

Same-repo Dependabot pip PRs use `.github/workflows/refresh-python-locks.yml` to compute refreshed lock files on the PR branch and `.github/workflows/commit-python-locks.yml` to validate the uploaded artifact contents in a follow-up trusted run before committing them if the PR head is unchanged.

Deployable site assembly uses `ARTIFACTS_DEPLOY_VERSION` when it is set, and otherwise falls back to `git rev-parse --short HEAD` for cache-busting asset URLs.

## External GitHub settings

The workflow depends on repository settings that are not enforceable from source control alone:

- GitHub Pages must publish from the `gh-pages` branch root.
- `vars.APP_ID` must contain the primary GitHub App id (Hermione1176).
- `secrets.APP_PRIVATE_KEY` must contain the primary app private key.
- `vars.ESCALATION_APP_ID` must contain the escalation GitHub App id (Harry1176).
- `secrets.ESCALATION_APP_PRIVATE_KEY` must contain the escalation app private key.
- `main` branch protection should enforce the `verify`, `secret-scan`, and `dependency-review` checks plus review/signing/history requirements.
- `gh-pages` should remain branch-based for now, but only the deploy GitHub App and the single repo admin should be able to bypass its ruleset.
- `.github/workflows/audit-repo-settings.yml` now provides a read-only manual/weekly drift check for those external settings.

## Compatibility notes

The target steady state is WebP thumbnails. The index generator keeps temporary PNG fallback support so the site remains stable during migration windows or older branch checkouts.

PR previews depend on the repository using branch-based GitHub Pages deployment with `gh-pages` as the published branch, so `gh-pages` protection must stay compatible with direct app-driven deploy writes until the repo migrates away from the legacy branch model.
