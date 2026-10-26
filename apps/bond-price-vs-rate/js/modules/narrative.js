/**
 * Narrative rendering for the bonds vs interest rates explainer.
 *
 * Every DOM write here uses textContent or createElement, so no markup is ever
 * interpolated. The pure copy builders are exported separately so they can be
 * unit tested without a DOM.
 * @module narrative
 */

import { setText } from "../../../../js/modules/dom-sync.js";
import { setMeterValue } from "../../../../js/modules/meter.js";

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

/** Price regimes in the order their stacked variants are created. */
const REGIMES = /** @type {const} */ (["premium", "par", "discount"]);

/**
 * @typedef {{ real: Map<string, HTMLElement>, ghost: Map<string, HTMLElement> }} StackNodes
 */

/** Variant and sizing elements per stacked container, keyed by variant name. */
const stackNodes = /** @type {WeakMap<HTMLElement, StackNodes>} */ (new WeakMap());

/**
 * Find a stacked container's elements, adopting any that the markup already
 * carries (`data-variant` for copy, `data-ghost` for sizing text), so the first
 * paint can hold the default copy.
 * @param {HTMLElement} container - Stacked container.
 * @returns {StackNodes} Its variant and sizing elements.
 */
function stackOf(container) {
  let nodes = stackNodes.get(container);
  if (!nodes) {
    nodes = { real: new Map(), ghost: new Map() };
    for (const child of Array.from(container.children ?? [])) {
      const variant = child.getAttribute("data-variant");
      const ghost = child.getAttribute("data-ghost");
      if (variant) {
        nodes.real.set(variant, /** @type {HTMLElement} */ (child));
      } else if (ghost) {
        nodes.ghost.set(ghost, /** @type {HTMLElement} */ (child));
      }
    }
    stackNodes.set(container, nodes);
  }
  return nodes;
}

/**
 * Find or create one element of a stack.
 * @param {HTMLElement} container - Stacked container.
 * @param {Map<string, HTMLElement>} map - The container's elements of this kind.
 * @param {string} key - Variant key.
 * @param {"variant" | "ghost"} kind - Which kind of element.
 * @returns {HTMLElement} The element.
 */
function stackNode(container, map, key, kind) {
  let node = map.get(key);
  if (!node) {
    node = document.createElement("span");
    node.className = kind === "ghost" ? "reserve-ghost" : "br-variant";
    node.setAttribute(`data-${kind}`, key);
    if (kind === "ghost") {
      node.setAttribute("aria-hidden", "true");
    }
    container.appendChild(node);
    map.set(key, node);
  }
  return node;
}

/**
 * Fill a stacked container: every variant shares one grid cell, so the tallest
 * copy sets the height and swapping the active variant never moves what sits
 * below. Inactive variants are visibility:hidden, so they are never read,
 * found, or selected; they only reserve space.
 *
 * With `sizing` copy, only the active variant carries real text. The sizing
 * copy is the same wording with the widest numbers any slider setting can print,
 * so the box is as tall as the longest possible text at this width and does not
 * change height when digits change where a line wraps.
 * @param {HTMLElement} container - Stacked container.
 * @param {Record<string, string>} texts - Copy by variant key.
 * @param {string} activeKey - The variant to show.
 * @param {Record<string, string>} [sizing] - Widest-number copy by variant key.
 * @returns {void}
 */
function renderVariants(container, texts, activeKey, sizing) {
  const nodes = stackOf(container);
  for (const [key, text] of Object.entries(texts)) {
    const node = stackNode(container, nodes.real, key, "variant");
    const active = key === activeKey;
    setText(node, active || !sizing ? text : "");
    node.classList.toggle("is-active", active);
  }
  for (const [key, text] of Object.entries(sizing ?? {})) {
    setText(stackNode(container, nodes.ghost, key, "ghost"), text);
  }
}

/**
 * Build the copy for every regime from one text builder.
 * @param {NarrativeState} state - Current state.
 * @param {(state: NarrativeState, formatters: NarrativeFormatters) => string} build - Copy builder.
 * @param {NarrativeFormatters} formatters - Formatters.
 * @returns {Record<string, string>} Copy by regime.
 */
function regimeTexts(state, build, formatters) {
  return Object.fromEntries(REGIMES.map((regime) => [regime, build({ ...state, regime }, formatters)]));
}

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
 *   curve: { key: string, label: string, atMaturityPct: number, shapes?: Record<string, { label: string, atMaturityPct: number }> }
 * }} NarrativeState
 * @typedef {{
 *   formatCurrency: (value: number, digits?: number) => string,
 *   formatPercent: (value: number, digits?: number) => string
 * }} NarrativeFormatters
 */

/**
 * Format a coupon or rate compactly, dropping a trailing ".0".
 * @param {number} value - Rate value.
 * @returns {string} Formatted rate.
 */
function couponText(value) {
  return Number.isInteger(value) ? `${value}%` : `${value.toFixed(1)}%`;
}

/**
 * Format a signed percentage move as a positive magnitude.
 * @param {number} value - Signed percentage.
 * @returns {string} Magnitude text.
 */
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
  setText(elements.mathLegendCoupon, formatCurrency((bond.faceValue * bond.couponRatePct) / 100, 0));
  setText(elements.mathLegendRate, formatPercent(bond.annualYieldPct));
  setText(elements.mathLegendYears, String(bond.years));
  setText(elements.mathLegendFace, formatCurrency(bond.faceValue, 0));
}

/**
 * @typedef {{
 *   row: HTMLElement,
 *   year: HTMLElement,
 *   payment: HTMLElement,
 *   faceNote: HTMLElement,
 *   factor: HTMLElement,
 *   value: HTMLElement
 * }} ScheduleRow
 * @typedef {{ rows: ScheduleRow[], total: HTMLElement, totalValue: HTMLElement }} ScheduleTable
 */

/**
 * Build one empty cash-flow table row. Every row has the same cells, so a row
 * can become the final one (or stop being it) without being rebuilt: the final
 * payment cell is one amount plus a face note, and the note is empty elsewhere.
 * @returns {ScheduleRow}
 */
function buildScheduleRow() {
  const row = document.createElement("tr");
  row.className = "br-schedule-row";

  const year = document.createElement("td");
  const payment = document.createElement("td");
  const paymentAmount = document.createElement("span");
  const faceNote = document.createElement("span");
  faceNote.className = "br-face-note";
  payment.append(paymentAmount, faceNote);
  const factor = document.createElement("td");
  const value = document.createElement("td");

  row.append(year, payment, factor, value);
  return { row, year, payment: paymentAmount, faceNote, factor, value };
}

/**
 * Build the total row and its price cell.
 * @returns {{ total: HTMLElement, totalValue: HTMLElement }}
 */
function buildTotalRow() {
  const total = document.createElement("tr");
  total.className = "br-schedule-total";
  const label = document.createElement("td");
  label.textContent = "Total (bond price)";
  label.setAttribute("colspan", "3");
  const totalValue = document.createElement("td");
  total.append(label, totalValue);
  return { total, totalValue };
}

/** Schedule state per table body: the rows and total row kept between renders. */
const scheduleTables = /** @type {WeakMap<HTMLElement, ScheduleTable>} */ (new WeakMap());

/**
 * Render the live worked cash-flow table: one row per coupon period plus a final
 * total row whose value is the bond price (the sum of the present values). The
 * rows are kept between renders and their cells updated in place; rows are added
 * or removed only when the number of periods changes, so a rate or coupon tick
 * touches no structure.
 * @param {HTMLElement} tbody
 * @param {NarrativeState} state
 * @param {NarrativeFormatters} formatters
 * @returns {void}
 */
export function renderScheduleTable(tbody, { bond, schedule, price }, { formatCurrency }) {
  let table = scheduleTables.get(tbody);
  if (!table) {
    tbody.textContent = "";
    table = { rows: [], ...buildTotalRow() };
    tbody.appendChild(table.total);
    scheduleTables.set(tbody, table);
  }

  while (table.rows.length > schedule.length) {
    /** @type {ScheduleRow} */ (table.rows.pop()).row.remove();
  }
  const added = [];
  while (table.rows.length < schedule.length) {
    const row = buildScheduleRow();
    table.rows.push(row);
    added.push(row.row);
  }
  if (added.length > 0) {
    // Appending the total row again moves it behind the new rows.
    tbody.append(...added, table.total);
  }

  const lastIndex = schedule.length - 1;
  schedule.forEach(({ timeYears, amount, discountFactor, presentValue }, index) => {
    const cells = table.rows[index];
    setText(cells.year, String(timeYears));
    setText(cells.payment, formatCurrency(amount, 2));
    setText(cells.faceNote, index === lastIndex ? `incl. ${formatCurrency(bond.faceValue, 0)} face` : "");
    setText(cells.factor, discountFactor.toFixed(4));
    setText(cells.value, formatCurrency(presentValue, 2));
  });
  setText(table.totalValue, formatCurrency(price, 2));
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
 * rate this curve offers at the bond's maturity versus the rate set on the left.
 * @param {NarrativeState} state
 * @param {NarrativeFormatters} formatters
 * @returns {string}
 */
export function curveExplainText({ bond, curve }, { formatPercent }) {
  return (
    `${CURVE_STORY[/** @type {keyof typeof CURVE_STORY} */ (curve.key)]} At your ${bond.years}-year maturity this ` +
    `${curve.label.toLowerCase()} curve offers about ${formatPercent(curve.atMaturityPct)}, ` +
    `versus the ${formatPercent(bond.annualYieldPct)} market rate set on the left.`
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
 * @typedef {{ label: string, widthPct: number, tone: string, valueText: string }} CompareRow
 * @typedef {{ name: HTMLElement, fill: HTMLElement, num: HTMLElement }} CompareRowParts
 */

/**
 * Build one labelled comparison row (label, proportional bar, value) as a DOM
 * node. The bar uses the shared .meter / .meter-fill component; `tone` is an
 * optional meter tone modifier (e.g. "is-amber") or "" for the default blue.
 * @param {string} tone - Optional meter tone modifier.
 * @returns {{ row: HTMLElement, parts: CompareRowParts }} The row and its writable parts.
 */
function buildCompareRow(tone) {
  const row = document.createElement("div");
  row.className = "br-compare-row";

  const name = document.createElement("span");
  name.className = "br-compare-label";

  const track = document.createElement("div");
  track.className = "meter";
  const fill = document.createElement("div");
  fill.className = tone ? `meter-fill ${tone}` : "meter-fill";
  track.appendChild(fill);

  const num = document.createElement("span");
  num.className = "br-compare-num";

  row.append(name, track, num);
  return { row, parts: { name, fill, num } };
}

/** Comparison row parts per container, kept between renders. */
const compareTables = /** @type {WeakMap<HTMLElement, CompareRowParts[]>} */ (new WeakMap());

/**
 * Find the parts of a comparison row that is already in the markup.
 * @param {Element} row - Row element.
 * @returns {CompareRowParts} Its label, fill, and value elements.
 */
function adoptCompareRow(row) {
  return {
    name: /** @type {HTMLElement} */ (row.children[0]),
    fill: /** @type {HTMLElement} */ (row.children[1].children[0]),
    num: /** @type {HTMLElement} */ (row.children[2])
  };
}

/**
 * Write comparison rows into a container. The rows are created (or adopted from
 * the markup) once and reused after, so a changed value rescales the bar and
 * the shared meter transition animates it instead of replacing the node.
 * @param {HTMLElement} container - Comparison container.
 * @param {CompareRow[]} rows - Rows to show.
 * @returns {void}
 */
function renderCompareRows(container, rows) {
  let parts = compareTables.get(container);
  if (!parts) {
    const existing = Array.from(container.children ?? []);
    if (existing.length === rows.length) {
      parts = existing.map(adoptCompareRow);
    } else {
      container.textContent = "";
      const built = rows.map(({ tone }) => buildCompareRow(tone));
      container.append(...built.map(({ row }) => row));
      parts = built.map(({ parts: rowParts }) => rowParts);
    }
    compareTables.set(container, parts);
  }

  rows.forEach(({ label, widthPct, valueText }, index) => {
    const { name, fill, num } = parts[index];
    setText(name, label);
    setMeterValue(fill, widthPct / 100);
    setText(num, valueText);
  });
}

/**
 * Render the coupon-vs-market comparison bars.
 * @param {HTMLElement} container
 * @param {NarrativeState} state
 * @param {NarrativeFormatters} formatters
 * @returns {void}
 */
export function renderCouponCompare(container, { bond }, { formatPercent }) {
  renderCompareRows(container, [
    {
      label: "This bond",
      widthPct: (bond.couponRatePct / RATE_SCALE_MAX) * 100,
      tone: "",
      valueText: formatPercent(bond.couponRatePct)
    },
    {
      label: "Market",
      widthPct: (bond.annualYieldPct / RATE_SCALE_MAX) * 100,
      tone: "is-amber",
      valueText: formatPercent(bond.annualYieldPct)
    }
  ]);
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
  renderCompareRows(container, [
    {
      label: "Coupons",
      widthPct: (analytics.pvCoupons / analytics.price) * 100,
      tone: "",
      valueText: formatCurrency(analytics.pvCoupons, 0)
    },
    {
      label: "Face value",
      widthPct: (analytics.pvFace / analytics.price) * 100,
      tone: "is-amber",
      valueText: formatCurrency(analytics.pvFace, 0)
    }
  ]);
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
  setText(elements.statCurrentYield, formatPercent(analytics.currentYieldPct, 2));
  setText(elements.statMacaulay, `${analytics.macaulayYears.toFixed(1)} yrs`);
  setText(elements.statModified, analytics.modifiedYears.toFixed(1));
  setText(elements.statConvexity, analytics.convexity.toFixed(1));
}

/**
 * The longest numbers any slider setting can print (found by scanning every
 * coupon, rate, and maturity): twelve percent rates, a thirty-year maturity, a
 * price of nine characters, and the widest duration, convexity, and sensitivity
 * readings. Only the copy built from it is used, never shown, to size the
 * callouts.
 * @type {NarrativeState}
 */
const WIDEST_STATE = {
  bond: { faceValue: 1000, couponRatePct: 12, years: 30, annualYieldPct: 12 },
  price: 3838.12,
  regime: "par",
  schedule: [
    { period: 30, timeYears: 30, amount: 1120, discountFactor: 0.9901, presentValue: 1108.8 }
  ],
  sensitivity: { currentPct: -22.4, shortPct: -22.4, longPct: -22.4 },
  analytics: {
    price: 3838.12,
    pvCoupons: 2838.22,
    pvFace: 999.9,
    currentYieldPct: 10.09,
    macaulayYears: 29.9,
    modifiedYears: 29.9,
    convexity: 888.8,
    dv01: 7.77
  },
  curve: {
    key: "normal",
    label: "Normal",
    atMaturityPct: 5.4,
    shapes: {
      normal: { label: "Normal", atMaturityPct: 5.4 },
      flat: { label: "Flat", atMaturityPct: 5.4 },
      inverted: { label: "Inverted", atMaturityPct: 5.4 }
    }
  }
};

/** Sizing copy for the formatters it was built with. */
let sizingCache = /** @type {{ formatters: NarrativeFormatters, copy: Record<string, Record<string, string>> } | null} */ (
  null
);

/**
 * Build the widest-number copy for every dynamic callout, by variant key. It
 * never changes, so it is built once per set of formatters.
 * @param {NarrativeFormatters} formatters - Formatters.
 * @returns {Record<string, Record<string, string>>} Sizing copy by callout id, then variant key.
 */
export function sizingCopy(formatters) {
  if (
    sizingCache?.formatters.formatCurrency === formatters.formatCurrency &&
    sizingCache.formatters.formatPercent === formatters.formatPercent
  ) {
    return sizingCache.copy;
  }
  const copy = {
    heroExplain: regimeTexts(WIDEST_STATE, heroExplainText, formatters),
    mechanismExplain: regimeTexts(WIDEST_STATE, mechanismExplainText, formatters),
    rippleExplain: regimeTexts(WIDEST_STATE, rippleExplainText, formatters),
    curveExplain: curveTexts(WIDEST_STATE, formatters),
    mathExplain: { text: mathExplainText(WIDEST_STATE, formatters) },
    sensitivityExplain: { text: sensitivityExplainText(WIDEST_STATE, formatters) },
    analystExplain: { text: analystExplainText(WIDEST_STATE, formatters) }
  };
  sizingCache = { formatters, copy };
  return copy;
}

/**
 * Build the yield-curve copy for every curve shape, so the stacked callout is as
 * tall as the longest one. Falls back to the selected shape alone when the state
 * carries no shape table.
 * @param {NarrativeState} state - Current state.
 * @param {NarrativeFormatters} formatters - Formatters.
 * @returns {Record<string, string>} Copy by curve key.
 */
function curveTexts(state, formatters) {
  const shapes = state.curve.shapes ?? { [state.curve.key]: state.curve };
  return Object.fromEntries(
    Object.entries(shapes).map(([key, shape]) => [
      key,
      curveExplainText({ ...state, curve: { ...shape, key } }, formatters)
    ])
  );
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

  setText(elements.priceValue, formatters.formatCurrency(price, 2));
  setText(elements.priceCaption, `This ${bond.years}-year, ${couponLabel} bond is now worth`);

  renderVariants(
    elements.regimeBadge,
    Object.fromEntries(REGIMES.map((key) => [key, REGIME_PRESENTATION[key].label])),
    regime
  );
  elements.regimeBadge.className = `chip reserve ${presentation.badgeClass}`;

  setText(elements.rateArrow, ARROW_GLYPH[/** @type {keyof typeof ARROW_GLYPH} */ (presentation.rateArrow)]);
  elements.rateArrow.className = `br-arrow ${presentation.rateArrow}`;
  setText(elements.priceArrow, ARROW_GLYPH[/** @type {keyof typeof ARROW_GLYPH} */ (presentation.priceArrow)]);
  elements.priceArrow.className = `br-arrow ${presentation.priceArrow}`;

  const sizing = sizingCopy(formatters);
  renderVariants(elements.heroExplain, regimeTexts(state, heroExplainText, formatters), regime, sizing.heroExplain);
  renderVariants(
    elements.mechanismExplain,
    regimeTexts(state, mechanismExplainText, formatters),
    regime,
    sizing.mechanismExplain
  );
  renderVariants(elements.mathExplain, { text: mathExplainText(state, formatters) }, "text", sizing.mathExplain);
  renderVariants(
    elements.sensitivityExplain,
    { text: sensitivityExplainText(state, formatters) },
    "text",
    sizing.sensitivityExplain
  );
  renderVariants(elements.analystExplain, { text: analystExplainText(state, formatters) }, "text", sizing.analystExplain);
  renderVariants(elements.curveExplain, curveTexts(state, formatters), state.curve.key, sizing.curveExplain);
  setText(
    elements.btnApplyCurveLabel,
    `Set the market rate to ${formatters.formatPercent(state.curve.atMaturityPct)}`
  );
  renderVariants(elements.rippleExplain, regimeTexts(state, rippleExplainText, formatters), regime, sizing.rippleExplain);

  renderCouponCompare(elements.couponCompare, state, formatters);
  renderMathLegend(elements, state, formatters);
  renderScheduleTable(elements.mathSchedule, state, formatters);
  renderPriceSplit(elements.pvSplit, state, formatters);
  renderAnalytics(elements, state, formatters);
}
