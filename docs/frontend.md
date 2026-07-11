# Frontend Guide

## Root gallery entry points

- `index.html` loads the root gallery shell
- `css/style.css` contains self-hosted font declarations, gallery styling, shared app tokens, and shared app shell styling. Each mature app keeps its layout selectors in `apps/<slug>/css/app.css`, scoped by its body class.
- `js/gallery-config.js` provides generated tool/tag labels, display order, and the shared artifact path contract from `config/gallery_metadata.json` and `config/artifact_contract.json`
- `js/data.js` provides generated artifact metadata
- `js/app.js` bootstraps the runtime, validates generated bootstrap data, and calls `initializeGalleryApp`

## Shared app system

- `css/style.css` owns the shared bookmark-note palette, light and dark themes, root gallery styling, and app shell styling
- `apps/<slug>/css/app.css` owns app-specific layout selectors and keeps the `body.app-<slug>` selector scope
- `js/app-theme.js` applies the saved mature-app theme before CSS loads
- `js/modules/app-shell.js` owns runtime theme toggling, back-button fallback behavior, and scroll-to-top behavior for app pages
- Mature app pages import `../../css/style.css` first and `./css/app.css` second, use `artifact-app` plus an `app-<slug>` body class, and keep app-local JavaScript inside `apps/<slug>/`

## JavaScript module responsibilities

Gallery modules (under `js/modules/gallery/`):

- `js/modules/gallery/gallery-app.js`: DOM wiring, event handlers, URL state, filtering, pagination, theme behavior, and book-scene integration
- `js/modules/gallery/catalog.js`: pure catalog helpers for search text, selection normalization, sorting, and pagination math
- `js/modules/gallery/config.js`: bootstrap data validation, generated config hydration, and label helpers
- `js/modules/gallery/detail-overlay.js`: detail panel lifecycle, open/close animation, and focus trapping (lazily loaded via dynamic import on first use)
- `js/modules/gallery/icons.js`: shared inline SVG icon markup
- `js/modules/gallery/inert.js`: background element inert/interactive toggling for overlay accessibility
- `js/modules/gallery/motion.js`: reduced-motion-aware scroll and animation helpers
- `js/modules/gallery/book-scene.js`: book cover intro animation and 3D page-turn motion
- `js/modules/gallery/render.js`: HTML generation and DOM sync helpers for cards, detail content, desk-note filters, and pagination
- `js/modules/gallery/gallery-url.js`: URL state sync for gallery search, filters, and sort

Shared modules (under `js/modules/`):

- `js/modules/runtime.js`: startup status, error reporting, and guarded localStorage access
- `js/modules/app-runtime.js`: mature-app bootstrap with fatal error handling
- `js/modules/element-cache.js`: DOM element caching by ID
- `js/modules/app-shell.js`: runtime theme toggling, back-button fallback behavior, and scroll-to-top behavior for app pages
- `js/modules/html-escape.js`: `escapeHtml()` and `escapeAttribute()` helpers, re-exported by `render.js` and app-local modules

The root filter UI is rendered as desk notes by `buildFilterNotes()` in `js/modules/gallery/render.js` and toggled in `js/modules/gallery/gallery-app.js`.

Interaction-heavy modules prefer guard clauses and small lookup maps when that keeps event routing linear and testable.

Invalid generated bootstrap data fails startup before the gallery initializes, which routes through the runtime error banner and global error reporting.

## Test coverage

- `tests/js/home/`: root gallery tests such as bootstrap wiring, catalog helpers, overlay behavior, rendering, keyboard flows, and home-page runtime coverage
- `tests/js/common/`: shared app-system tests for runtime helpers, app shell behavior, theme bootstrap, motion helpers, inert handling, and element caching
- `tests/js/apps/loan-amortization/`: app-specific entry, DOM, and module coverage for the loan amortization app
- `tests/js/apps/tokenizer-explorer/`: app-specific entry and module coverage for the tokenizer explorer app
- `tests/js/workflows/`: Node tests for the `deploy-site` and `verified-commit` GitHub composite-action modules
- `tests/browser/test_frontend_smoke.py`: browser smoke coverage for gallery load, invalid bootstrap data, search, desk-note filters, pagination, detail overlay, and `404.html`
- `tests/browser/test_frontend_accessibility.py`: Playwright + axe coverage for root light/dark themes, overlay state, no-results state, and `404.html`, plus explicit contrast assertions
- `tests/browser/test_frontend_browser_flows.py`: keyboard-only, mobile, reduced-motion, theme persistence, and larger-catalog browser interaction coverage
- `tests/browser/test_frontend_apps_smoke.py`: real app smoke coverage for mature app folders that opt into the shared app system
- `tests/browser/test_frontend_apps_accessibility.py`: Playwright + axe coverage for mature app shared-shell accessibility and contrast
- `tests/browser/test_frontend_apps_browser_flows.py`: mature app browser-flow coverage for app-specific interactions and theme behavior
- `tests/browser/test_frontend_live.py`: post-deploy browser verification for the published root and `404.html` when `ARTIFACTS_LIVE_SITE_URL` is set

## Accessibility notes for the root shell

- The root shell keeps keyboard focus visible across search, desk-note filters, pagination, overlay close/return, and the scroll-to-top control.
- `js/modules/gallery/gallery-app.js` keeps the theme toggle stateful with `aria-pressed`, updates the toggle label for the next theme, and announces result/theme changes through a dedicated live region.
- Artifact cards render as real `<button>` controls so keyboard and screen-reader semantics match the interaction model instead of relying on `role="button"` shims.
- `js/modules/gallery/render.js` gives the detail description a stable ID, and `js/modules/gallery/detail-overlay.js` uses it to describe the dialog while artifact links announce that they open in a new tab.
- `404.html` has explicit focus-visible styling so fallback navigation is keyboard-safe even outside the main app shell.
- `css/style.css` owns focus ring tokens, skip-link behavior, and accessible contrast tuning for active pagination and detail CTA states.
- `tests/browser/frontend_helpers.py` fails browser suites on `pageerror`, unexpected `console.error`, failed requests, and HTTP 4xx/5xx responses, and can emit screenshots, traces, and runtime logs for CI artifacts.

## Local vs CI expectations

- Use [operations.md](operations.md) as the canonical workflow reference; the targets below are the frontend-specific checkpoints you will use most often.
- `make test-js` runs the JavaScript unit suite with Node's built-in test runner across `tests/js/home/`, `tests/js/common/`, `tests/js/apps/`, and `tests/js/workflows/`
- `make coverage-js` uses Node's built-in experimental coverage report, which covers all source files imported by tests while excluding `node_modules/` and `tests/`. Thresholds and exclusions are configured in `package.json`
- `make check-local` runs the non-browser local gate: formatting, linting, dead-code checks, non-browser Python tests, JavaScript unit tests, JavaScript source-to-test coverage lint, JavaScript coverage, dependency audits, artifact validation, and canonical generated-file drift checks
- `make test-browser-root` runs all root-gallery Playwright suites
- `make test-browser-root-smoke`, `make test-browser-root-accessibility`, and `make test-browser-root-flows` run the root smoke, accessibility, and browser-flow suites separately
- `make test-browser-apps` runs all mature app Playwright suites; set `ARTIFACTS_BROWSER_APP_SLUGS` to limit coverage to specific app slugs
- `make test-browser-apps-smoke`, `make test-browser-apps-accessibility`, and `make test-browser-apps-flows` run the mature app smoke, accessibility, and browser-flow suites separately
- `make check-web` runs both root and app browser suites plus thumbnail generation; use `make setup-all` first so Chromium is available
- `make check` runs the full local release gate by combining `make check-local`, `make check-web`, index generation, and deployable site assembly
- `make test-browser` sets `ARTIFACTS_REQUIRE_BROWSER_TESTS=1`, so root and mature app browser suites must execute successfully instead of skipping when Chromium is unavailable
- `make test-browser-live` runs the published-site Playwright verification suite when `ARTIFACTS_LIVE_SITE_URL` is set
- full Istanbul/nyc-style instrumentation is intentionally not added because that would require extra dependencies beyond the current production-readiness scope
