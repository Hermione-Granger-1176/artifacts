# Architecture

## Page layout

The page is two columns on the normal page scroll. The shell is 1200px wide in app-local CSS, and the header widens with it so both share one left edge.

- Header shell: back button, home logo, and theme toggle, aligned with the gallery contract.
- Intro: the app title and a one-line statement of the inverse price-rate relationship.
- Left rail (about 352px, `position: sticky`): the price caption, the large price, the regime badge (premium, par, or discount), the price-vs-rate curve that marks the current bond, and three sliders (market rate, coupon, years to maturity). Each slider shows its live value and at most one short helper line. In a window too short to hold the rail, the rail scrolls inside itself. Between 761px and 960px the rail narrows to 300px and stays pinned. Below 760px it becomes static and stacks above the story.
- Story column: seven numbered chapters. Each has a number badge, a small label, a heading, and its content. A chapter shows at most one key-idea box, the shared blue `.app-callout`.

Three narrower breakpoints trim the layout further. At 700px the shell margins shrink. At 600px each chapter drops the badge column, and the badge stacks above the content. At 480px the comparison rows and the formula legend use narrower columns, and the legend becomes one column.

## Chapters

Adaptive paragraphs change their wording with the slider values.

1. The inverse move: the intro paragraph, the rate and price seesaw arrows, the adaptive hero explanation, and a note on reading the curve in the rail.
2. Why it happens: the coupon-vs-market comparison bars, and one callout with the static premium, par, and discount rule and the adaptive mechanism paragraph.
3. How hard it swings: a horizontal bar chart of the dollars that a one-point rate rise costs at 2, 5, 10, 20, and 30 years and at the bond's own maturity (the years slider). Each bar ends with the new price and the loss. The title names the rate move, for example 5.0% to 6.0%. An adaptive sensitivity paragraph follows.
4. The yield curve: three preset shape buttons (normal, flat, inverted), each with an inline curve glyph. They drive a yield-by-maturity line chart that marks the bond's maturity. An apply button copies the curve's rate at that maturity into the market rate slider in the rail. The readout flashes so the change is visible.
5. The maths: a discounting paragraph, the pricing formula rendered in plain HTML and CSS, a live legend that maps each symbol to its value, a scrollable worked cash-flow table, and an adaptive paragraph. The table's present values total the bond price.
6. The analyst readout: four stat tiles (current yield, Macaulay duration, modified duration, convexity), a split of the price into coupons and face value, and an adaptive paragraph that ties the duration estimate, the convexity cushion, and DV01 together.
7. The ripple: an adaptive paragraph and three cards (existing bondholders, tomorrow's bonds, the real economy).

Chapter text refers to the controls in the left rail.

The bond has a fixed $1,000 face value and annual coupons (`frequency = 1`). The three sliders supply the market rate, the coupon, and the years to maturity.

## Chapter tracking and controls

`js/modules/chapters.js` marks one chapter `.is-current`. An IntersectionObserver watches a band 10% tall, 30% from the top of the viewport. The chapter that crosses the band becomes current. A second observer covers the last chapter. That chapter can be too short to reach the band before the page runs out of scroll, so the observer activates it once it is fully visible. The story gets `.is-tracking` only when IntersectionObserver exists. The muting CSS applies only under `.is-tracking`, so a browser without IntersectionObserver shows every chapter at full strength.

Muted chapters drop their heading to the secondary text color, keep the number badge hollow, and fade their charts. Body text keeps full opacity. The current chapter has a filled badge, a full-strength heading, and full-strength charts.

The yield-curve toggle uses the shared inset pill, `.segmented.is-fused.is-inset`. Its choices tint on hover, and every button presses slightly on `:active`. Buttons also lift on hover. Only `transform` transitions on `.btn`. See [decisions](decisions.md) for the reason. Transitions use `--transition-fast`. Under `prefers-reduced-motion: reduce`, every transition stops, along with the press and lift transforms and the rate readout flash. Icons are inline SVG (16px, `currentColor`, 1.5px stroke) and always sit beside a label.

## Module map

- `js/vendor/`: vendored Chart.js 4.4.1, loaded with `<script defer>` and a `<link rel="preload">` hint. No annotation or datalabels plugins are used.
- `js/app.js`: bootstrap through the shared `initializeMatureApp`, the mutable chart state, and the recalc orchestration (`readBond`, `recalc`, and the series builders). It starts chapter tracking after the first render.
- `../../../js/modules/app-runtime.js`: `initializeMatureApp` installs the error handlers, runs the app once the DOM is ready, reports a thrown error as fatal, and sets `window.__ARTIFACT_READY__` after the first render returns.
- `../../../js/modules/frame-scheduler.js`: `createFrameScheduler` coalesces slider input into one recalc per animation frame.
- `../../../js/modules/offscreen-draws.js`: `createOffscreenDraws` holds a chart redraw while its canvas is off screen. It runs the latest redraw when the canvas nears the viewport.
- `../../../js/modules/app-shell.js`: shared theme sync, back-button fallback, and scroll-to-top.
- `js/modules/bond-math.js`: pure pricing math. It covers the bond price, the discounted cash-flow schedule (`bondSchedule`, one row per period), the regime (`priceRegime`), the analytics bundle, and the yield-curve presets with their yield function.
- `../../../js/modules/formatting.js`: `formatCurrency`, `formatPercent`, and `formatDollarTick`. Bond call sites pass explicit fraction digits.
- `js/modules/chapters.js`: the chapter highlighter. It owns the band and tail observers and the `.is-current` and `.is-tracking` classes.
- `js/modules/narrative.js`: writes the rail and chapter readouts, the coupon-vs-market bars, the formula legend values, the cash-flow table rows, the analyst tiles and price-split bars, the apply-curve button label, and the explanation paragraphs. It uses `textContent` and `createElement` only. It builds the stacked callouts (`renderVariants`) and their widest-number sizing copy (`sizingCopy`, from `WIDEST_STATE`).
- `js/modules/charts.js`: Chart.js setup and in-place updates for the price-rate curve, the sensitivity bars, and the yield-by-maturity curve. Each chart decides whether to redraw now, ease, or wait for its canvas to scroll in. The palette comes from `../../../js/modules/chart-theme.js`.
- `js/modules/interactions.js`: wires the three slider `input` events, the apply-curve click, and the yield-curve preset group through `../../../js/modules/segmented.js`. State changes stay injected from `js/app.js`.
- `js/modules/ui.js`: DOM caching, the live slider labels, the market-rate readout flash (`nudgeRateValue`), and the chart canvas lookup.

## State flow

- Scalar UI state lives in `js/app.js`: `charts`, `chartInputs` (the inputs each chart was last drawn from), and `selectedCurveKey` (the active yield-curve preset).
- The bond terms are read from the slider elements on demand. They are not mirrored into state.
- A slider `input` event updates its live label and calls `scheduleRecalc`, which coalesces recalcs through `requestAnimationFrame`. A curve preset click updates the pressed state and coalesces the same way.
- The apply-curve button writes the curve's rate at the bond's maturity into the market-rate slider. It rounds to the 0.1 slider step and clamps to 1-12. Then it flashes the readout and runs the normal recalc.

## Recalculation chain

1. A slider `input` event updates the live label and schedules a recalc.
2. `recalc()` reads the bond terms, prices the bond, builds the discounted cash-flow schedule and analytics bundle, and classifies the price regime.
3. It samples the price against the market rate for the rail curve. It computes the price after a one-point rate rise and the dollars lost at each maturity for the sensitivity bars. It samples the selected yield-curve preset across maturities for the curve chart.
4. The narrative module updates the rail and chapter readouts, the coupon-vs-market bars, the formula legend, the cash-flow table, the analyst tiles and price split, the apply-curve label, and the explanation paragraphs. It writes text only when the text changed. Bar rows and table rows persist, and rows are added or removed only when the years change. The bar width transition runs.
5. The three charts are created once and updated in place. A chart redraws only when its own inputs changed. `chartInputKeys` builds those inputs. The price curve and the sensitivity bars depend on all three sliders. The yield curve depends only on the curve shape and the years. An off-screen chart keeps its latest data pending and draws when it scrolls into view. Input-driven redraws skip Chart.js animation. Only the first draw and a curve switch ease, and only when reduced motion is off.

## Stable layout

- Copy that changes length sits in grid cells. Each variant stacks in one cell (`.reserve`), and only the active variant is visible. The tallest variant sets the height. The regime chip stacks its three labels. The hero, mechanism, curve, and ripple callouts stack their variants.
- Callouts also hold a hidden sizing copy (`.reserve-ghost`, `aria-hidden`) written with the longest numbers a slider can print (`WIDEST_STATE` in `narrative.js`). A digit more or less never changes where a line wraps.
- The first-paint copy of those callouts, the comparison rows, and the chip labels is in `index.html`. The script therefore does not change the height on first run.
- The cash-flow table box has a fixed height. The price keeps a minimum width. The rate and price arrows have a fixed width.

## Theme model

- `<html>` owns `data-theme="light|dark"`.
- The shared `../../js/app-theme.js` head script applies the saved theme before first paint.
- The app and the root gallery share the `theme` localStorage key.
- Charts read colors from CSS custom properties and cache the palette by theme. A theme change calls `refreshPalette()`, then `recalc({ redrawAll: true })` repaints every chart without animation.
