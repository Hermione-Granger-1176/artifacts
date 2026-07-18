# Verification

## Core formulas

For a bond with face value `F`, annual coupon rate `c`, `k` coupon periods per year, and `n = years * k` periods, the per-period coupon is `C = F * c / k` and the per-period yield is `i = y / k` for an annual market rate `y`. The explainer always prices annual bonds (`k = 1`), but the math stays frequency-general.

- Price: `P = sum_{t=1..n} C / (1 + i)^t + F / (1 + i)^n`
- Regime: coupon above the market rate is a premium (price above face), coupon equal to the rate is par (price at face), coupon below the rate is a discount (price below face)
- Sensitivity: the percent price change from a one-point rate rise at maturity `m` is `bondPrice(m, y + 1) / bondPrice(m, y) - 1`, evaluated directly (no duration approximation)
- Price split: `PV(face) = F / (1 + i)^n` and `PV(coupons) = P - PV(face)`
- Current yield: annual coupon dollars over price, `(F * c) / P`
- Macaulay duration (years): `sum(t_years * PV_t) / P`
- Modified duration: `Macaulay / (1 + i)`
- Convexity: `sum(PV_t * t * (t + 1)) / (P * (1 + i)^2 * k^2)` with `t` the period index
- DV01: `modified duration * P * 0.0001`
- Yield curve: each preset blends a short-end rate toward a long-end rate, `y(m) = long + (short - long) * exp(-m / 8)` for maturity `m` in years; normal is 3% to 5.5%, flat is 4.5%, inverted is 5.5% to 3.5%

## Representative checks

All fixtures below assume a 10-year, 5% annual coupon, $1,000 face bond unless stated. The price and regime fixtures are encoded as assertions in `tests/js/apps/bond-price-vs-rate/bond-math.test.js`.

- Prices by market rate: 3% gives `1170.60`, 4% gives `1081.11`, 5% gives `1000.00`, 6% gives `926.40`, 7% gives `859.53`
- Zero-coupon 10-year $1,000: rate 3% gives `744.09`, rate 5% gives `613.91`, rate 7% gives `508.35`
- A par bond prices to exactly its face value when the market rate equals the coupon (5%)
- Cash-flow schedule (`bondSchedule`): the 10-year bond returns 10 rows, each paying the `$50` coupon except the final row, which merges the `$1,000` face into a `$1,050` payment; every discount factor is `1 / (1 + i)^t`, with the first-year 5% factor equal to `0.9524`; each present value is `amount * discountFactor`; and the present values sum to the bond price (asserted at both 5% and 6%)
- Regime: `priceRegime(6, 5)` is premium, `priceRegime(5, 5)` is par, `priceRegime(4, 5)` is discount
- Sensitivity at a 5% rate and 5% coupon (percent drop for a +1 point move): 2-year about `-1.83%`, 5-year about `-4.21%`, 10-year about `-7.36%`, 20-year about `-11.47%`, 30-year about `-13.76%`
- Analytics at a 6% rate (the discount fixture): price `926.40` splitting into coupons `368.00` plus face `558.39`, current yield `5.397%`, Macaulay `8.02` years, modified `7.57`, convexity `72.57`, DV01 `0.70`
- Closed-form anchors: a zero-coupon bond's Macaulay duration equals its maturity and its convexity is `n(n+1)/(1+y)^2`; a par bond's Macaulay duration is `(1+y)/y * (1 - (1+y)^-n)`
- Consistency anchors: DV01 matches the exact one-basis-point reprice to within `0.001`; modified duration matches a central-difference numeric derivative for a semiannual bond; duration plus the convexity term reproduces the exact one-point move to second order
- Yield-curve anchors: the normal preset rises with maturity and the inverted preset falls; the flat preset is constant at `4.5%`; the normal curve at 10 years is `4.7837%`; every preset stays inside the 1-12 slider range over 1-30 years (all asserted directly)

## Edge cases

- A market rate near `0%` must not divide by zero; discount factors approach 1 and the price approaches the undiscounted sum of the cash flows
- A 1-year bond has a single coupon-plus-face cash flow and prices to `(C + F) / (1 + i)` (asserted directly)
- A hair-thin coupon/rate difference is classified as par so slider rounding does not flicker the badge (asserted directly)

## Precision notes

- Prices are asserted to within `0.01`
- Core math stays in floating point; rounding happens only for presentation in the hero readout, the comparison bars, and the chart axes
