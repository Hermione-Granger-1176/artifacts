# Bonds vs Interest Rates

A scroll-through explainer of why bond prices fall when interest rates rise. Drag three sliders to reprice a bond you already own, then read why the price moved and what the same move does to the wider economy.

## Highlights

- Three sliders (market rate, coupon, years to maturity) drive a large price readout and premium/par/discount badge
- Price-vs-rate curve marks where the bond currently sits
- Discounting formula rendered in plain HTML and CSS (no math library, CSP-safe)
- Worked cash-flow table with per-year present value breakdown
- Percent price drop bar chart across maturities
- Yield curve presets (normal, flat, inverted) with chart
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
