# Workspace structure

This reference describes repository layout, file ownership, generated outputs, and their source files. [`README.md`](README.md) indexes the document that owns every other concern, such as [`architecture.md`](architecture.md) for runtime, build, and deploy design and [`operations.md`](operations.md) for commands and recovery.

## What this repo is

This repository hosts a GitHub Pages gallery of interactive HTML artifacts.

- The root site is the gallery.
- Each artifact lives in its own folder under `apps/`.
- Python build tooling generates the shared stylesheet, gallery data, thumbnails, and the deployable site payload.
- GitHub Actions deploys the verified `_site/` artifact and publishes PR previews. The main publish flow never writes to contributor branches.

## Top-level layout

```text
.
|- .agents/skills/           Agent skill definitions (copilot-review-loop)
|- .claude/skills/           Claude Code skill definitions (copilot-review-loop)
|- .editorconfig             Editor settings for all file types
|- .github/
|  |- actions/               Shared composite actions (ci-setup, deploy-site, verified-commit)
|  |- codeql/                CodeQL scan scope
|  |- workflows/             CI/CD automation
|  |- ISSUE_TEMPLATE/        Bug report and feature request forms
|  |- CODEOWNERS             Default review owner
|  |- CODE_OF_CONDUCT.md     Collaboration expectations
|  |- CONTRIBUTING.md        Contribution workflow
|  |- dependabot.yml         Automated dependency update config
|  |- SECURITY.md            Vulnerability reporting
|  |- pull_request_template.md
|- .gitleaks.toml            Gitleaks scope for the CI secret scan
|- .gitleaksignore           Reviewed Gitleaks finding fingerprints
|- .pre-commit-config.yaml   Local pre-commit hooks
|- apps/                     Artifact folders, each with index.html and metadata
|- assets/
|  |- fonts/                 Self-hosted web font subsets (Caveat, Fredoka One)
|  |- icons/                 Logo, favicon, and web app manifest
|  |- scrapbook/             SVG doodles and snapshots used by the gallery stylesheet
|  |- social/                Social share preview image
|- config/                   Gallery metadata, artifact contract, tool configs (eslint, stylelint, and more), vendored-asset manifest, security audit policy, and hand-written type declarations (types/)
|- css/
|  |- src/                   Ordered shared stylesheet source partials
|  |- style.css              Generated shared stylesheet loaded by pages
|- docs/                     Workspace documentation and ADRs
|- js/
|  |- app.js                 Root gallery entry point
|  |- app-theme.js           Shared mature-app theme bootstrap
|  |- boot-guard.js          Reveals the startup error banner when the gallery module never starts
|  |- data.js                Generated artifact metadata
|  |- gallery-config.js      Generated display config
|  |- modules/               Shared JS modules (runtime, element-cache, app-runtime, app-shell, html-escape, formatting, segmented, section-nav, chart-theme, frame-scheduler, dom-sync, meter, offscreen-draws)
|  |  |- gallery/            Gallery-specific JS modules (gallery-app, catalog, config, render, etc.)
|- scripts/
|  |- check-overrides.mjs    npm overrides check behind make check-overrides
|  |- build/                 Index and stylesheet generation, thumbnail planning and generation, site assembly, scaffolding, share-image optimization
|  |- ci/                    Workflow helpers, impact plan and shard tooling, browser test runner, deploy verification, security audits, repo and preview audits, issue alerts, schedule watchdog, pin refresh, parallel check runner
|  |- gh/                    PR, issue, review-thread, and CI helpers behind the make pr-*, issue-*, and ci-* targets, with a REST fallback
|  |- lib/                   Shared libraries (app discovery, artifact contract, GitHub API and policy, project config, path validation, branch pruning, file staging, workspace status)
|  |- lint/                  EditorConfig check, table alignment, workflow linting, doc-command validation, JS test coverage lint and per-file floors, generated-drift detection, Make-target validation, artifact CSP checking, app CSS token linting, vendored-asset integrity
|  |- setup/                 No-sudo Playwright local-runtime provisioning
|- tests/
|  |- build/                 Tests for scripts/build/
|  |- ci/                    Tests for scripts/ci/
|  |- gh/                    Tests for scripts/gh/
|  |- lib/                   Tests for scripts/lib/
|  |- lint/                  Tests for scripts/lint/
|  |- setup/                 Tests for scripts/setup/
|  |- browser/               Playwright smoke, accessibility, flow, cross-engine, and visual regression tests
|  |- js/
|  |  |- home/               Root gallery Node unit tests
|  |  |- common/             Shared app/runtime Node unit tests
|  |  |- apps/               App-specific Node unit tests grouped by slug
|  |  |- tooling/            Node tests for repo tooling scripts
|  |  |- workflows/          Node tests for GitHub action modules
|- 404.html                  GitHub Pages error page
|- index.html                Root gallery entry point
|- Makefile                  Primary interface for supported workspace commands (run make help)
|- mk/                       Make targets, one NN-<group>.mk file per make help group
|- pyproject.toml            Python deps, tool config, site metadata
|- uv.lock                   Frozen Python dependency graph
|- package.json              Node deps, npm scripts, JS test/coverage config
|- .yamllint.yml             Yamllint scope and rules
```

## Source of truth by area

- `apps/*/index.html`: artifact implementation
- `apps/*/css/app.css`: app-specific composition and layout styles for mature apps. Reusable app components belong in `css/src/`
- `apps/*/name.txt`, `description.txt`, `tags.txt`, `tools.txt`: artifact metadata
- `index.html`, `css/style.css`, `css/src/`, `js/app.js`, `js/boot-guard.js`, `js/modules/gallery/*`: root gallery UI, shared app styling, and reusable app components
- `js/modules/runtime.js`, `js/modules/html-escape.js`: JS utilities that the gallery and the apps both import
- `js/modules/element-cache.js`: DOM element lookup by id, imported by the apps only
- `js/modules/formatting.js`, `js/modules/segmented.js`, `js/modules/section-nav.js`, `js/modules/chart-theme.js`, `js/modules/frame-scheduler.js`, `js/modules/dom-sync.js`, `js/modules/meter.js`, `js/modules/offscreen-draws.js`: shared artifact-app helpers for number formatting, segmented toggles, section-progress nav, theme-aware Chart.js palettes, once-per-frame recalculation, in-place DOM updates, meter fills, and holding chart redraws while a canvas is off screen
- `js/app-theme.js`, `js/modules/app-shell.js`, `js/modules/app-runtime.js`: shared mature-app theme, interaction, and bootstrap system
- `assets/fonts/*`: self-hosted Latin web font subsets for gallery display fonts
- `css/src/01-tokens.css`: `@font-face` declarations for self-hosted Caveat and Fredoka One, plus the gallery and app tokens that stay the same in both themes
- `css/src/01-theme-light.css`, `css/src/01-theme-dark.css`: every themed color, with the same tokens on the same lines in both files
- `css/style.css`: generated public bundle loaded by the gallery and mature apps. Rebuild it with `make styles`; do not edit it directly
- `assets/icons/*`: logo, favicon, apple touch icon, PWA manifest, and raster icons
- `assets/social/share-preview.png`: social preview image referenced by deploy-time Open Graph and Twitter metadata
- `config/gallery_metadata.json`: shared tool and tag display metadata used by generators to produce `js/gallery-config.js` and ordered README badges
- `config/artifact_contract.json`: shared artifact id, URL, and thumbnail-path contract emitted into `js/gallery-config.js` and enforced by Python build validation
- `config/types/*.d.ts`: hand-written type declarations for the vendored libraries and app globals, read by `make typecheck-web`
- `config/security_audit.json`: source of truth for reviewed Python, npm, and vendored-library vulnerability exceptions
- `config/vendored_assets.json`: integrity manifest pinning the version, upstream URL, and SHA-256 of each vendored library, enforced by `make lint-vendored-assets` and audited against OSV by `make audit-vendored`
- `docs/adr/*`: accepted architecture decision records
- `pyproject.toml`: Python dependency declarations, tool configuration, and workspace metadata
- `uv.lock`: frozen Python dependency graph
- `package.json`: Node dependency declarations, npm scripts, and JS test/coverage configuration where applicable
- `package-lock.json`: frozen Node dependency graph
- `scripts/build/prepare_site.py`: deploy-time site assembly, cache busting, canonical and share metadata injection, site path injection, module preload hints, and CSS and JS minification through esbuild
- `scripts/ci/verify_deploy.py`: post-deploy polling and verification for published Pages URLs against cache-busted HTML and deploy metadata
- `scripts/gh/`: PR, issue, review-thread, and CI helpers behind the `make pr-*`, `make issue-*`, and `make ci-*` targets, with a REST fallback when GraphQL is blocked, covered by `tests/gh/`
- `.github/actions/verified-commit/action.yml` and `.github/actions/verified-commit/verified-commit.mjs`: shared verified commit and PR fallback logic for CI
- `.github/actions/deploy-site/action.yml` and `.github/actions/deploy-site/deploy-verified.mjs`: verified deploy logic for `gh-pages` (full site, preview deploy, and preview removal)
- `.github/workflows/update.yml`: main automation workflow for pushes, PR previews, scheduled full sweeps, and manual runs. The [workflow reference](architecture.md#workflow-reference) lists every other workflow

## Generated and derived files

These files are generated outputs. Their inputs and generators determine their contents.

- `css/style.css`: bundled from the ordered `css/src/` partials by `scripts/build/generate_styles.py` (`make styles`)
- `js/data.js`: generated from `apps/*/{name,description,tags,tools}.txt` and artifact discovery by `scripts/build/generate_index.py`
- `js/gallery-config.js`: generated from `config/gallery_metadata.json` and `config/artifact_contract.json` by `scripts/build/generate_index.py`
- README auto-marked values such as site URL, total count, and badges: generated by `scripts/build/generate_index.py` from `pyproject.toml`, `config/gallery_metadata.json`, and app metadata
- `apps/*/thumbnail.webp`: generated from rendered artifact pages by `scripts/build/generate_thumbnails.py`
- `_site/`: assembled by `scripts/build/prepare_site.py` from tracked source files plus generated assets

The website is the canonical artifact catalog. `README.md` intentionally keeps only a high-level snapshot instead of listing every artifact.

## Artifact folder contract

The artifact contract includes these files. Paths are relative to the artifact directory unless they start with `tests/`:

- `index.html`: required entry point
- `js/app.js`: recommended app-local runtime entry for mature apps
- `docs/architecture.md`, `docs/verification.md`, `docs/decisions.md`: recommended internal docs for mature apps
- `README.md`: recommended app overview and folder map
- `css/app.css`: recommended app-local stylesheet loaded after the shared `css/style.css`
- `assets/`, `js/vendor/`: optional app-local runtime assets and vendored libraries (see [Vendored runtime dependencies](operations.md#vendored-runtime-dependencies))
- `tests/js/apps/<slug>/app.test.js`: matching app-specific Node test, emitted automatically by `make new`
- `name.txt`: required display name
- `description.txt`: optional short description
- `tags.txt`: optional tags, one per line
- `tools.txt`: optional AI tools, one per line
- `thumbnail.webp`: preferred generated thumbnail when present

`make site` deploys only `index.html`, `css/`, `js/`, `assets/`, and `thumbnail.webp` from each artifact folder. Metadata, `README.md`, and `docs/` stay in the repository.

## Editing workflow

[Contributing](../.github/CONTRIBUTING.md) gives the steps to add an artifact. [Operations](operations.md) lists the local checks and generation commands. The ownership rules are:

- Add or modify artifacts in `apps/`.
- Use Makefile targets for normal local and documented workflows. See [`operations.md`](operations.md) for which targets to run in each workflow.
- Run `make new name=my-artifact` for a starting structure that passes the gates: the shared-stylesheet and app-shell wiring, `css/app.css` and `js/app.js` stubs, `README.md` and `docs/` stubs, metadata files, and a passing `tests/js/apps/<slug>/app.test.js`.
- Run `make new name=my-artifact src=path/to/file.html` to import an existing HTML file. It installs the file as `index.html`, adds the CSP meta tag and shared stylesheet links only when they are absent, reports off-origin script or style references without rewriting them, and scaffolds the same app-local files, docs, and test stub.
- Update generator logic in `scripts/` when derived-output behavior should change.
- Prefer keeping tool scope in its owning config file, and avoid adding ad hoc duplicated file selection unless a target or workflow truly needs it.
- Use `make validate` when you change top-level artifact directories or the artifact folder contract.
- Keep site configuration, dependency declarations, and lockfiles in their owning files, primarily `pyproject.toml`, `uv.lock`, `package.json`, `package-lock.json`, and `config/*.json`.
- If a repo-level ownership boundary changes, update this document and link to the owning adjacent doc instead of copying the same rule into multiple docs.
