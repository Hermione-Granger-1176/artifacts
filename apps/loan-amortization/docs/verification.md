# Verification

## Core formula

The calculator uses the standard amortizing-payment formula for non-zero interest rates:

`EMI = P * r * (1 + r)^n / ((1 + r)^n - 1)`

Where:

- `P` = principal
- `r` = interest rate per payment period
- `n` = total number of payment periods

For zero-interest loans, payment falls back to `P / n`.

## Accelerated bi-weekly assumption

- Baseline bi-weekly mode recalculates EMI for `26` periods per year
- Accelerated bi-weekly mode uses `monthly EMI / 2` and applies that payment `26` times per year

## Representative checks

The regression scenarios have these expected results:

1. Principal `50000`, rate `5%`, tenure `7` years, monthly cadence, no extras
   - EMI is about `$706`
   - Total periods equal `84`
2. Same loan, add recurring extra payment `$500` every `1` month from month `1`
   - Total interest is lower than the baseline
   - The payoff period is shorter than the baseline
3. Same loan, switch to bi-weekly accelerated mode
   - The EMI display is half the equivalent monthly EMI
   - Payoff is earlier than in true bi-weekly mode
4. Principal `12000`, rate `0%`, tenure `1` year, monthly cadence, no extras
   - Payment equals `$1,000`
   - Break-even occurs in period `1`, the first period where cumulative principal meets or exceeds cumulative interest

## Edge cases

- At `0%` interest, the schedule pays down linearly without division by zero
- A high tenure (`30` years) renders charts and yearly summaries without runtime errors
- Extra payments above the remaining balance are capped at that balance
- Break-even is the first period where cumulative principal plus extras meets or exceeds cumulative interest

## Precision notes

- Chart values and displayed table amounts are rounded for readability
- Core schedule math stays in floating point and only rounds for presentation
