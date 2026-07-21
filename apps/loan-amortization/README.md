# Loan Amortization Schedule

Interactive loan amortization calculator with charts, extra payment scenarios, and detailed repayment schedules.

## Highlights

- Baseline payoff vs extra-payment scenario comparison
- Yearly, half-yearly, quarterly, monthly, bi-weekly, and weekly cadences
- Five visual breakdowns: balance, interest, savings, per-period payments
- Per-period and yearly repayment tables
- Light/dark theme persistence via shared app shell

## Made with

- Claude
- Chart.js 4.4.1 (vendored)
- chartjs-plugin-annotation 3.0.1 (vendored)
- chartjs-plugin-datalabels 2.2.0 (vendored)

## Structure

```text
index.html
css/app.css
js/
├── app.js
├── modules/
│   ├── amortization.js
│   ├── charts.js
│   ├── tables.js
│   ├── extras.js
│   ├── interactions.js
│   ├── metrics.js
│   ├── schedule-summary.js
│   └── ui.js
└── vendor/
    ├── chart.umd.min.js
    ├── chartjs-plugin-annotation.umd.min.js
    └── chartjs-plugin-datalabels.umd.min.js
docs/
```

## Docs

See `docs/` for architecture, verification, and implementation decisions.
