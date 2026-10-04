# Architecture

## Page layout

The page is two columns on the normal page scroll (there is no inner scroll box). The shell is widened to 1200px in app-local CSS, and the header widens with it so both share one left edge.

- Header shell: back button, home logo, and theme toggle aligned with the gallery contract
- Intro: app title and a one-line framing of the inverse price-rate relationship
- Left rail (about 352px, `position: sticky`): the price caption, the large price, the premium/par/discount badge, the price-vs-rate curve marking the current bond, then the three sliders (market rate, coupon, years to maturity) each with its live value and at most one short helper line. If a short window cannot hold the rail whole, it scrolls inside itself rather than clipping the sliders. Below 960px it becomes static and stacks above the story
- Story column: seven numbered chapters, each a number badge beside a kicker, a heading, and the chapter content. At most one key-idea box (the shared blue `.app-callout`) appears per chapter

## Chapters

1. The inverse move: the intro paragraph, the rate/price seesaw arrows, the adaptive hero explanation, and a note on reading the curve in the rail
2. Why it happens: the coupon-vs-market comparison bars, and one callout holding the static premium/par/discount rule plus the adaptive mechanism paragraph
3. How hard it swings: a bar chart of the one-point price drop by maturity (driven by the years slider) and an adaptive sensitivity paragraph
4. The yield curve: three preset shape buttons (normal, flat, inverted, each with a small inline curve glyph) driving a yield-by-maturity line chart with the bond's maturity marked, an adaptive shape-story paragraph, and an apply button that pushes the curve's rate at that maturity into the market-rate slider in the rail (the readout flashes so the move is visible)
5. The maths: an intro paragraph on discounting, the pricing formula rendered in plain HTML and CSS (styled spans, border-top fraction bars, sup/sub bounds and exponents, no math library so the self-only CSP holds), a live legend mapping each symbol to its current value, a scrollable worked cash-flow table (year, payment, discount factor, present value with a total row that equals the bond price), and an adaptive paragraph that walks the discounting from the coupons to the price
6. The analyst readout: four stat tiles (current yield, Macaulay duration, modified duration, convexity), a coupons-vs-face present-value split of the price, and an adaptive paragraph tying the duration estimate, the convexity cushion, and the DV01 together
7. The ripple: an adaptive paragraph plus three cards (existing bondholders, tomorrow's bonds, the real economy)

Chapter copy that used to say "the control panel above" now points to the controls on the left.

The bond is a single object with a fixed face value ($1,000) and annual coupons (`frequency = 1`); the rail's three sliders supply the market rate, the coupon, and the years to maturity.

## Chapter tracking and control feel

`js/modules/chapters.js` marks one chapter `.is-current`. An IntersectionObserver watches a band 10% tall, 30% from the top of the viewport, and the chapter crossing it becomes current. A second observer covers the last chapter, which can be too short to reach the band before the page runs out of scroll, by activating it once it is fully visible. The story gets `.is-tracking` only when IntersectionObserver exists, and the muting CSS is gated on it, so a browser without it leaves every chapter at full strength.

Muted chapters drop their heading to the secondary text colour, keep the number badge hollow, and fade their charts. Body text is never faded with opacity because that would push it under the 4.5:1 contrast floor. The filled badge, full-strength heading, and full-strength charts mark the current chapter.

Choices share one texture with the vendor docs app: the yield-curve toggle uses the shared inset pill, `.segmented.is-fused.is-inset` (recessed track, raised active pill with a small shadow). Its choices tint on hover, everything presses slightly on `:active`, and buttons lift on hover. Only `transform` transitions on `.btn`, so fills flip with the theme instead of fading through a low-contrast midpoint. Transitions use `--transition-fast`, and `prefers-reduced-motion: reduce` turns off every transition, the press and lift transforms, and the rate readout flash. Icons are inline SVG (16px, `currentColor`, 1.5px stroke) and always sit beside a label.

## Module map

- `js/vendor/`: vendored Chart.js 4.4.1 (loaded via `<script defer>` with a `<link rel="preload">` hint). No annotation or datalabels plugins are used.
- `js/app.js`
  - owns bootstrap, mutable chart state, and high-level recalc orchestration, and starts chapter tracking once the first render is done
- `../../../js/modules/app-shell.js`
  - owns shared theme sync, back-button fallback behavior, and scroll-to-top behavior
- `js/modules/bond-math.js`
  - pure pricing math: bond price (present value of the coupon-plus-face schedule), the discounted cash-flow schedule (`bondSchedule`, one row per period with its payment, discount factor, and present value), premium/par/discount classification, the analytics bundle (price split, current yield, Macaulay and modified duration, convexity, DV01), and the yield-curve presets with their exponential-blend yield function
- `../../../js/modules/formatting.js`
  - shared `formatCurrency`, `formatPercent`, and `formatDollarTick`; bond call sites pass explicit fraction digits so the shared whole-dollar default never changes a value
- `js/modules/chapters.js`
  - owns the chapter highlighter: the band and tail IntersectionObservers and the `.is-current` / `.is-tracking` classes
- `js/modules/narrative.js`
  - owns the rail and chapter 1 readouts (price, caption, badge, arrows, explanation), the coupon-vs-market bars, the pricing-formula legend values, the worked cash-flow table rows, the analyst stat tiles and price-split bars, the apply-curve button label (a text span beside its icon), and the mechanism, mathematics, sensitivity, curve, analyst, and ripple paragraphs, all written with textContent/createElement
- `js/modules/charts.js`
  - owns Chart.js initialization and in-place updates for the price-rate curve, the sensitivity bars, and the yield-by-maturity curve; the theme-aware palette caching comes from the shared `js/modules/chart-theme.js` at the repo root
- `js/modules/interactions.js`
  - wires the three slider `input` events, the apply-curve-rate click, and the yield-curve preset group through the shared `js/modules/segmented.js` (which owns the active class and aria-pressed sync); app state mutations stay injected from `js/app.js`
- `js/modules/ui.js`
  - owns DOM caching, the live slider-value labels, the market-rate readout flash (`nudgeRateValue`), and the chart-canvas lookup

## State flow

- Scalar UI state lives in `js/app.js`:
  - `charts`
  - `pendingRecalcFrame`
  - `selectedCurveKey` (which yield-curve preset is active)
- The bond terms are read from the slider elements on demand rather than mirrored into state
- Every slider drag updates its live label, then coalesces a recalc through `requestAnimationFrame`; curve-preset clicks update the pressed state and coalesce the same way
- The apply-curve button writes the curve's rate at the bond's maturity (rounded to the 0.1 slider step and clamped to 1-12) into the market-rate slider, flashes its readout, then reuses the normal recalc path

## Recalculation chain

1. A slider `input` event updates the live value label and schedules a recalc (drags coalesce through `requestAnimationFrame`)
2. `recalc()` reads the bond terms, prices the bond, builds its discounted cash-flow schedule, and classifies the price regime
3. It samples price against the market rate for the rail curve, the percent price change from a one-point rate rise across maturities for the sensitivity bars, and the selected yield-curve preset across maturities for the curve chart
4. The narrative module rewrites the rail and chapter readouts, the coupon-vs-market bars, the pricing-formula legend, the worked cash-flow table, the analyst tiles and price split, the apply-curve button label, and the six explanation paragraphs
5. The three charts are created once and then updated in place with the new series and current-point highlights

## Theme model

- `<html>` owns `data-theme="light|dark"`
- The shared `../../../js/app-theme.js` head script applies the saved theme before first paint
- The same `theme` localStorage key as the root gallery is reused so theme changes stay synchronized across pages
- Charts read colors from CSS custom properties, cache the palette keyed by theme, and invalidate it through `refreshPalette()` on theme change
