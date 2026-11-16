# Architecture

## Page sections

- Header shell: back button, home logo, and theme toggle, aligned with the gallery contract.
- Intro: the app title and a short explanation of the calculator.
- Layout: two columns in a page shell that the app widens to 1200px. The left input column is 300px wide and `position: sticky`. It is capped at the window height and scrolls inside itself when the extra payments overflow it. Below 760px it stops being sticky and stacks above the results. The four KPI tiles use two columns from 761px to 1100px and below 700px. The savings chip always takes its own row under the EMI.
- Input column, top to bottom:
  - Loan group: loan amount, interest rate, and tenure. Each is a `.control-field` row with the label on the left, the value field on the right, and the slider beneath.
  - EMI frequency select, with the bi-weekly True and Accelerated toggle and its note beneath. The toggle keeps its place. It is dimmed and disabled unless bi-weekly is selected. See [decisions](decisions.md) for the layout reasoning.
  - Extra payments group: compact rows (type toggle, remove button, labeled amount and timing fields, and a one-line summary), an empty-state line, and the **+ Add extra payment** button.
- Results column, top to bottom:
  - `#metrics`: the EMI as the hero number with a sub-line. A "Saves $X · Ny Mm sooner" chip appears when extras help. The chip keeps its slot and fades out when there is nothing to show. Four KPI tiles follow: total interest, payoff time, total paid, and break-even.
  - Charts / Schedule toggle. The view area has a minimum height of one viewport.
  - Charts view: all five charts stacked in one card style (title, legend, and a frame at 260px). Scenario comparison and interest saved sit side by side when the column is wide enough, and stack otherwise.
  - Schedule view: summary tiles, then the per-period schedule or the yearly summary table.
- Choice controls (Charts / Schedule, Per period / Yearly, recurring / one-time, and the bi-weekly method) use the shared inset pill, `.segmented.is-fused.is-inset`, or `.type-toggle.is-inset` for the bi-weekly method. The app adds a gap between choices and a softer track border. The first three carry inline SVG icons to the left of the label. Buttons share a hover tint, a press on `:active`, and the shared focus ring. Motion stops under `prefers-reduced-motion`.

## Module map

- `js/vendor/`: vendored Chart.js 4.4.1, chartjs-plugin-annotation 3.0.1, and chartjs-plugin-datalabels 2.2.0, loaded with `<script defer>` and `<link rel="preload">` hints.
- `js/app.js`: bootstrap through the shared `initializeMatureApp`, mutable app state, `recalc`, and `renderResults`.
- `../../../js/modules/frame-scheduler.js`: `createFrameScheduler` coalesces slider input and extra-field typing into one recalc per animation frame.
- `../../../js/modules/offscreen-draws.js`: `createOffscreenDraws` holds a chart redraw while its canvas is off screen. It runs the latest redraw when the canvas nears the viewport.
- `../../../js/modules/dom-sync.js`: `setText` and `setAttr` write only when the value changed. `createElement` builds a node without parsing HTML.
- `../../../js/modules/app-shell.js`: shared theme sync, back-button fallback, and scroll-to-top.
- `js/modules/amortization.js`: exports `calcEmi`, `getExtraForPeriod`, and `runSchedule`.
- `js/modules/interactions.js`: event listener wiring. State changes stay injected from `js/app.js`.
- `../../../js/modules/formatting.js`: currency and axis tick formatting, and numeric parsing.
- `../../../js/modules/html-escape.js`: `escapeHtml`, which escapes the summary text in extras rendering.
- `js/modules/metrics.js`: builds the hero EMI, the savings chip, and the KPI text (`buildMetricsView`). `renderMetrics` writes them into the `data-metric` slots in `index.html`. The module also converts periods to a "Ny Mm" duration.
- `js/modules/schedule-summary.js`: cadence metadata, the accelerated bi-weekly EMI derivation, and schedule total rollups.
- `js/modules/charts.js`: Chart.js initialization, palette refresh, and in-place updates. A chart's first draw animates, and later draws do not. The palette comes from `../../../js/modules/chart-theme.js`.
- `js/modules/tables.js`: table summary, period rows, and yearly rollup rendering. The summary tiles and table rows are created once and reused. A redraw adds or removes only the difference.
- `js/modules/extras.js`: extra-payment item creation, mutation helpers, summaries, and compact row rendering. Each row shows its own summary line, which `js/app.js` refreshes as the fields change. A row rebuild returns focus to the control that was pressed.
- `js/modules/ui.js`: DOM caching, view-mode, table-mode, slider-sync, and bi-weekly mode helpers.

## State flow

- Scalar UI state lives in `js/app.js`:
  - `extras` and `nextExtraId`: the extra-payment rows and the next row ID.
  - `charts`: the Chart.js instances.
  - `bwMode`: the bi-weekly method.
  - `inputs`: the principal, rate, and tenure the calculation reads. They keep a typed value's precision.
  - `baseSchedule`: the schedule without extras, stored with the key of the loan terms it was built from.
  - `latest`: the inputs of the latest calculation. A hidden view draws from them when it opens.
  - `staleTables`: which of the period and yearly tables needs a redraw.
- Slider drags and extra-field typing call `scheduleRecalc`, which runs one `recalc()` per animation frame. Text-input commits, frequency changes, bi-weekly mode changes, and adding, removing, or retyping an extra call `recalc()` directly.
- `recalc()` computes the baseline and extra-payment schedules, writes the metrics, and calls `renderResults()`.
- `renderResults()` draws only the visible view. The hidden view costs nothing until it is shown.

## Recalculation chain

1. A slider drag reads all three sliders into `inputs` with `readSliderInputs()`. A text-field commit sets one field of `inputs` to the typed value, clamped to the slider range, and moves the slider to the nearest step. Either way, `syncTextInputs()` writes `inputs` back to the formatted text fields. A rejected value (empty, zero, or not a number) restores the last committed value in its field.
2. `recalc()` reads the loan terms from `inputs`, not from the sliders. It then derives the cadence parameters (`getFrequencyParams`) and the optional accelerated bi-weekly EMI (`getBiweeklyEmiOverride`).
3. `runSchedule()` returns the baseline schedule and the extra-payment schedule. The baseline depends only on the loan terms. `baseSchedule` keeps it until principal, rate, tenure, frequency, or bi-weekly mode changes. Typing in an extra field reuses it.
4. `renderMetrics()` updates the metric slots in place.
5. `renderResults()` draws the charts when the Charts view is open. In the Schedule view, it draws the summary tiles and the visible table, and marks the other table stale. Showing the Charts view draws every chart. Showing a table draws it if it is stale.

## Theme model

- `<html>` owns `data-theme="light|dark"`.
- The shared `../../js/app-theme.js` head script applies the saved theme before first paint.
- The app and the root gallery share the `theme` localStorage key.
