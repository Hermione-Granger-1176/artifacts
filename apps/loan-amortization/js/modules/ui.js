import { cacheElements as cacheElementsByIds } from "../../../../js/modules/element-cache.js";

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
 * Sync the formatted text inputs from the slider values.
 *
 * @param {Record<string, HTMLElement>} elements
 * @returns {void}
 */
export function syncInputsFromSliders(elements) {
  const inputs = /** @type {Record<string, HTMLInputElement>} */ (elements);
  inputs.inPrincipal.value = Math.round(+inputs.slPrincipal.value).toLocaleString("en-US");
  inputs.inRate.value = (+inputs.slRate.value).toFixed(2);
  inputs.inTenure.value = inputs.slTenure.value;
}

/**
 * Update the bi-weekly mode button state and description copy.
 *
 * @param {Record<string, HTMLElement>} elements
 * @param {string} bwMode
 * @returns {void}
 */
export function syncBiweeklyModeUI(elements, bwMode) {
  elements.bwTrue.classList.toggle("active", bwMode === "true");
  elements.bwAccel.classList.toggle("active", bwMode === "accelerated");
  elements.bwDesc.textContent =
    bwMode === "true"
      ? "EMI recalculated for 26 periods per year"
      : "Monthly EMI / 2 paid 26 times (13 monthly payments per year)";
}

/**
 * Toggle the bi-weekly mode panel based on the selected cadence.
 *
 * @param {Record<string, HTMLElement>} elements
 * @param {string} frequency
 * @param {string} bwMode
 * @returns {void}
 */
export function updateBiweeklyMode(elements, frequency, bwMode) {
  elements.biweeklyMode.hidden = frequency !== "biweekly";
  syncBiweeklyModeUI(elements, bwMode);
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
