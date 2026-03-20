# Frontend Guide

## Root gallery entry points

- `index.html` loads the root gallery shell
- `js/gallery-config.js` provides generated tool/tag labels and display order
- `js/data.js` provides generated artifact metadata
- `js/app.js` bootstraps the runtime, validates generated bootstrap data, and calls `initializeGalleryApp`

## JavaScript module responsibilities

- `js/modules/gallery-app.js`: DOM wiring, event handlers, URL state, filtering, pagination, and theme behavior
- `js/modules/catalog.js`: pure catalog helpers for search text, selection normalization, sorting, and pagination math
- `js/modules/config.js`: bootstrap data validation, generated config hydration, and label helpers
- `js/modules/detail-overlay.js`: detail panel lifecycle, open/close animation, and focus trapping
- `js/modules/filter-dropdown.js`: filter dropdown open/close state management
- `js/modules/icons.js`: shared inline SVG icon markup
- `js/modules/inert.js`: background element inert/interactive toggling for overlay accessibility
- `js/modules/motion.js`: reduced-motion-aware scroll and animation helpers
- `js/modules/render.js`: HTML generation and DOM sync helpers for cards, detail content, filters, and pagination
- `js/modules/runtime.js`: startup status, error reporting, and guarded localStorage access

Invalid generated bootstrap data fails startup before the gallery initializes, which routes through the runtime error banner and global error reporting.

## Test coverage

- `tests/js/catalog.test.js`: catalog helper behavior
- `tests/js/config.test.js`: config merging, bootstrap validation, and label fallbacks
- `tests/js/detail-overlay.test.js`: overlay open/close, focus trapping, animation, and motion preferences
- `tests/js/filter-dropdown.test.js`: dropdown toggle, open, close, and state queries
- `tests/js/gallery-app.test.js`: gallery initialization, URL state, filters, pagination, overlay behavior, keyboard shortcuts, and theme persistence
- `tests/js/inert.test.js`: element inert toggling and background content management
- `tests/js/motion.test.js`: reduced-motion detection, scroll behavior, and scroll-to-top
- `tests/js/render.test.js`: escaping, filter UI sync, detail content, card rendering, and pagination markup
- `tests/js/runtime.test.js`: runtime state, error capture, and fatal banner behavior
- `tests/js/verified-commit.test.js`: workflow helper logic for the verified-commit action
- `tests/test_frontend_smoke.py`: browser smoke coverage for gallery load, invalid bootstrap data, search, filters, pagination, detail overlay, and `404.html`

## Local vs CI expectations

- `npm run test` runs the JavaScript unit suite with Node's built-in test runner
- `npm run test:coverage` and `make coverage-js` use Node's built-in experimental coverage report, which is the current no-new-dependencies option in this repo
- `make check` runs Python tests and the JavaScript unit suite locally
- browser smoke tests are allowed to skip locally when Chromium is unavailable
- CI sets `ARTIFACTS_REQUIRE_BROWSER_TESTS=1`, so browser smoke tests must execute successfully there instead of skipping when Chromium is unavailable
- full Istanbul/nyc-style instrumentation is intentionally not added because that would require extra dependencies beyond the current production-readiness scope
