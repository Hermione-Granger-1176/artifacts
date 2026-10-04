# Bonds vs Interest Rates

An explainer of why bond prices fall when interest rates rise. The price, its curve, and three sliders stay pinned on the left while seven numbered chapters scroll on the right, so you can reprice a bond you already own and read why the price moved and what the same move does to the wider economy.

## Highlights

- Two columns on the normal page scroll: a sticky left rail (price, premium/par/discount badge, price-vs-rate curve, then the market rate, coupon, and years sliders) beside the story. Below 960px the rail stops pinning and stacks above the chapters
- Seven numbered chapters (the inverse move, why it happens, how hard it swings, the yield curve, the maths, the analyst readout, the ripple). The chapter in view gets a filled number badge and full-strength heading and charts while the others sit slightly muted, tracked with an IntersectionObserver
- Price-vs-rate curve marks where the bond currently sits
- Discounting formula rendered in plain HTML and CSS (no math library, CSP-safe)
- Worked cash-flow table with per-year present value breakdown
- Percent price drop bar chart across maturities
- Yield curve presets (normal, flat, inverted) with chart, and a button that moves the market-rate slider in the rail to the curve's rate
- Analyst readout: current yield, Macaulay duration, modified duration, convexity, DV01
- Adaptive ripple explanation for existing bondholders, tomorrow's bonds, the real economy

## Made with

- Claude
- Chart.js 4.4.1 (vendored)

## Structure

```text
index.html
css/app.css
js/
├── app.js
├── modules/
│   ├── bond-math.js
│   ├── chapters.js
│   ├── charts.js
│   ├── narrative.js
│   ├── interactions.js
│   └── ui.js
└── vendor/
    └── chart.umd.min.js
docs/
```

## Docs

See `docs/` for architecture, verification, and implementation decisions.
