# Decisions

## Why a focused scroll-through explainer

The app trades a full metric dashboard for one story told top to bottom: the inverse move, why it happens, how hard it swings, and how it ripples out. All three sliders sit together in one hero control panel, right next to the price readout they drive, so the inputs and the headline output are never separated. The sliders originally lived one per section, but that scattered the controls across the page while the price stayed pinned at the top. The later sections stay focused on reading the story (the comparison bars, the sensitivity chart, the ripple cards) while pointing back to the panel. Fixed face value ($1,000) and annual coupons keep the numbers clean (a par bond prices to exactly its face value), so the reader's attention stays on the relationship rather than on conventions.

## Why plain ES modules

The app stays browser-native and deployable without a bundler. That keeps each artifact portable and compatible with the repository contract that `index.html` remains the entry point.

## Why vendored Chart.js, core library only

The page depends on Chart.js 4.4.1, self-hosted in `js/vendor/` rather than loaded from a CDN.

- **Cold-load performance**: CDN delivery adds latency from external DNS resolution, TLS handshake, and download. Vendoring serves the script from the same GitHub Pages origin over an existing HTTP/2 connection.
- **Resilience**: no runtime dependency on CDN availability or URL stability, which also keeps the self-only Content-Security-Policy intact.
- **Full UMD build**: the tree-shakeable ESM build is smaller but requires a bundler. The project uses plain `<script>` tags to stay portable, so the UMD build is the right trade-off.
- **No plugins**: the highlighted current point on the curve is a second one-point dataset and the highlighted sensitivity bar is a per-bar color, so neither the annotation nor the datalabels plugin is needed. They were removed from the page, `js/vendor/`, and the vendored-asset manifest.

## Why annual compounding and a fixed face value

The teaching bond (10-year, 5% coupon, $1,000 face) is easiest to reason about with annual coupons, where a par bond prices to exactly its face value. Holding face value and frequency constant removes two controls that do not change the shape of the story, leaving the three that do: the market rate, the coupon, and the years to maturity.

## Why the sensitivity chart uses a direct reprice

Rather than approximate the price move with modified duration, the sensitivity bars reprice the bond directly at the current rate and at the current rate plus one point for each maturity, then report the exact percent change. This keeps the chart honest and free of approximation error, while still showing the headline result: longer bonds swing far more.

## Why a separate analyst readout section

Duration, convexity, DV01, and current yield are the numbers a practitioner would actually quote, but leading with them would bury the story for a general reader. They live in their own late section as live stat tiles, after the intuition has been built, and the accompanying paragraph deliberately contrasts the duration straight-line estimate with the exact reprice so convexity is shown doing real work rather than named in passing. The price-split bars reuse the comparison-bar pattern from the coupon section so the page keeps one visual language.

## Why the mathematics is shown with a live table and an HTML-rendered formula

The mathematics section makes the pricing fully explicit: the formula, a legend of live values, and a worked cash-flow table whose present values total the price. The formula is built from styled spans (flex rows, border-top fraction bars, and sup/sub for the sum bounds and exponents) rather than MathJax or KaTeX, because the page ships a strict self-only Content-Security-Policy and vendoring a full math-typesetting library for one equation is not worth the weight or the added surface. The table is generated with createElement per recalc (no interpolated markup), reuses the shared `.table-wrap` and table styles other apps already use, and scrolls inside a fixed-height container so a 30-year bond's 30 rows do not stretch the page. Its total is the same bond price the hero shows, so the reader can watch every payment shrink and add back up to the headline number.

## Why three preset yield-curve shapes instead of a free-form curve

The yield-curve section teaches one idea: rates differ by maturity and the shape is a signal. Three canonical presets (normal, flat, inverted) cover the shapes people actually talk about, and an exponential blend from a short-end rate to a long-end rate gives smooth, realistic curves with two numbers per preset and no curve-fitting machinery. The bond itself still prices against the single market-rate slider so the earlier sections stay untouched; the bridge is an explicit button that copies the curve's rate at the bond's maturity into that slider, keeping one obvious source of truth for the price.

## Why `data-theme` plus localStorage

The root gallery already uses this model. Reusing it keeps theme state consistent when users move between the gallery and individual apps, and lets charts recolor through a single `refreshPalette()` call on theme change.

## Why the app exposes a ready signal

`window.__ARTIFACT_READY__` is set during the initial render so thumbnail generation can wait for the readouts and charts to finish drawing before capturing the page.

## Deferred items

- Semiannual and continuous compounding, day-count conventions
- Accrued interest and dirty vs clean price
- Discounting each cash flow off the curve's spot rates (the bond still prices against one flat rate; the curve section is context, not the discounting engine)
