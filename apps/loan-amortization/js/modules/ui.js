import { cacheElements as cacheElementsByIds } from "../../../../js/modules/element-cache.js";
import { setText } from "../../../../js/modules/dom-sync.js";

// One formatter per field, so a slider drag does not build one per tick (which
// is what toLocaleString does on every call).
const PRINCIPAL_FORMAT = new Intl.NumberFormat("en-US");
// Two decimals for a slider rate such as 5.25, and up to four for a typed rate
// such as 6.125, so the field shows the rate the calculation uses.
const RATE_FORMAT = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
  useGrouping: false
});

/** @typedef {{ principal: number, rate: number, tenure: number }} LoanInputs */

const ELEMENT_IDS = [
  "inPrincipal",
  "inRate",
  "inTenure",
  "slPrincipal",
  "slRate",
  "slTenure",
  "selFreq",
  "biweeklyMode",
  "bwTrue",
  "bwAccel",
  "bwDesc",
  "extraList",
  "btnAdd",
  "metrics",
  "viewToggle",
  "btnCharts",
  "btnTable",
  "chartsWrap",
  "tableWrap",
  "tableToggle",
  "btnPeriod",
  "btnYearly",
  "tableSummary",
  "periodTableWrap",
  "yearlyTableWrap",
  "tbody",
  "ybody",
  "balanceChart",
  "compChart",
  "savingsChart",
  "cumulChart",
  "periodChart"
];

/**
 * Cache the DOM nodes used by the loan amortization UI.
 *
 * @param {Document} documentObj
 * @returns {Record<string, HTMLElement|null>}
 */
export function cacheElements(documentObj = document) {
  return cacheElementsByIds(ELEMENT_IDS, documentObj);
}

/**
 * Read the loan inputs from the three sliders.
 *
 * @param {Record<string, HTMLElement>} elements
 * @returns {LoanInputs}
 */
export function readSliderInputs(elements) {
  const sliders = /** @type {Record<string, HTMLInputElement>} */ (elements);
  return {
    principal: +sliders.slPrincipal.value,
    rate: +sliders.slRate.value,
    tenure: +sliders.slTenure.value
  };
}

/**
 * Write the loan inputs into the formatted text fields.
 *
 * @param {Record<string, HTMLElement>} elements
 * @param {LoanInputs} inputs
 * @returns {void}
 */
export function syncTextInputs(elements, { principal, rate, tenure }) {
  const fields = /** @type {Record<string, HTMLInputElement>} */ (elements);
  fields.inPrincipal.value = PRINCIPAL_FORMAT.format(Math.round(principal));
  fields.inRate.value = RATE_FORMAT.format(rate);
  fields.inTenure.value = String(tenure);
}

const BIWEEKLY_DESCRIPTIONS = {
  inactive: "Used when the EMI frequency is Bi-weekly",
  true: "EMI recalculated for 26 periods per year",
  accelerated: "Monthly EMI / 2 paid 26 times (13 monthly payments per year)"
};

/**
 * Update the bi-weekly mode button state and description copy.
 *
 * @param {Record<string, HTMLElement>} elements
 * @param {string} bwMode
 * @param {boolean} [enabled] - Whether bi-weekly is the selected frequency.
 * @returns {void}
 */
export function syncBiweeklyModeUI(elements, bwMode, enabled = true) {
  for (const [button, mode] of /** @type {const} */ ([[elements.bwTrue, "true"], [elements.bwAccel, "accelerated"]])) {
    button.classList.toggle("active", bwMode === mode);
    button.setAttribute("aria-pressed", String(bwMode === mode));
  }
  setText(
    elements.bwDesc,
    enabled
      ? BIWEEKLY_DESCRIPTIONS[/** @type {"true" | "accelerated"} */ (bwMode)]
      : BIWEEKLY_DESCRIPTIONS.inactive
  );
}

/**
 * Enable the bi-weekly mode panel only for the bi-weekly cadence. The panel
 * stays in the layout and its buttons are disabled otherwise, so the controls
 * below it never move when the frequency changes.
 *
 * @param {Record<string, HTMLElement>} elements
 * @param {string} frequency
 * @param {string} bwMode
 * @returns {void}
 */
export function updateBiweeklyMode(elements, frequency, bwMode) {
  const enabled = frequency === "biweekly";
  elements.biweeklyMode.classList.toggle("is-inactive", !enabled);
  /** @type {HTMLButtonElement} */ (elements.bwTrue).disabled = !enabled;
  /** @type {HTMLButtonElement} */ (elements.bwAccel).disabled = !enabled;
  syncBiweeklyModeUI(elements, bwMode, enabled);
}

/**
 * Show one of two panels and mark its toggle button active.
 *
 * @param {[HTMLElement, HTMLElement]} panels - First and second panel.
 * @param {[HTMLElement, HTMLElement]} buttons - Toggle buttons in the same order.
 * @param {boolean} showFirst - Whether the first panel is the visible one.
 * @returns {void}
 */
function showFirstPanel([firstPanel, secondPanel], [firstButton, secondButton], showFirst) {
  firstPanel.hidden = !showFirst;
  secondPanel.hidden = showFirst;
  firstButton.classList.toggle("active", showFirst);
  secondButton.classList.toggle("active", !showFirst);
}

/**
 * Switch between chart and table views.
 *
 * @param {Record<string, HTMLElement>} elements
 * @param {"charts" | "table"} mode
 * @returns {void}
 */
export function setViewMode(elements, mode) {
  showFirstPanel(
    [elements.chartsWrap, elements.tableWrap],
    [elements.btnCharts, elements.btnTable],
    mode === "charts"
  );
}

/**
 * Switch between per-period and yearly schedule tables.
 *
 * @param {Record<string, HTMLElement>} elements
 * @param {"period" | "yearly"} mode
 * @returns {void}
 */
export function setTableMode(elements, mode) {
  showFirstPanel(
    [elements.periodTableWrap, elements.yearlyTableWrap],
    [elements.btnPeriod, elements.btnYearly],
    mode === "period"
  );
}

/**
 * Return the chart canvas nodes expected by the chart renderer.
 *
 * @param {Record<string, HTMLElement>} elements
 * @returns {{ balanceChart: HTMLElement, compChart: HTMLElement, savingsChart: HTMLElement, cumulChart: HTMLElement, periodChart: HTMLElement }}
 */
export function getChartElements(elements) {
  return {
    balanceChart: elements.balanceChart,
    compChart: elements.compChart,
    savingsChart: elements.savingsChart,
    cumulChart: elements.cumulChart,
    periodChart: elements.periodChart
  };
}
