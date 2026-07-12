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

Use these as smoke-verification scenarios after refactors:

1. Principal `50000`, rate `5%`, tenure `7` years, monthly cadence, no extras
   - EMI should remain about `$706`
   - Total periods should remain `84`
2. Same loan, add recurring extra payment `$500` every `1` month from month `1`
   - Total interest should drop materially versus baseline
   - Payoff period should shorten materially versus baseline
3. Same loan, switch to bi-weekly accelerated mode
   - EMI display should halve the equivalent monthly EMI
   - Payoff should shorten versus true bi-weekly mode

## Edge cases

- `0%` interest should not divide by zero and should pay down linearly
- High tenure (`30` years) should still render charts and yearly summaries without runtime errors
- Extra payments larger than the remaining balance should clamp to the outstanding balance
- Break-even should be the first period where cumulative principal plus extras exceeds cumulative interest

## Precision notes

- Chart values and displayed table amounts are rounded for readability
- Core schedule math stays in floating point and only rounds for presentation
