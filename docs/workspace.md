# Workspace Structure

This is the canonical reference for repository layout, file ownership, generated-output ownership, and source-of-truth files.

- For runtime, build, and deploy design, see [`architecture.md`](architecture.md).
- For day-to-day commands, CI parity, troubleshooting, and recovery, see [`operations.md`](operations.md).
- For long-term stability contracts and review points, see [`maintenance.md`](maintenance.md).

## What this repo is

This repository hosts a GitHub Pages gallery of interactive HTML artifacts.

- The root site is the gallery.
- Each artifact lives in its own folder under `apps/`.
- Python build tooling generates gallery data, thumbnails, and the deployable site payload.
- GitHub Actions deploys the verified `_site/` artifact and publishes PR previews without writing to contributor branches during the main publish flow.

## Top-level layout

```text
.
|- .editorconfig             Editor settings for all file types
|- .github/
|  |- actions/               Shared composite actions (ci-setup, deploy-site, verified-commit)
|  |- workflows/             CI/CD automation
|  |- ISSUE_TEMPLATE/        Bug report and feature request forms
|  |- CODE_OF_CONDUCT.md     Collaboration expectations
|  |- CONTRIBUTING.md        Contribution workflow
|  |- dependabot.yml         Automated dependency update config
|  |- SECURITY.md            Vulnerability reporting
|  |- pull_request_template.md
|- apps/                     Artifact folders, each with index.html and metadata
|- assets/
|  |- fonts/                 Self-hosted web font subsets (Caveat, Fredoka One)
|  |- icons/                 Logo, favicon, and web app manifest
|  |- social/                Social share preview image
|- config/                   Gallery metadata and security audit policy
|- css/                      Root gallery styles and shared app design tokens
|- docs/                     Workspace documentation and ADRs
|- js/
|  |- app.js                 Root gallery entry point
|  |- app-theme.js           Shared mature-app theme bootstrap
|  |- data.js                Generated artifact metadata
|  |- gallery-config.js      Generated display config
|  |- modules/               Shared JS modules (runtime, element-cache, app-runtime, app-shell, html-escape)
|  |  |- gallery/            Gallery-specific JS modules (gallery-app, catalog, config, render, etc.)
|- locks/                    Frozen Python dependency lock files
|- scripts/
|  |- build/                 Index generation (with index_config, index_sources, index_outputs), thumbnail planning, thumbnails, site assembly, scaffolding
|  |- ci/                    Workflow helpers, deploy verification, security audits, issue alerts
|  |- lib/                   Shared libraries (app discovery, artifact contract, GitHub API, project config, path validation)
|  |- lint/                  EditorConfig check, table alignment, workflow linting, doc-command validation, JS test coverage lint, generated-drift detection, Make-target validation
|- tests/
|  |- build/                 Tests for scripts/build/
|  |- ci/                    Tests for scripts/ci/
|  |- lib/                   Tests for scripts/lib/
|  |- lint/                  Tests for scripts/lint/
|  |- browser/               Playwright smoke, accessibility, and flow tests
|  |- js/
|  |  |- home/               Root gallery Node unit tests
|  |  |- common/             Shared app/runtime Node unit tests
|  |  |- apps/               App-specific Node unit tests grouped by slug
|  |  |- workflows/          Node tests for GitHub action modules
|- 404.html                  GitHub Pages error page
|- index.html                Root gallery entry point
|- Makefile                  Primary interface for supported workspace commands (run make help)
|- pyproject.toml            Python deps, tool config, site metadata
|- package.json              Node deps, npm scripts, JS test/coverage config
|- eslint.config.js          ESLint scope and rules
|- stylelint.config.js       Stylelint scope and rules
|- .yamllint.yml             Yamllint scope and rules
```

## Source of truth by area

- `docs/workspace.md`: repository layout, file ownership, generated outputs, and source-of-truth-by-area
- `docs/architecture.md`: runtime, build, deploy, and workflow design
- `docs/operations.md`: command selection, CI mirroring, troubleshooting, and recovery
- `docs/maintenance.md`: long-term contracts, review points, and stability expectations
- `apps/*/index.html`: artifact implementation
- `apps/*/name.txt`, `description.txt`, `tags.txt`, `tools.txt`: artifact metadata
- `index.html`, `css/style.css`, `css/gallery/*`, `js/app.js`, `js/modules/gallery/*`: root gallery UI
- `js/modules/runtime.js`, `js/modules/element-cache.js`, `js/modules/html-escape.js`: shared JS utilities
- `css/app-tokens.css`, `css/app-shell.css`, `js/app-theme.js`, `js/modules/app-shell.js`: shared mature-app design and interaction system
- `assets/fonts/*`: self-hosted Latin web font subsets for gallery display fonts
- `css/fonts.css`: `@font-face` declarations for self-hosted Caveat and Fredoka One
- `assets/icons/*`: logo, favicon, apple touch icon, PWA manifest, and raster icons
- `assets/social/share-preview.png`: social preview image referenced by deploy-time Open Graph and Twitter metadata
- `config/gallery_metadata.json`: shared tool and tag display metadata used by generators to produce `js/gallery-config.js` and ordered README badges
- `config/artifact_contract.json`: shared artifact id, URL, and thumbnail-path contract emitted into `js/gallery-config.js` and enforced by Python build validation
- `config/security_audit.json`: source of truth for Python security-audit lock files and reviewed vulnerability exceptions
- `docs/adr/*`: accepted cross-cutting decisions about the root publishing platform
- `pyproject.toml`: Python dependency declarations, tool configuration, and workspace metadata
- `locks/requirements.lock`, `locks/requirements-dev.lock`: frozen Python dependency graphs
- `package.json`: Node dependency declarations, npm scripts, and JS test/coverage configuration where applicable
- `package-lock.json`: frozen Node dependency graph
- `scripts/build/prepare_site.py`: deploy-time site assembly, cache busting, canonical/share metadata injection, site path injection, and CSS/JS minification via esbuild
- `scripts/ci/verify_deploy.py`: post-deploy polling and verification for published Pages URLs against cache-busted HTML and deploy metadata
- `.github/actions/verified-commit/action.yml` and `.github/actions/verified-commit/verified-commit.mjs`: shared verified commit and PR fallback logic for CI
- `.github/actions/deploy-site/action.yml` and `.github/actions/deploy-site/deploy-verified.mjs`: verified deploy logic for `gh-pages` (full site, preview deploy, and preview removal)
- `.github/workflows/update.yml`: main automation workflow for pushes, PR previews, and manual runs
- `.github/workflows/live-site-smoke.yml`: scheduled live published-site browser smoke checks with issue-based alerting

## Generated and derived files

These files are outputs. Prefer changing the generator instead of editing them directly.

- `js/data.js`: generated from `apps/*/{name,description,tags,tools}.txt` and artifact discovery by `scripts/build/generate_index.py`
- `js/gallery-config.js`: generated from `config/gallery_metadata.json` and `config/artifact_contract.json` by `scripts/build/generate_index.py`
- README auto-marked values such as site URL, total count, and badges: generated by `scripts/build/generate_index.py` from `pyproject.toml`, `config/gallery_metadata.json`, and app metadata
- `apps/*/thumbnail.webp`: generated from rendered artifact pages by `scripts/build/generate_thumbnails.py`
- `_site/`: assembled by `scripts/build/prepare_site.py` from tracked source files plus generated assets

The website is the canonical artifact catalog. `README.md` intentionally keeps only a high-level snapshot instead of listing every artifact.

## Artifact folder contract

Each artifact directory under `apps/` is expected to contain:

- `index.html`: required entry point
- `css/app.css`: recommended app-local visual overrides for mature apps
- `js/app.js`: recommended app-local runtime entry for mature apps
- `docs/architecture.md`, `docs/verification.md`, `docs/decisions.md`: recommended internal docs for mature apps
- `README.md`: recommended app overview and folder map
- `tests/js/apps/<slug>/`: recommended matching app-specific Node test directory, created automatically by `make new`
- `name.txt`: required display name
- `description.txt`: optional short description
- `tags.txt`: optional tags, one per line
- `tools.txt`: optional AI tools, one per line
- `thumbnail.webp`: preferred generated thumbnail when present

## Editing rules

- Add or modify artifacts in `apps/`.
- Use Makefile targets for normal local and documented workflows. See [`operations.md`](operations.md) for which targets to run in each workflow.
- Use `make new name=my-artifact` when you want a correct starting structure quickly; it also creates the matching `tests/js/apps/<slug>/` directory.
- Update generator logic in `scripts/` when derived-output behavior should change.
- Prefer keeping tool scope in its owning config file, and avoid adding ad hoc duplicated file selection unless a target or workflow truly needs it.
- Use `make validate` when you change top-level artifact directories or the artifact folder contract.
- Keep site configuration, dependency declarations, and lockfiles in their owning files, primarily `pyproject.toml`, `package.json`, `package-lock.json`, `locks/*.lock`, and `config/*.json`.
- If a repo-level ownership boundary changes, update this document and link to the owning adjacent doc instead of copying the same rule into multiple docs.
