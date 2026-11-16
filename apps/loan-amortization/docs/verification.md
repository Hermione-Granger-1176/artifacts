# Verification

This page lists the payment formula, the expected results of the regression scenarios, and the commands that run the checks.

## Core formula

The calculator uses the standard amortizing-payment formula for non-zero interest rates:

`EMI = P * r * (1 + r)^n / ((1 + r)^n - 1)`

- `P` is the principal.
- `r` is the interest rate per payment period.
- `n` is the total number of payment periods.

At zero interest, the payment is `P / n`.

## Accelerated bi-weekly assumption

- Baseline bi-weekly recalculates the EMI for `26` periods per year.
- Accelerated bi-weekly computes the monthly EMI, halves it, and applies that payment `26` times a year. That equals 13 monthly payments a year (`getBiweeklyEmiOverride`).

## Representative checks

1. Principal `50000`, rate `5%`, tenure `7` years, monthly cadence, no extras
   - The EMI is about `$706.70`.
   - Total periods equal `84`.
2. The same loan with a recurring extra payment of `$500` every `1` month from month `1`
   - Total interest is lower than the baseline.
   - The payoff period is shorter than the baseline.
3. The same loan in bi-weekly accelerated mode
   - The EMI display is half the equivalent monthly EMI.
   - Payoff comes earlier than in true bi-weekly mode.
4. Principal `12000`, rate `0%`, tenure `1` year, monthly cadence, no extras
   - The payment is `$1,000`.
   - Break-even falls in period `1`.

To re-check a scenario, call `calcEmi` or `runSchedule` from `js/modules/amortization.js` with its inputs. The Node tests in `modules.test.js` cover the same functions.

## Edge cases

- At `0%` interest, the schedule pays down linearly without division by zero.
- A 30-year tenure renders charts and yearly summaries without runtime errors.
- Extra payments above the remaining balance are capped at that balance.
- A negative extra amount, or one that is not finite (such as `1e400`), is ignored, and the last valid amount stays. An amount above `$500,000` clamps to `$500,000`, the top of the loan-amount slider.
- Break-even is the first period where cumulative principal plus extras meets or exceeds cumulative interest.
- The schedule stops when the balance falls below `$0.01`, and the remainder is set to zero. It also stops after `2000` periods, whichever comes first. The longest loan the inputs allow is 30 years weekly, or `1560` periods.

## Precision notes

- Each chart series is whole dollars. Each per-period part and each cumulative total rounds on its own, so a sum of rounded parts can differ from a rounded total.
- Displayed table amounts are rounded for readability.
- Core schedule math stays in floating point and rounds only for presentation.

## Automated tests

- `tests/js/apps/loan-amortization/modules.test.js`: the calculation functions, the schedule, break-even, extra-payment capping, and currency formatting.
- `tests/js/apps/loan-amortization/app.test.js`: the visible-table rule, extra-field typing, and calculation with a typed rate.
- `tests/js/apps/loan-amortization/dom.test.js`: DOM helpers, table rendering, event binding, and chart redraw timing.

## Re-check

- Node tests: `make test-js`. Coverage thresholds: `make coverage-js`.
- Browser flows (theme and schedule switching, the savings chip, the tablet breakpoint): `make test-browser-apps-flows ARGS="-k loan_amortization"`.

Browser targets need Chromium. Run `make setup-playwright` once.
