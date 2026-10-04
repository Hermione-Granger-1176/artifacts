# Loan Amortization Schedule

Interactive loan amortization calculator with charts, extra payment scenarios, and detailed repayment schedules.

## Highlights

- Baseline payoff vs extra-payment scenario comparison
- Yearly, half-yearly, quarterly, monthly, bi-weekly, and weekly cadences
- Two-column calculator: a sticky input column (loan, frequency, extra payments) beside the results, which stack above each other below 900px
- EMI as the hero number, with a savings chip and four supporting KPIs
- Five visual breakdowns stacked in one consistent chart-card style: balance, scenario comparison, interest savings, cumulative payments, and per-period payments
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
    ├── chartjs-plugin-annotation.min.js
    └── chartjs-plugin-datalabels.min.js
docs/
```

## Docs

See `docs/` for architecture, verification, and implementation decisions.
