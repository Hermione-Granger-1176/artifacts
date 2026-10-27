# Architecture

## Page sections

- Header shell: back button, home logo, and theme toggle aligned with the gallery contract
- Intro: app title and concise explanation of the calculator
- Layout: two columns inside a page shell widened app-locally to 1200px. The left input column is 300px wide and `position: sticky` (capped to the window height and scrolling internally if extras overflow it). Below 900px it stops being sticky and stacks above the results. The four KPI tiles use two columns from 901px to 1100px and below 700px, and the savings chip takes its own row below 700px
- Input column, top to bottom:
  - Loan group: loan amount, interest rate, and tenure, each a shared `.control-field` row with the label left, the value field right, and the slider underneath
  - EMI frequency select, with the bi-weekly True/Accelerated toggle and its note beneath it. The toggle always holds its place and is dimmed and disabled unless bi-weekly is selected, so the controls below never move
  - Extra payments group: compact rows (type toggle, remove, labeled amount and timing fields, and a one-line summary), a quiet empty-state line, and the Add button
- Results column, top to bottom:
  - `#metrics`: the EMI as the hero number with a sub-line and a "Saves $X · Ny Mm sooner" chip when extras help (the chip keeps its slot and fades out when there is nothing to show), then four KPI tiles (total interest, payoff in, total paid, break-even)
  - Charts / Schedule toggle. The view area has a minimum height of one viewport, so switching views never clamps the scroll position
  - Charts view: all five charts stacked in the same chart-card style (title, legend, frame at one shared height of 260px). Scenario comparison and Interest saved sit as a pair when the column is wide enough and stack otherwise
  - Schedule view: summary tiles, then the per-period schedule or the yearly summary table
- Choice controls (Charts / Schedule, Per period / Yearly, recurring / one-time, bi-weekly method) use the shared inset pill: `.segmented.is-fused.is-inset`, or `.type-toggle.is-inset` for the bi-weekly method. The app adds only a gap between choices and a softer track border. The first three carry small inline SVG icons left of the label. All buttons share a tint on hover, a small press on `:active`, and the shared focus ring, and motion is dropped under `prefers-reduced-motion`

## Module map

- `js/vendor/`: vendored Chart.js 4.4.1, chartjs-plugin-annotation 3.0.1, chartjs-plugin-datalabels 2.2.0 (loaded via `<script defer>` with `<link rel="preload">` hints)
- `js/app.js`
  - owns bootstrap through the shared `initializeMatureApp`, mutable app state, `recalc`, and `renderResults`
- `../../../js/modules/frame-scheduler.js`
  - `createFrameScheduler` coalesces slider input and extra-field typing into one recalc per animation frame
- `../../../js/modules/offscreen-draws.js`
  - `createOffscreenDraws` holds a chart redraw while its canvas is off screen and runs the latest one when the canvas scrolls near the viewport
- `../../../js/modules/dom-sync.js`
  - `setText` and `setAttr` write only when the value changed, and `createElement` builds a node without parsing HTML
- `../../../js/modules/app-shell.js`
  - owns shared theme sync, back-button fallback behavior, and scroll-to-top behavior
- `js/modules/amortization.js`
  - exports `calcEmi`, `getExtraForPeriod`, and `runSchedule`
- `js/modules/interactions.js`
  - owns event listener wiring while app state mutations stay injected from `js/app.js`
- `../../../js/modules/formatting.js`
  - exports currency formatting, axis tick formatting, and numeric parsing helpers
- `../../../js/modules/html-escape.js`
  - exports `escapeHtml`, which escapes the summary text in extras rendering
- `js/modules/metrics.js`
  - builds the hero EMI, savings chip, and KPI text (`buildMetricsView`), writes it into the `data-metric` slots that ship in `index.html` (`renderMetrics`), and converts periods to a "Ny Mm" duration
- `js/modules/schedule-summary.js`
  - exports cadence metadata, accelerated bi-weekly EMI derivation, and schedule total rollups
- `js/modules/charts.js`
  - owns Chart.js initialization, palette refresh, and in-place chart updates. A chart's first draw animates and later draws do not. Each chart redraws now when its canvas is near the viewport and otherwise keeps its latest redraw pending. The theme-aware palette caching comes from the shared `js/modules/chart-theme.js` at the repo root
- `js/modules/tables.js`
  - exports table summary, period rows, and yearly rollup rendering. The summary tiles and table rows are created once and reused, and a redraw adds or removes only the difference
- `js/modules/extras.js`
  - exports extra-payment item creation, mutation helpers, summaries, and compact row rendering (each row shows its own summary line, which `js/app.js` refreshes as the fields change). A row rebuild returns focus to the control that was pressed
- `js/modules/ui.js`
  - owns DOM caching plus view-mode, table-mode, slider-sync, and bi-weekly mode UI helpers

## State flow

- Scalar UI state lives in `js/app.js`:
  - `extras`
  - `nextExtraId`
  - `charts`
  - `bwMode`
  - `baseSchedule` (the schedule without extras, with the key of the loan terms it was built from)
  - `latest` (the inputs of the latest calculation, so a view that was hidden can be drawn when it is shown)
  - `staleTables` (which of the period and yearly tables needs a redraw)
- Slider drags and extra-field typing call `scheduleRecalc`, which runs one `recalc()` per animation frame. Text-input commits, frequency changes, bi-weekly mode changes, and adding, removing, or retyping an extra call `recalc()` directly
- `recalc()` computes the baseline and extra-payment schedules, writes the metrics, and calls `renderResults()`
- `renderResults()` draws only the visible view, so the hidden one costs nothing until it is shown

## Recalculation chain

1. An input event updates control state, and `syncInputsFromSliders()` copies the slider values into the formatted text inputs
2. `recalc()` reads the loan terms, then derives the cadence parameters (`getFrequencyParams`) and the optional accelerated bi-weekly EMI (`getBiweeklyEmiOverride`)
3. `runSchedule()` returns the baseline schedule and the extra-payment schedule. The baseline depends only on the loan terms, so `baseSchedule` keeps it until principal, rate, tenure, frequency, or bi-weekly mode changes, and typing in an extra field reuses it
4. `renderMetrics()` updates the metric slots in place
5. `renderResults()` draws the charts when the Charts view is open. In the Schedule view it draws the summary tiles and only the visible table, and marks the other table stale. Showing the Charts view draws every chart, and showing a table draws it if it is stale

## Theme model

- `<html>` owns `data-theme="light|dark"`
- The shared `../../js/app-theme.js` head script applies the saved theme before first paint
- The app and root gallery share the `theme` localStorage key
