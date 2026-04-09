# Architecture

## Page sections

- Header shell: back button, home logo, and theme toggle aligned with the gallery contract
- Intro: app title and concise explanation of the calculator
- Inputs: loan amount, interest rate, tenure, repayment cadence, and bi-weekly mode
- Extra payments: recurring and one-time extra-payment cards with inline summaries
- Metrics: EMI, total interest, payoff duration, total paid, and break-even snapshot
- Charts: balance, scenario comparison, interest saved, cumulative payments, and per-period breakdown
- Tables: per-period schedule and yearly summary

## Module map

- `js/app.js`
  - owns bootstrap, mutable app state, and high-level recalc orchestration
- `../../../js/modules/app-shell.js`
  - owns shared theme sync, back-button fallback behavior, and scroll-to-top behavior
- `js/modules/amortization.js`
  - exports `calcEMI`, `getExtraForPeriod`, and `runSchedule`
- `js/modules/interactions.js`
  - owns event listener wiring while app state mutations stay injected from `js/app.js`
- `js/modules/formatting.js`
  - exports currency formatting, axis tick formatting, numeric parsing, and safe attribute escaping
- `js/modules/metrics.js`
  - owns metric-card template rendering
- `js/modules/schedule-summary.js`
  - exports cadence metadata, accelerated bi-weekly EMI derivation, and schedule total rollups
- `js/modules/charts.js`
  - owns theme-aware Chart.js initialization, palette refresh, and in-place chart updates
- `js/modules/tables.js`
  - exports table summary, period rows, and yearly rollup rendering
- `js/modules/extras.js`
  - exports extra-payment item creation, mutation helpers, summaries, and card rendering
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
5. Metrics are rerendered, visible charts are updated in place, and visible tables are refreshed from those derived values

## Theme model

- `<html>` owns `data-theme="light|dark"`
- The shared `../../../js/app-theme.js` head script applies the saved theme before first paint
- The same `theme` localStorage key as the root gallery is reused so theme changes stay synchronized across pages
