# Bonds vs Interest Rates

A plain-language, scroll-through explainer of why bond prices fall when interest rates rise. Drag three sliders to reprice a bond you already own, then read exactly why the price moved and what the same move does to the wider economy.

## The seven sections

1. **The inverse move (hero).** One control panel holds all three sliders (market rate, coupon, years to maturity). They drive a large price readout, a premium/par/discount badge, and a seesaw of arrows that always point opposite ways. A price-vs-rate curve marks where the bond currently sits.
2. **Why it happens.** A coupon-vs-market comparison shows that the payments are fixed, so only the price can move to make an older bond compete with newly issued ones.
3. **The mathematics.** The full discounting story: a paragraph on why a dollar in year t is worth 1/(1+r)^t today, the pricing formula rendered in plain HTML and CSS (no math library, so the self-only CSP holds), a live legend mapping each symbol to its current value, and a scrollable worked cash-flow table (year, payment, discount factor, present value) whose present values total the bond price.
4. **How hard it swings.** A bar chart shows the percent price drop from a one-point rate rise across maturities, with the current bond highlighted.
5. **The yield curve.** Three preset shapes (normal, flat, inverted) drive a yield-by-maturity chart with the bond's maturity marked, a paragraph on what each shape signals, and a button that pushes the curve's rate at that maturity into the market-rate slider.
6. **The analyst readout.** Four live stat tiles (current yield, Macaulay duration, modified duration, convexity), a coupons-vs-face split of where the price comes from, and a paragraph comparing the duration estimate with the exact reprice and quoting the DV01.
7. **The ripple.** An adaptive paragraph plus three cards tie the current move to existing bondholders, tomorrow's bonds, and the real economy.

Every slider recomputes and repaints the whole page. The bond is one object with fixed face value ($1,000) and annual coupons.

## Structure

- `index.html` - page shell, the hero control panel with the three sliders, hero readouts, the CSS-rendered pricing formula and its legend, the worked cash-flow table body, the yield-curve preset buttons, three chart canvases, and the ripple cards
- `css/app.css` - hero stage, comparison bars, the pricing formula and legend, the schedule table, section cards, stat tiles, chart sizing, and badge/arrow styling scoped under `body.app-bond-price-vs-rate`
- `js/app.js` - bootstrap, slider reads, curve-preset state, and recalc orchestration
- `js/modules/bond-math.js` - pure pricing math (no DOM): bond price, the discounted cash-flow schedule, price-regime classification, the analytics bundle (duration, convexity, DV01, current yield, price split), and the yield-curve presets
- `js/modules/formatting.js` - currency and percent formatting, plus the shared tick formatter from the repo-root `js/modules/formatting.js`
- `js/modules/charts.js` - Chart.js creation and in-place updates for the three charts, with palette caching from the shared `js/modules/chart-theme.js`
- `js/modules/narrative.js` - hero readouts, coupon-vs-market bars, the formula legend and worked cash-flow table, analyst tiles, price split, and the adaptive explanation paragraphs
- `js/modules/interactions.js` - slider, curve-preset, and apply-button event wiring
- `js/modules/ui.js` - DOM caching and slider-label helpers
- `js/vendor/` - vendored Chart.js
- `docs/` - internal engineering notes

## Dependencies

- Chart.js 4.4.1

Chart.js is vendored under `js/vendor/` and loaded via `<script defer>` with a `<link rel="preload">` hint so the self-only Content-Security-Policy keeps holding. No CDN or other off-origin requests. The explainer uses only the core library: no annotation or datalabels plugins.

## Development

- Keep shared design decisions in `../../css/style.css` and app-specific layout in `css/app.css`
- Charts must read colors from CSS custom properties and cache the palette by theme; invalidate it through `refreshPalette()` on theme change
- Always verify the pricing math against the fixtures in `docs/verification.md` (encoded in `tests/js/apps/bond-price-vs-rate/bond-math.test.js`) before changing `js/modules/bond-math.js`
