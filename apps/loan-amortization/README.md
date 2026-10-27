# Loan amortization schedule

Interactive loan amortization calculator with charts, extra payment scenarios, and detailed repayment schedules.

## Features

The calculator includes these views and controls:

- Baseline payoff vs extra-payment scenario comparison
- Yearly, half-yearly, quarterly, monthly, bi-weekly, and weekly cadences
- Two-column calculator: a sticky input column (loan, frequency, extra payments) beside the results. Below 900px the inputs stack above the results
- The periodic payment (EMI) as the main result, with a savings chip and four supporting metrics (total interest, payoff time, total paid, break-even)
- Five charts in one chart-card style: balance, scenario comparison, interest savings, cumulative payments, and per-period payments
- Per-period and yearly repayment tables, drawn only while visible
- Light and dark theme persistence through the shared app shell

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

## Documentation

The app documentation covers [architecture](docs/architecture.md), [verification](docs/verification.md), and [implementation decisions](docs/decisions.md).
