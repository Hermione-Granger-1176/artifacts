/**
 * Narrative rendering for the bonds vs interest rates explainer.
 *
 * Every DOM write here uses textContent or createElement, so no markup is ever
 * interpolated. The pure copy builders are exported separately so they can be
 * unit tested without a DOM.
 * @module narrative
 */

const REGIME_PRESENTATION = {
  premium: { label: "Premium", badgeClass: "is-green", rateArrow: "is-down", priceArrow: "is-up" },
  par: { label: "At par", badgeClass: "is-blue", rateArrow: "is-flat", priceArrow: "is-flat" },
  discount: { label: "Discount", badgeClass: "is-red", rateArrow: "is-up", priceArrow: "is-down" }
};

const ARROW_GLYPH = {
  "is-up": "▲",
  "is-down": "▼",
  "is-flat": "-"
};

/** The slider ceiling, used to scale the coupon-vs-market comparison bars. */
const RATE_SCALE_MAX = 12;

/**
 * @typedef {{
 *   faceValue: number,
 *   couponRatePct: number,
 *   years: number,
 *   annualYieldPct: number
 * }} NarrativeBond
 * @typedef {{
 *   bond: NarrativeBond,
 *   price: number,
 *   regime: import('./bond-math.js').PriceRegime,
 *   schedule: import('./bond-math.js').DiscountedCashFlow[],
 *   sensitivity: { currentPct: number, shortPct: number, longPct: number },
 *   analytics: import('./bond-math.js').BondAnalytics,
 *   curve: { key: string, label: string, atMaturityPct: number }
 * }} NarrativeState
 * @typedef {{
 *   formatCurrency: (value: number, digits?: number) => string,
 *   formatPercent: (value: number, digits?: number) => string
 * }} NarrativeFormatters
 */

/** Format a coupon or rate compactly, dropping a trailing ".0" (e.g. "5%", "5.4%"). */
function couponText(value) {
  return Number.isInteger(value) ? `${value}%` : `${value.toFixed(1)}%`;
}

/** Format a signed percentage move as a positive magnitude (e.g. "7.4%"). */
function magnitudeText(value) {
  return `${Math.abs(value).toFixed(1)}%`;
}

/**
 * Resolve the badge label and arrow directions for a price regime.
 * @param {import('./bond-math.js').PriceRegime} regime
 * @returns {{ label: string, badgeClass: string, rateArrow: string, priceArrow: string }}
 */
export function regimePresentation(regime) {
  return REGIME_PRESENTATION[regime];
}

/**
 * Build the plain-language hero explanation of the current price move.
 * @param {NarrativeState} state
 * @param {NarrativeFormatters} formatters
 * @returns {string}
 */
export function heroExplainText({ bond, price, regime }, { formatCurrency, formatPercent }) {
  const ratePct = formatPercent(bond.annualYieldPct);
  const couponPct = formatPercent(bond.couponRatePct);
  const priceText = formatCurrency(price, 2);
  const faceText = formatCurrency(bond.faceValue, 0);

  if (regime === "discount") {
    return (
      `Rates rose to ${ratePct}, above this bond's ${couponPct} coupon. A new buyer can ` +
      `earn ${ratePct} on a fresh bond, so they will only pay ${priceText} for your ` +
      `${couponPct} bond, a discount to its ${faceText} face value.`
    );
  }

  if (regime === "premium") {
    return (
      `Rates slipped to ${ratePct}, below this bond's ${couponPct} coupon. Your ${couponPct} ` +
      `payments now beat the market, so buyers will pay ${priceText}, a premium over the ` +
      `${faceText} face value.`
    );
  }

  return (
    `The market rate matches this bond's ${couponPct} coupon, so it changes hands right at ` +
    `its ${faceText} face value.`
  );
}

/**
 * Build the mechanism explanation tying coupon and market rate to the price move.
 * @param {NarrativeState} state
 * @param {NarrativeFormatters} formatters
 * @returns {string}
 */
export function mechanismExplainText({ bond, regime }, { formatPercent }) {
  const ratePct = formatPercent(bond.annualYieldPct);
  const couponPct = formatPercent(bond.couponRatePct);

  if (regime === "discount") {
    return (
      `Your coupon (${couponPct}) sits below the market (${ratePct}), so the price must fall ` +
      `until a new buyer's total return matches that ${ratePct}.`
    );
  }

  if (regime === "premium") {
    return (
      `Your coupon (${couponPct}) sits above the market (${ratePct}), so buyers bid the price ` +
      `up above face value.`
    );
  }

  return (
    `Your coupon (${couponPct}) equals the market (${ratePct}), so there is nothing to ` +
    `discount or pay up for.`
  );
}

/**
 * Build the mathematics explanation: how each coupon and the face repayment is
 * discounted and summed into the price, and why a higher rate lowers the price.
 * @param {NarrativeState} state
 * @param {NarrativeFormatters} formatters
 * @returns {string}
 */
export function mathExplainText({ bond, schedule, price }, { formatCurrency, formatPercent }) {
  const ratePct = formatPercent(bond.annualYieldPct);
  const couponDollarsText = formatCurrency((bond.faceValue * bond.couponRatePct) / 100, 0);
  const faceText = formatCurrency(bond.faceValue, 0);
  const finalFactor = schedule[schedule.length - 1].discountFactor;
  const pvFaceText = formatCurrency(bond.faceValue * finalFactor, 2);
  const priceText = formatCurrency(price, 2);

  return (
    `At a ${ratePct} market rate, each of the ${bond.years} ${couponDollarsText} coupon payments is ` +
    `divided by (1 + r) raised to its year, so a payment shrinks more the further out it sits. ` +
    `The ${faceText} face repayment in year ${bond.years} is worth ${pvFaceText} today, and adding ` +
    `every discounted coupon to that repayment gives the ${priceText} price. Raise the rate and ` +
    `every discount factor gets smaller, which is exactly why a higher rate drags the price down.`
  );
}

/**
 * Write the live legend values beside the pricing formula (coupon dollars,
 * market rate, years to maturity, and face value).
 * @param {Record<string, HTMLElement>} elements
 * @param {NarrativeState} state
 * @param {NarrativeFormatters} formatters
 * @returns {void}
 */
export function renderMathLegend(elements, { bond }, { formatCurrency, formatPercent }) {
  elements.mathLegendCoupon.textContent = formatCurrency((bond.faceValue * bond.couponRatePct) / 100, 0);
  elements.mathLegendRate.textContent = formatPercent(bond.annualYieldPct);
  elements.mathLegendYears.textContent = String(bond.years);
  elements.mathLegendFace.textContent = formatCurrency(bond.faceValue, 0);
}

/**
 * Build one cash-flow table row: year, payment, discount factor, and present value.
 * The final period merges the face repayment into the payment and flags it.
 * @param {import('./bond-math.js').DiscountedCashFlow} flow
 * @param {boolean} isFinal
 * @param {number} faceValue
 * @param {Pick<NarrativeFormatters, 'formatCurrency'>} formatters
 * @returns {HTMLElement}
 */
function buildScheduleRow({ timeYears, amount, discountFactor, presentValue }, isFinal, faceValue, { formatCurrency }) {
  const row = document.createElement("tr");
  row.className = "br-schedule-row";

  const year = document.createElement("td");
  year.textContent = String(timeYears);

  const payment = document.createElement("td");
  if (isFinal) {
    const paymentAmount = document.createElement("span");
    paymentAmount.textContent = formatCurrency(amount, 2);
    const faceNote = document.createElement("span");
    faceNote.className = "br-face-note";
    faceNote.textContent = `incl. ${formatCurrency(faceValue, 0)} face`;
    payment.append(paymentAmount, faceNote);
  } else {
    payment.textContent = formatCurrency(amount, 2);
  }

  const factor = document.createElement("td");
  factor.textContent = discountFactor.toFixed(4);

  const value = document.createElement("td");
  value.textContent = formatCurrency(presentValue, 2);

  row.append(year, payment, factor, value);
  return row;
}

/**
 * Render the live worked cash-flow table: one row per coupon period plus a final
 * total row whose value is the bond price (the sum of the present values).
 * @param {HTMLElement} tbody
 * @param {NarrativeState} state
 * @param {NarrativeFormatters} formatters
 * @returns {void}
 */
export function renderScheduleTable(tbody, { bond, schedule, price }, { formatCurrency }) {
  tbody.textContent = "";
  const lastIndex = schedule.length - 1;
  schedule.forEach((flow, index) => {
    tbody.appendChild(buildScheduleRow(flow, index === lastIndex, bond.faceValue, { formatCurrency }));
  });

  const totalRow = document.createElement("tr");
  totalRow.className = "br-schedule-total";
  const label = document.createElement("td");
  label.textContent = "Total (bond price)";
  label.setAttribute("colspan", "3");
  const total = document.createElement("td");
  total.textContent = formatCurrency(price, 2);
  totalRow.append(label, total);
  tbody.appendChild(totalRow);
}

/**
 * Build the sensitivity explanation comparing the current maturity with a 2- and 30-year bond.
 * @param {NarrativeState} state
 * @param {NarrativeFormatters} formatters
 * @returns {string}
 */
export function sensitivityExplainText({ bond, sensitivity }, { formatPercent }) {
  const ratePct = formatPercent(bond.annualYieldPct);
  return (
    `At today's ${ratePct} rate, a one-point rise would shave about ` +
    `${magnitudeText(sensitivity.currentPct)} off your ${bond.years}-year bond, versus ` +
    `roughly ${magnitudeText(sensitivity.shortPct)} for a 2-year and ` +
    `${magnitudeText(sensitivity.longPct)} for a 30-year.`
  );
}

const CURVE_STORY = {
  normal:
    "A normal curve slopes up: lenders demand extra yield to lock their money away longer, " +
    "and the market expects steady conditions ahead.",
  flat:
    "A flat curve pays nothing extra for waiting. Curves usually flatten in transition, " +
    "when the market is deciding whether rates go up or come down next.",
  inverted:
    "An inverted curve pays less on long bonds than short ones. The market is betting on " +
    "rate cuts ahead, which is why inversion is finance's most famous recession warning."
};

/**
 * Build the yield-curve explanation: what the selected shape signals, plus the
 * rate this curve offers at the bond's maturity versus the rate set at the top.
 * @param {NarrativeState} state
 * @param {NarrativeFormatters} formatters
 * @returns {string}
 */
export function curveExplainText({ bond, curve }, { formatPercent }) {
  return (
    `${CURVE_STORY[curve.key]} At your ${bond.years}-year maturity this ` +
    `${curve.label.toLowerCase()} curve offers about ${formatPercent(curve.atMaturityPct)}, ` +
    `versus the ${formatPercent(bond.annualYieldPct)} market rate set at the top.`
  );
}

/**
 * Build the ripple explanation keyed to whether rates sit above, below, or at the coupon.
 * @param {NarrativeState} state
 * @returns {string}
 */
export function rippleExplainText({ regime }) {
  if (regime === "discount") {
    return (
      "With the market rate above this bond's coupon, every older, lower-coupon bond loses " +
      "value, brand-new bonds are issued at these higher, more attractive coupons, and the " +
      "same climb in yields pushes up borrowing costs across mortgages, companies, and " +
      "governments."
    );
  }

  if (regime === "premium") {
    return (
      "With the market rate below this bond's coupon, older high-coupon bonds gain value, " +
      "brand-new bonds are issued at these lower coupons, and the same drop in yields eases " +
      "borrowing costs across mortgages, companies, and governments."
    );
  }

  return (
    "With the market rate level with this bond's coupon, older bonds hold their value, new " +
    "bonds are issued at matching coupons, and borrowing costs across the economy sit right " +
    "where the market expects."
  );
}

/**
 * Build one labelled comparison row (label, proportional bar, value) as a DOM
 * node. The bar uses the shared .meter / .meter-fill component; `fillTone` is an
 * optional meter tone modifier (e.g. "is-amber") or "" for the default blue.
 */
function buildCompareRow(label, widthPct, fillTone, valueText) {
  const row = document.createElement("div");
  row.className = "br-compare-row";

  const name = document.createElement("span");
  name.className = "br-compare-label";
  name.textContent = label;

  const track = document.createElement("div");
  track.className = "meter";
  const fill = document.createElement("div");
  fill.className = fillTone ? `meter-fill ${fillTone}` : "meter-fill";
  fill.style.width = `${Math.max(0, Math.min(100, widthPct))}%`;
  track.appendChild(fill);

  const num = document.createElement("span");
  num.className = "br-compare-num";
  num.textContent = valueText;

  row.append(name, track, num);
  return row;
}

/**
 * Render the coupon-vs-market comparison bars.
 * @param {HTMLElement} container
 * @param {NarrativeState} state
 * @param {NarrativeFormatters} formatters
 * @returns {void}
 */
export function renderCouponCompare(container, { bond }, { formatPercent }) {
  container.textContent = "";
  container.appendChild(
    buildCompareRow(
      "This bond",
      (bond.couponRatePct / RATE_SCALE_MAX) * 100,
      "",
      formatPercent(bond.couponRatePct)
    )
  );
  container.appendChild(
    buildCompareRow(
      "Market",
      (bond.annualYieldPct / RATE_SCALE_MAX) * 100,
      "is-amber",
      formatPercent(bond.annualYieldPct)
    )
  );
}

/**
 * Render the present-value decomposition bars: coupons vs the face repayment.
 * Each bar's width is that piece's share of today's price.
 * @param {HTMLElement} container
 * @param {NarrativeState} state
 * @param {NarrativeFormatters} formatters
 * @returns {void}
 */
export function renderPriceSplit(container, { analytics }, { formatCurrency }) {
  container.textContent = "";
  container.appendChild(
    buildCompareRow(
      "Coupons",
      (analytics.pvCoupons / analytics.price) * 100,
      "",
      formatCurrency(analytics.pvCoupons, 0)
    )
  );
  container.appendChild(
    buildCompareRow(
      "Face value",
      (analytics.pvFace / analytics.price) * 100,
      "is-amber",
      formatCurrency(analytics.pvFace, 0)
    )
  );
}

/**
 * Build the analyst paragraph: the duration estimate against the exact
 * reprice, the convexity cushion, and the DV01 in desk terms.
 * @param {NarrativeState} state
 * @param {NarrativeFormatters} formatters
 * @returns {string}
 */
export function analystExplainText({ bond, analytics, sensitivity }, { formatCurrency, formatPercent }) {
  const durationEstimate = formatPercent(analytics.modifiedYears);
  const exact = magnitudeText(sensitivity.currentPct);
  const convexityText = analytics.convexity.toFixed(1);
  const dv01Text = formatCurrency(analytics.dv01, 2);

  return (
    `Modified duration says a one-point rate rise should cost about ${durationEstimate}; the ` +
    `exact reprice is ${exact}. The shortfall is convexity (${convexityText}) working in your ` +
    `favor: the price-rate curve flattens as rates climb, so losses undershoot the straight-line ` +
    `estimate. On a desk this bond would be quoted as roughly ${dv01Text} of price move per ` +
    `basis point (its DV01) on every $1,000 of face value, and a buyer at today's price earns a ` +
    `${formatPercent(analytics.currentYieldPct, 2)} current yield on the ${formatPercent(bond.couponRatePct)} coupon.`
  );
}

/**
 * Render the four analyst stat tiles.
 * @param {Record<string, HTMLElement>} elements
 * @param {NarrativeState} state
 * @param {NarrativeFormatters} formatters
 * @returns {void}
 */
export function renderAnalytics(elements, { analytics }, { formatPercent }) {
  elements.statCurrentYield.textContent = formatPercent(analytics.currentYieldPct, 2);
  elements.statMacaulay.textContent = `${analytics.macaulayYears.toFixed(1)} yrs`;
  elements.statModified.textContent = analytics.modifiedYears.toFixed(1);
  elements.statConvexity.textContent = analytics.convexity.toFixed(1);
}

/**
 * Render every narrative readout for the current bond state.
 * @param {Record<string, HTMLElement>} elements
 * @param {NarrativeState} state
 * @param {NarrativeFormatters} formatters
 * @returns {void}
 */
export function renderNarrative(elements, state, formatters) {
  const { bond, price, regime } = state;
  const presentation = regimePresentation(regime);
  const couponLabel = couponText(bond.couponRatePct);

  elements.priceValue.textContent = formatters.formatCurrency(price, 2);
  elements.priceCaption.textContent = `This ${bond.years}-year, ${couponLabel} bond is now worth`;

  elements.regimeBadge.textContent = presentation.label;
  elements.regimeBadge.className = `chip ${presentation.badgeClass}`;

  elements.rateArrow.textContent = ARROW_GLYPH[presentation.rateArrow];
  elements.rateArrow.className = `br-arrow ${presentation.rateArrow}`;
  elements.priceArrow.textContent = ARROW_GLYPH[presentation.priceArrow];
  elements.priceArrow.className = `br-arrow ${presentation.priceArrow}`;

  elements.heroExplain.textContent = heroExplainText(state, formatters);
  elements.mechanismExplain.textContent = mechanismExplainText(state, formatters);
  elements.mathExplain.textContent = mathExplainText(state, formatters);
  elements.sensitivityExplain.textContent = sensitivityExplainText(state, formatters);
  elements.analystExplain.textContent = analystExplainText(state, formatters);
  elements.curveExplain.textContent = curveExplainText(state, formatters);
  elements.btnApplyCurve.textContent =
    `Set the market rate to ${formatters.formatPercent(state.curve.atMaturityPct)}`;
  elements.rippleExplain.textContent = rippleExplainText(state);

  renderCouponCompare(elements.couponCompare, state, formatters);
  renderMathLegend(elements, state, formatters);
  renderScheduleTable(elements.mathSchedule, state, formatters);
  renderPriceSplit(elements.pvSplit, state, formatters);
  renderAnalytics(elements, state, formatters);
}
