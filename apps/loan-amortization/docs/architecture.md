# Architecture

## Page sections

- Header shell: back button, home logo, and theme toggle aligned with the gallery contract
- Intro: app title and concise explanation of the calculator
- Layout: two columns inside a page shell widened app-locally to 1200px. The left input column is 300px wide and `position: sticky` (capped to the window height and scrolling internally if extras overflow it). Below 900px it stops being sticky and stacks above the results
- Input column, top to bottom:
  - Loan group: loan amount, interest rate, and tenure, each a shared `.control-field` row with the label left, the value field right, and the slider underneath
  - EMI frequency select, with the bi-weekly True/Accelerated toggle and its note beneath it only when bi-weekly is selected
  - Extra payments group: compact rows (type toggle, remove, labeled amount and timing fields, and a one-line summary), a quiet empty-state line, and the Add button
- Results column, top to bottom:
  - `#metrics`: the EMI as the hero number with a sub-line and a "saves $X, Ny Mm sooner" chip when extras help, then four KPI tiles (total interest, payoff in, total paid, break-even)
  - Charts / Schedule toggle
  - Charts view: all five charts stacked in the same chart-card style (title, legend, frame at one shared height). Scenario comparison and Interest saved sit as a pair when the column is wide enough and stack otherwise
  - Schedule view: per-period schedule and yearly summary tables
- Choice controls (Charts / Schedule, Per period / Yearly, recurring / one-time, bi-weekly method) use the shared inset pill: `.segmented.is-fused.is-inset`, or `.type-toggle.is-inset` for the bi-weekly method. The app adds only a gap between choices and a softer track border. The first three carry small inline SVG icons left of the label. All buttons share a tint on hover, a small press on `:active`, and the shared focus ring, and motion is dropped under `prefers-reduced-motion`

## Module map

- `js/vendor/`: vendored Chart.js 4.4.1, chartjs-plugin-annotation 3.0.1, chartjs-plugin-datalabels 2.2.0 (loaded via `<script defer>` with `<link rel="preload">` hints)
- `js/app.js`
  - owns bootstrap, mutable app state, and recalculation
- `../../../js/modules/app-shell.js`
  - owns shared theme sync, back-button fallback behavior, and scroll-to-top behavior
- `js/modules/amortization.js`
  - exports `calcEmi`, `getExtraForPeriod`, and `runSchedule`
- `js/modules/interactions.js`
  - owns event listener wiring while app state mutations stay injected from `js/app.js`
- `../../../js/modules/formatting.js`
  - exports currency formatting, axis tick formatting, and numeric parsing helpers
- `../../../js/modules/html-escape.js`
  - exports the safe attribute escaping used by metric and extras rendering
- `js/modules/metrics.js`
  - owns hero EMI, savings chip, and KPI tile template rendering, plus the periods-to-"Ny Mm" duration helper
- `js/modules/schedule-summary.js`
  - exports cadence metadata, accelerated bi-weekly EMI derivation, and schedule total rollups
- `js/modules/charts.js`
  - owns Chart.js initialization, palette refresh, and in-place chart updates; the theme-aware palette caching comes from the shared `js/modules/chart-theme.js` at the repo root
- `js/modules/tables.js`
  - exports table summary, period rows, and yearly rollup rendering
- `js/modules/extras.js`
  - exports extra-payment item creation, mutation helpers, summaries, and compact row rendering (each row shows its own summary line, which `js/app.js` refreshes as the fields change)
- `js/modules/ui.js`
  - owns DOM caching plus view-mode, slider-sync, and bi-weekly mode UI helpers

## State flow

- Scalar UI state lives in `js/app.js`:
  - `extras`
  - `nextExtraId`
  - `charts`
  - `bwMode`
- Input changes update slider/text state first, then call `recalc()`
- `recalc()` computes baseline + extra-payment schedules, refreshes metrics, updates visible charts in place, and refreshes visible tables

## Recalculation chain

1. Input event updates control state
2. `syncInputsFromSliders()` normalizes formatted text inputs
3. `recalc()` derives cadence params and optional accelerated bi-weekly EMI
4. `runSchedule()` returns baseline and extra-payment schedules
5. The renderer refreshes metrics, visible charts, and visible tables from the derived values

## Theme model

- `<html>` owns `data-theme="light|dark"`
- The shared `../../js/app-theme.js` head script applies the saved theme before first paint
- The app and root gallery share the `theme` localStorage key
