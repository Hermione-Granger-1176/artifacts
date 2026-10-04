# Decisions

## Why a pinned rail beside numbered chapters

All seven chapters use the same price and three inputs. The original top-of-page controls forced readers to scroll back to change a value. A sticky left column keeps the price, curve, and sliders visible beside the explanation.

The story uses normal page scrolling so anchors and find-in-page work without a second scroll area. Below 960px, the controls stack above the chapters. In a short desktop window, the control column scrolls internally so every slider remains reachable.

IntersectionObserver marks the current chapter with a filled badge and a stronger heading and chart. Body text retains full opacity because fading it failed the 4.5:1 contrast check. Each chapter has at most one shared blue callout. Longer slider explanations belong in their chapters, leaving one short helper line per slider.

The bond uses a fixed $1,000 face value and annual coupons. Those assumptions keep the lesson focused on the price-rate relationship.

## Why the apply button flashes the rate readout

"Set the market rate to this curve's rate" changes a slider in the rail, which can be a few hundred pixels from the button. The slider thumb moves on its own, and the readout also flashes briefly so the cause and effect are visible without looking for it. The flash is a CSS animation that the reduced-motion rule turns off.

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

For each maturity, the sensitivity bars price the bond at the current rate and one percentage point higher. They report the exact percentage change rather than a duration approximation. The resulting comparison shows how longer maturities increase rate sensitivity.

## Why a separate analyst readout chapter

Duration, convexity, DV01, and current yield are the numbers a practitioner would actually quote, but leading with them would bury the story for a general reader. They live in their own late chapter as live stat tiles, after the intuition has been built, and the accompanying paragraph deliberately contrasts the duration straight-line estimate with the exact reprice so convexity is shown doing real work rather than named in passing. The price-split bars reuse the comparison-bar pattern from the coupon chapter so the page keeps one visual language.

## Why the mathematics is shown with a live table and an HTML-rendered formula

The mathematics chapter includes the pricing formula, live symbol values, and a cash-flow table whose present values sum to the displayed price. Styled spans, fraction borders, and `sup` and `sub` elements render the formula without another library. That keeps the self-only CSP and avoids vendoring a typesetting dependency for one equation.

Each recalculation builds table cells with `createElement`. Shared `.table-wrap` styles provide a fixed-height scroll container, so a 30-year bond does not extend the page by 30 rows.

## Why three preset yield-curve shapes instead of a free-form curve

The yield-curve chapter teaches one idea: rates differ by maturity and the shape is a signal. Three canonical presets (normal, flat, inverted) cover the shapes people actually talk about, and an exponential blend from a short-end rate to a long-end rate gives smooth, realistic curves with two numbers per preset and no curve-fitting machinery. The bond itself still prices against the single market-rate slider so the earlier chapters stay untouched; the bridge is an explicit button that copies the curve's rate at the bond's maturity into that slider, keeping one obvious source of truth for the price.

## Why `data-theme` plus localStorage

The root gallery already uses this model. Reusing it keeps theme state consistent when users move between the gallery and individual apps, and lets charts recolor through a single `refreshPalette()` call on theme change.

## Why the app exposes a ready signal

`window.__ARTIFACT_READY__` is set during the initial render so thumbnail generation can wait for the readouts and charts to finish drawing before capturing the page.

## Deferred items

- Semiannual and continuous compounding, day-count conventions
- Accrued interest and dirty vs clean price
- Discounting each cash flow off the curve's spot rates (the bond still prices against one flat rate; the curve chapter is context, not the discounting engine)
