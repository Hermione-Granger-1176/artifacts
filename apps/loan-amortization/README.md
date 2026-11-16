# Loan amortization schedule

This interactive calculator shows the periodic payment, total interest, and payoff time for a loan. It compares the baseline schedule with a schedule that adds extra payments.

## Features

- A payment (EMI) as the main result, with a savings chip and four metrics: total interest, payoff time, total paid, and break-even.
- Yearly, half-yearly, quarterly, monthly, bi-weekly, and weekly payment frequencies.
- Five charts: balance, scenario comparison, interest savings, cumulative payments, and per-period payments.
- Per-period and yearly repayment tables. The app draws only the view that is on screen.
- Light and dark themes through the shared app shell.

## Use the app

- Set the loan amount, interest rate, and tenure with the sliders, or type a value into a field. A typed rate such as 6.1% keeps its precision, even though the rate slider moves in 0.25 steps. Typed values clamp to the slider range. An empty, zero, or non-numeric value reverts to the last valid value.
- Choose a payment frequency. Bi-weekly payments have a toggle between the True and Accelerated methods.
- Click **+ Add extra payment** to add a one-time or recurring extra payment. Each row shows a summary of its effect.
- Switch between **Charts** and **Schedule**. The schedule view shows the per-period or yearly table.

## Made with

- Claude
- Chart.js 4.4.1 (vendored)
- chartjs-plugin-annotation 3.0.1 (vendored)
- chartjs-plugin-datalabels 2.2.0 (vendored)

## Documentation

The app documentation covers [architecture](docs/architecture.md), [verification](docs/verification.md), and [implementation decisions](docs/decisions.md).
