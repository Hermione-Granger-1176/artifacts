# Loan Amortization Schedule

Interactive loan amortization calculator with charts, extra payment scenarios, and detailed repayment schedules.

## Features

- Compare baseline payoff against extra-payment scenarios
- Switch between yearly, half-yearly, quarterly, monthly, bi-weekly, and weekly repayment cadences
- Review five visual breakdowns of balance, interest, savings, and per-period payments
- Inspect per-period and yearly repayment tables
- Persist light and dark theme using the same `data-theme` and `localStorage` model as the root gallery

## Structure

- `index.html` - app shell, metadata, and semantic layout
- `../../css/style.css` - shared site stylesheet, tokens, and app shell selectors
- `css/app.css` - calculator layout and component selectors
- `js/app.js` - bootstrap and top-level coordination across the smaller loan modules
- `js/modules/amortization.js` - amortization math and schedule generation
- `../../js/modules/formatting.js` - shared currency, tick, and attribute formatting helpers
- `js/modules/charts.js` - Chart.js rendering and theme-aware chart colors
- `js/modules/tables.js` - period summary and yearly summary rendering
- `js/modules/extras.js` - extra-payment state helpers and card rendering
- `js/modules/interactions.js` - event listener wiring with injected callbacks
- `js/modules/metrics.js` - metric card markup and rendering
- `js/modules/schedule-summary.js` - cadence helpers, accelerated bi-weekly EMI, and table totals
- `js/modules/ui.js` - DOM caching and UI state sync helpers
- `js/vendor/` - vendored Chart.js and plugin UMD bundles
- `docs/` - architecture notes, verification references, and implementation decisions

## Dependencies

- Chart.js 4.4.1 (vendored in `js/vendor/`)
- chartjs-plugin-annotation 3.0.1 (vendored in `js/vendor/`)
- chartjs-plugin-datalabels 2.2.0 (vendored in `js/vendor/`)

## Development notes

- Keep app CSS colors token-derived through `var()` or a `color-mix()` over shared tokens. Raw hex, named colors, and literal-channel color functions are rejected by `make lint-app-css-tokens`
- Treat the bookmark-note palette as the shared app visual system
- Preserve repayment calculations and payoff behavior when refactoring UI or structure
