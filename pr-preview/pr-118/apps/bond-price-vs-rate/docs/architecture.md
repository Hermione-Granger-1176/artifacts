# Architecture

## Page sections

- Header shell: back button, home logo, and theme toggle aligned with the gallery contract
- Intro: app title and a one-line framing of the inverse price-rate relationship
- Hero: a single control panel holding all three sliders (market rate, coupon, years to maturity) driving a large price readout, a premium/par/discount badge, a rate/price seesaw of arrows, an adaptive explanation, and a price-vs-rate curve marking the current bond
- Why it happens: a coupon-vs-market comparison and an adaptive mechanism paragraph, both driven by the hero's coupon slider
- The mathematics: an intro paragraph on discounting, the pricing formula rendered in plain HTML and CSS (styled spans, border-top fraction bars, sup/sub bounds and exponents, no math library so the self-only CSP holds), a live legend mapping each symbol to its current value, a scrollable worked cash-flow table (year, payment, discount factor, present value with a total row that equals the bond price), and an adaptive paragraph that walks the discounting from the coupons to the price
- How hard it swings: a bar chart of the one-point price drop by maturity (driven by the hero's years slider) and an adaptive sensitivity paragraph
- The yield curve: three preset shape buttons (normal, flat, inverted) driving a yield-by-maturity line chart with the bond's maturity marked, an adaptive shape-story paragraph, and an apply button that pushes the curve's rate at that maturity into the market-rate slider
- The analyst readout: four stat tiles (current yield, Macaulay duration, modified duration, convexity), a coupons-vs-face present-value split of the price, and an adaptive paragraph tying the duration estimate, the convexity cushion, and the DV01 together
- The ripple: an adaptive paragraph plus three cards (existing bondholders, tomorrow's bonds, the real economy)

The bond is a single object with a fixed face value ($1,000) and annual coupons (`frequency = 1`); the hero control panel's three sliders supply the market rate, the coupon, and the years to maturity.

## Module map

- `js/vendor/`: vendored Chart.js 4.4.1 (loaded via `<script defer>` with a `<link rel="preload">` hint). No annotation or datalabels plugins are used.
- `js/app.js`
  - owns bootstrap, mutable chart state, and high-level recalc orchestration
- `../../../js/modules/app-shell.js`
  - owns shared theme sync, back-button fallback behavior, and scroll-to-top behavior
- `js/modules/bond-math.js`
  - pure pricing math: bond price (present value of the coupon-plus-face schedule), the discounted cash-flow schedule (`bondSchedule`, one row per period with its payment, discount factor, and present value), premium/par/discount classification, the analytics bundle (price split, current yield, Macaulay and modified duration, convexity, DV01), and the yield-curve presets with their exponential-blend yield function
- `../../../js/modules/formatting.js`
  - shared `formatCurrency`, `formatPercent`, and `formatDollarTick`; bond call sites pass explicit fraction digits so the shared whole-dollar default never changes a value
- `js/modules/narrative.js`
  - owns the hero readouts (price, caption, badge, arrows, explanation), the coupon-vs-market bars, the pricing-formula legend values, the worked cash-flow table rows, the analyst stat tiles and price-split bars, the apply-curve button label, and the mechanism, mathematics, sensitivity, curve, analyst, and ripple paragraphs, all written with textContent/createElement
- `js/modules/charts.js`
  - owns Chart.js initialization and in-place updates for the price-rate curve, the sensitivity bars, and the yield-by-maturity curve; the theme-aware palette caching comes from the shared `js/modules/chart-theme.js` at the repo root
- `js/modules/interactions.js`
  - wires the three slider `input` events, the apply-curve-rate click, and the yield-curve preset group through the shared `js/modules/segmented.js` (which owns the active class and aria-pressed sync); app state mutations stay injected from `js/app.js`
- `js/modules/ui.js`
  - owns DOM caching, the live slider-value labels, and the chart-canvas lookup

## State flow

- Scalar UI state lives in `js/app.js`:
  - `charts`
  - `pendingRecalcFrame`
  - `selectedCurveKey` (which yield-curve preset is active)
- The bond terms are read from the slider elements on demand rather than mirrored into state
- Every slider drag updates its live label, then coalesces a recalc through `requestAnimationFrame`; curve-preset clicks update the pressed state and coalesce the same way
- The apply-curve button writes the curve's rate at the bond's maturity (rounded to the 0.1 slider step and clamped to 1-12) into the market-rate slider, then reuses the normal recalc path

## Recalculation chain

1. A slider `input` event updates the live value label and schedules a recalc (drags coalesce through `requestAnimationFrame`)
2. `recalc()` reads the bond terms, prices the bond, builds its discounted cash-flow schedule, and classifies the price regime
3. It samples price against the market rate for the hero curve, the percent price change from a one-point rate rise across maturities for the sensitivity bars, and the selected yield-curve preset across maturities for the curve chart
4. The narrative module rewrites the hero readouts, the coupon-vs-market bars, the pricing-formula legend, the worked cash-flow table, the analyst tiles and price split, the apply-curve button label, and the six explanation paragraphs
5. The three charts are created once and then updated in place with the new series and current-point highlights

## Theme model

- `<html>` owns `data-theme="light|dark"`
- The shared `../../../js/app-theme.js` head script applies the saved theme before first paint
- The same `theme` localStorage key as the root gallery is reused so theme changes stay synchronized across pages
- Charts read colors from CSS custom properties, cache the palette keyed by theme, and invalidate it through `refreshPalette()` on theme change
