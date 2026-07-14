/**
 * Pure bond pricing math. No DOM access.
 *
 * Conventions: a coupon frequency `k` sets the number of periods per year.
 * The per-period yield is `annualYieldPct / 100 / k`, the per-period coupon is
 * `faceValue * couponRatePct / 100 / k`, and the number of periods is
 * `years * k`. The explainer always prices annual bonds (`k = 1`), but the
 * math stays frequency-general so the fixtures can exercise both cases.
 *
 * @module bond-math
 */

/**
 * @typedef {{
 *   faceValue: number,
 *   couponRatePct: number,
 *   years: number,
 *   frequency: number
 * }} BondShape
 * @typedef {BondShape & { annualYieldPct: number }} PricedBond
 * @typedef {{ period: number, timeYears: number, amount: number }} CashFlow
 * @typedef {CashFlow & { discountFactor: number, presentValue: number }} DiscountedCashFlow
 * @typedef {"premium" | "par" | "discount"} PriceRegime
 */

/**
 * Build the undiscounted cash-flow schedule for a bond.
 * Each period pays the periodic coupon; the final period also returns face.
 *
 * @param {BondShape} bond - Bond terms.
 * @returns {CashFlow[]} One entry per coupon period.
 */
function buildCashFlows({ faceValue, couponRatePct, years, frequency }) {
  const periods = Math.round(years * frequency);
  const coupon = (faceValue * couponRatePct) / 100 / frequency;
  /** @type {CashFlow[]} */
  const flows = [];

  for (let period = 1; period <= periods; period += 1) {
    const isFinal = period === periods;
    flows.push({
      period,
      timeYears: period / frequency,
      amount: coupon + (isFinal ? faceValue : 0)
    });
  }

  return flows;
}

/**
 * Discount a cash-flow schedule at a given annual yield.
 *
 * @param {CashFlow[]} cashFlows - Undiscounted schedule.
 * @param {number} annualYieldPct - Market yield, as an annual percentage.
 * @param {number} frequency - Compounding periods per year.
 * @returns {DiscountedCashFlow[]} Schedule with discount factors and present values.
 */
function discountCashFlows(cashFlows, annualYieldPct, frequency) {
  const periodYield = annualYieldPct / 100 / frequency;
  return cashFlows.map((flow) => {
    const discountFactor = 1 / Math.pow(1 + periodYield, flow.period);
    return {
      ...flow,
      discountFactor,
      presentValue: flow.amount * discountFactor
    };
  });
}

/** @param {PricedBond} bond - Bond terms plus its market yield. */
function discountBond({ faceValue, couponRatePct, years, annualYieldPct, frequency }) {
  return discountCashFlows(
    buildCashFlows({ faceValue, couponRatePct, years, frequency }),
    annualYieldPct,
    frequency
  );
}

/**
 * Present value (clean price) of a bond.
 *
 * @param {PricedBond} bond - Bond terms plus its market yield.
 * @returns {number} Bond price.
 */
export function bondPrice(bond) {
  return discountBond(bond).reduce((sum, row) => sum + row.presentValue, 0);
}

/**
 * Discounted cash-flow schedule for a bond: one row per coupon period, each with
 * its undiscounted payment (the final period also returns face), the discount
 * factor `1 / (1 + i)^t`, and the present value. The present values sum to the
 * bond price, so the schedule is what the worked-example table and its fixtures
 * read from.
 *
 * @param {PricedBond} bond - Bond terms plus its market yield.
 * @returns {DiscountedCashFlow[]} The discounted schedule.
 */
export function bondSchedule(bond) {
  return discountBond(bond);
}

/**
 * @typedef {{
 *   price: number,
 *   pvCoupons: number,
 *   pvFace: number,
 *   currentYieldPct: number,
 *   macaulayYears: number,
 *   modifiedYears: number,
 *   convexity: number,
 *   dv01: number
 * }} BondAnalytics
 */

/**
 * Desk-style analytics for a bond: price decomposition, current yield,
 * Macaulay and modified duration, convexity, and DV01.
 *
 * Definitions (per-period yield `i`, `n` periods, `k` periods per year):
 * - Macaulay duration: PV-weighted average time to each cash flow, in years.
 * - Modified duration: Macaulay / (1 + i); the percent price drop per
 *   one-point annual rate rise.
 * - Convexity: sum(PV_t * t * (t + 1)) / (price * (1 + i)^2 * k^2), the
 *   curvature term in the price-rate relationship, in years squared.
 * - DV01: modified duration * price * 0.0001; the dollar move per one
 *   basis point.
 *
 * @param {PricedBond} bond - Bond terms plus its market yield.
 * @returns {BondAnalytics} The analytics bundle.
 */
export function bondAnalytics(bond) {
  const rows = discountBond(bond);
  const periodYield = bond.annualYieldPct / 100 / bond.frequency;
  const price = rows.reduce((sum, row) => sum + row.presentValue, 0);

  const pvFace = bond.faceValue / Math.pow(1 + periodYield, rows.length);
  const macaulayYears =
    rows.reduce((sum, row) => sum + row.timeYears * row.presentValue, 0) / price;
  const modifiedYears = macaulayYears / (1 + periodYield);
  const convexity =
    rows.reduce((sum, row) => sum + row.presentValue * row.period * (row.period + 1), 0) /
    (price * Math.pow(1 + periodYield, 2) * bond.frequency * bond.frequency);

  return {
    price,
    pvCoupons: price - pvFace,
    pvFace,
    currentYieldPct: ((bond.faceValue * bond.couponRatePct) / 100 / price) * 100,
    macaulayYears,
    modifiedYears,
    convexity,
    dv01: modifiedYears * price * 0.0001
  };
}

/**
 * @typedef {{ label: string, shortPct: number, longPct: number }} YieldCurveShape
 */

/**
 * The three teaching yield-curve shapes. Each is an exponential blend from a
 * short-end rate toward a long-end rate (see {@link curveYieldPct}).
 * @type {Record<"normal" | "flat" | "inverted", YieldCurveShape>}
 */
export const YIELD_CURVES = {
  normal: { label: "Normal", shortPct: 3, longPct: 5.5 },
  flat: { label: "Flat", shortPct: 4.5, longPct: 4.5 },
  inverted: { label: "Inverted", shortPct: 5.5, longPct: 3.5 }
};

/** Mean-reversion horizon (years) for the curve blend; ~63% of the short-to-long move happens by here. */
const CURVE_TAU_YEARS = 8;

/**
 * Annual yield offered by a curve shape at a given maturity:
 * `long + (short - long) * exp(-years / tau)`. Starts at the short rate and
 * decays smoothly toward the long rate, giving the standard concave shapes.
 *
 * @param {YieldCurveShape} curve - Short- and long-end rates.
 * @param {number} years - Maturity in years.
 * @returns {number} Annual yield at that maturity, as a percentage.
 */
export function curveYieldPct(curve, years) {
  return curve.longPct + (curve.shortPct - curve.longPct) * Math.exp(-years / CURVE_TAU_YEARS);
}

/**
 * Classify a bond as trading at a premium, at par, or at a discount.
 *
 * @param {number} couponRatePct - Coupon rate as an annual percentage.
 * @param {number} annualYieldPct - Market yield as an annual percentage.
 * @returns {PriceRegime} The price regime.
 */
export function priceRegime(couponRatePct, annualYieldPct) {
  const difference = couponRatePct - annualYieldPct;
  if (Math.abs(difference) < 1e-9) {
    return "par";
  }
  return difference > 0 ? "premium" : "discount";
}
