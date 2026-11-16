# Architecture

This document explains how the browser runtime, build scripts, and deployment pipeline work together.

- [`workspace.md`](workspace.md) owns file ownership, generated outputs, and source-of-truth locations.
- [`ci.md`](ci.md) owns workflows, jobs, tokens, deployments, and GitHub settings.
- [`operations.md`](operations.md) owns day-to-day commands, browser setup, thumbnails, and vendored dependencies.
- [`troubleshooting.md`](troubleshooting.md) owns failure symptoms and recovery.
- [`maintenance.md`](maintenance.md) owns periodic upkeep and stability contracts.

The workflow files and helper scripts are the executable source of truth. This document records the intended design and the boundaries between components.

## Overview

This repository publishes interactive HTML artifacts on GitHub Pages. Each app is an entry page under `apps/` with its own runtime files. The platform renders the gallery, generates thumbnails and metadata, deploys PR previews and the main site, and verifies each deploy.

The system has three layers:

1. The runtime layer is the gallery in the browser. This page describes it in [Runtime layer](#runtime-layer).
2. The build layer generates metadata, thumbnails, and the deployable site. This page describes it in [Build layer](#build-layer).
3. The CI/CD layer carries a commit to the live site and runs checks at each step. [`ci.md`](ci.md) describes its workflows, jobs, and deploy steps.

## Runtime layer

The deployed site is static HTML plus generated data files. [`frontend.md`](frontend.md) describes each module in detail.

- `index.html` is the gallery shell.
- The ordered `css/src/` partials hold the gallery styles, shared app tokens, shell rules, reusable app components, utilities, and responsive rules. `make styles` bundles them into the single public `css/style.css`. A mature app loads `css/style.css` first and then its own composition and layout rules from `apps/<slug>/css/app.css`.
- `js/app.js` validates the bootstrap data and initializes the gallery.
- `js/modules/gallery/*` holds the gallery modules: config validation, catalog helpers, render helpers, the book scene, URL state, the detail overlay, and the `gallery-app.js` orchestrator.
- `js/modules/runtime.js` and `js/modules/html-escape.js` are shared by the gallery and the apps. `js/modules/element-cache.js` and the other shared modules in `js/modules/` serve the apps.
- `js/gallery-config.js` (generated) holds the shared display metadata.
- `js/data.js` (generated) holds the artifact metadata.
- `js/app-theme.js`, `js/modules/app-shell.js`, and `js/modules/app-runtime.js` form the shared mature-app system.
- `apps/*/index.html` is each artifact's entry point, with app-local JS and docs beside it.

### How the gallery loads

1. `index.html` runs the classic script `js/app-theme.js` in the head, then loads `css/style.css`.
2. `js/gallery-config.js` defines `window.ARTIFACTS_CONFIG`.
3. `js/data.js` defines `window.ARTIFACTS_DATA`.
4. The classic script `js/boot-guard.js` waits 8 seconds. If the module has not marked the runtime ready by then, it reveals the `#runtime-error` banner.
5. The module `js/app.js` runs on `DOMContentLoaded`. It validates the bootstrap data, calls `initializeGalleryApp`, and marks the runtime ready.
6. `js/modules/gallery/gallery-app.js` restores URL-synced search, filters, and sort, and manages theme, overlays, keyboard shortcuts, cards, and pagination.
7. `js/modules/gallery/book-scene.js` animates the scrapbook cover and page turns, including pointer-driven dragging.
8. The first click on a card loads `detail-overlay.js` with a dynamic `import()` and opens the detail panel. Later clicks reuse the cached module.

The gallery never reads artifact HTML. It depends entirely on the generated metadata.

## Build layer

### Metadata generation (`scripts/build/generate_index.py`)

- Uses an `IndexConfig` context object (`scripts/build/index_config.py`) that centralizes all generation configuration and convenience methods
- Loads the artifact contract via `scripts/lib/artifact_contract.py`, which provides shared contract types and path helpers used by both the index generator and app discovery
- Scans `apps/` for valid artifact folders
- Reads `name.txt`, `description.txt`, `tags.txt`, `tools.txt`
- Resolves thumbnails from `thumbnail.webp`
- Writes `js/gallery-config.js` and `js/data.js`
- Updates README auto markers (site URL, counts, badges)
- Checks artifact folders in `make validate`, which calls `validate()` in the same module

### Stylesheet bundling (`scripts/build/generate_styles.py`)

- Concatenates the `css/src/NN-name.css` partials in filename order into `css/style.css`
- Rejects symlinks, filenames that do not match `NN-name.css`, and a light and dark theme pair that does not declare the same tokens on the same lines

### Thumbnail generation (`scripts/build/generate_thumbnails.py`)

- Serves the repo over local HTTP so app pages load shared CSS and JS
- Skips an artifact whose thumbnail is newer than its runtime files
- Opens each artifact page in Playwright
- Waits for `window.__ARTIFACT_READY__ !== false` before capture
- Captures, resizes to at most 960 pixels wide, and writes a WebP thumbnail, retrying a failed screenshot up to three times
- Reads `ARTIFACTS_THUMBNAIL_SLUGS` or a shard manifest to limit the run to some artifacts

### Deployable site assembly (`scripts/build/prepare_site.py`)

- Copies `404.html`, `assets/`, `css/`, `index.html`, and `js/` into `_site/`
- Copies only the runtime files of each app (`index.html`, `css/`, `js/`, `assets/`, and `thumbnail.webp`), so app docs and metadata stay out of the site
- Omits the build-only `css/src/` partials because `css/style.css` already bundles them
- Appends a content-hash `?v=` query string to the root asset URLs and to each app's shared and app-local CSS and JS URLs
- Injects canonical, Open Graph, and Twitter share metadata into the root page and each app page
- Injects the configured site path into `404.html` and the web app manifest
- Injects `<link rel="modulepreload">` hints by walking the static ES module import tree of each HTML entry point
- Minifies CSS and JS with esbuild, skipping vendored and already-minified files, and logs a warning instead when esbuild is missing
- Writes `deploy-metadata.json` with the deploy commit SHA and version
- Writes `.nojekyll`, which GitHub Pages needs to serve the files without Jekyll processing

## Configuration strategy

[Tool configuration](workspace.md#tool-configuration) in `workspace.md` maps each configuration file to the settings it owns.

## Design decisions

- [ADR 0001: Treat the repository root as a strict publishing platform](adr/0001-root-publishing-platform.md)
- [ADR 0002: Use a shared app system with planner-driven thumbnail persistence](adr/0002-shared-app-system-and-thumbnail-persistence.md)
- [ADR 0003: Makefile as sole interface, tool configs as single sources of truth](adr/0003-makefile-first-and-single-source-of-truth.md)
- [ADR 0004: Split artifact-specific CSS into app-local stylesheets](adr/0004-per-artifact-app-stylesheets.md)
- [ADR 0005: CI scaling architecture and roadmap](adr/0005-ci-scaling-architecture-and-roadmap.md)
- [ADR 0006: Adopt a shared design-token and component system for mature apps](adr/0006-shared-design-tokens-and-component-system.md)
- [ADR 0007: Keep themed colors in line-matched light and dark files](adr/0007-line-matched-theme-files.md)
- [ADR 0008: Try GraphQL first and fall back to REST for local GitHub tooling](adr/0008-graphql-first-rest-fallback.md)
