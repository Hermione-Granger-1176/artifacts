# Frontend Guide

## Root gallery entry points

- `index.html` loads the root gallery shell
- `css/root-gallery-foundation.css` owns the shared theme and layout tokens used by the root gallery, including book height, page padding, and desk-note geometry
- `js/gallery-config.js` provides generated tool/tag labels and display order
- `js/data.js` provides generated artifact metadata
- `js/app.js` bootstraps the runtime, validates generated bootstrap data, and calls `initializeGalleryApp`

## JavaScript module responsibilities

- `js/modules/gallery-app.js`: DOM wiring, event handlers, URL state, filtering, pagination, theme behavior, and book-scene integration
- `js/modules/catalog.js`: pure catalog helpers for search text, selection normalization, sorting, and pagination math
- `js/modules/config.js`: bootstrap data validation, generated config hydration, and label helpers
- `js/modules/detail-overlay.js`: detail panel lifecycle, open/close animation, and focus trapping
- `js/modules/icons.js`: shared inline SVG icon markup
- `js/modules/inert.js`: background element inert/interactive toggling for overlay accessibility
- `js/modules/motion.js`: reduced-motion-aware scroll and animation helpers
- `js/modules/book-scene.js`: book cover intro animation and 3D page-turn motion
- `js/modules/render.js`: HTML generation and DOM sync helpers for cards, detail content, desk-note filters, and pagination
- `js/modules/runtime.js`: startup status, error reporting, and guarded localStorage access

The root filter UI is rendered as desk notes by `buildFilterNotes()` in `js/modules/render.js` and toggled in `js/modules/gallery-app.js`.

Interaction-heavy modules prefer guard clauses and small lookup maps when that keeps event routing linear and testable.

Invalid generated bootstrap data fails startup before the gallery initializes, which routes through the runtime error banner and global error reporting.

## Test coverage

- `tests/js/app.test.js`: DOMContentLoaded bootstrap wiring, fatal startup errors, and runtime handoff
- `tests/js/book-scene.test.js`: intro motion, reduced-motion handling, desktop/mobile page turns, and queued transitions
- `tests/js/catalog.test.js`: catalog helper behavior
- `tests/js/config.test.js`: config merging, bootstrap validation, and label fallbacks
- `tests/js/detail-overlay.test.js`: overlay open/close, focus trapping, animation, and motion preferences
- `tests/js/gallery-app.test.js`: gallery initialization, URL state, desk-note filters, pagination, overlay behavior, keyboard shortcuts, and theme persistence
- `tests/js/icons.test.js`: inline SVG export coverage for shared icon fragments
- `tests/js/inert.test.js`: element inert toggling and background content management
- `tests/js/motion.test.js`: reduced-motion detection, scroll behavior, and scroll-to-top
- `tests/js/render.test.js`: escaping, filter UI sync, detail content, card rendering, and pagination markup
- `tests/js/runtime.test.js`: runtime state, error capture, and fatal banner behavior
- `tests/js/verified-commit.test.js`: workflow helper logic for the verified-commit action
- `tests/js/deploy-verified.test.js`: deploy-site action logic (blob SHA, change computation, verified deploy, preview modes)
- `tests/test_frontend_smoke.py`: browser smoke coverage for gallery load, invalid bootstrap data, search, desk-note filters, pagination, detail overlay, and `404.html`

## Accessibility notes for the root shell

- The root shell keeps keyboard focus visible across search, desk-note filters, pagination, overlay close/return, and the scroll-to-top control.
- `js/modules/gallery-app.js` keeps the theme toggle stateful with `aria-pressed`, updates the toggle label for the next theme, and announces result/theme changes through a dedicated live region.
- `js/modules/render.js` gives the detail description a stable ID, and `js/modules/detail-overlay.js` uses it to describe the dialog while artifact links announce that they open in a new tab.
- `404.html` has explicit focus-visible styling so fallback navigation is keyboard-safe even outside the main app shell.
- `css/root-gallery-foundation.css` owns the root focus ring tokens and skip-link behavior; `css/root-gallery-artifacts.css` owns accessible contrast tuning for active pagination and detail CTA states.

## Local vs CI expectations

- `npm run test` runs the JavaScript unit suite with Node's built-in test runner
- `npm run test:coverage` and `make coverage-js` use Node's built-in experimental coverage report, which currently gates `js/app.js`, `js/modules/*.js`, `.github/actions/verified-commit/*.mjs`, and `.github/actions/deploy-site/*.mjs`
- `make check-local` runs the fast local gate: lint, non-browser pytest, JavaScript unit tests, JavaScript coverage, dependency audits, and artifact validation
- `make web` runs browser smoke tests and thumbnail generation; use `make setup` first so Chromium is available
- `make check` runs the full local release gate by combining `make check-local`, `make web`, index generation, and deployable site assembly
- `make test-browser` sets `ARTIFACTS_REQUIRE_BROWSER_TESTS=1`, so browser smoke tests must execute successfully instead of skipping when Chromium is unavailable
- full Istanbul/nyc-style instrumentation is intentionally not added because that would require extra dependencies beyond the current production-readiness scope
