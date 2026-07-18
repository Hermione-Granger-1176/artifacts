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
 * @param {Record<string, HTMLInputElement>} elements
 * @returns {void}
 */
export function syncInputsFromSliders(elements) {
  elements.inPrincipal.value = Math.round(+elements.slPrincipal.value).toLocaleString("en-US");
  elements.inRate.value = (+elements.slRate.value).toFixed(2);
  elements.inTenure.value = elements.slTenure.value;
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
 * Switch between chart and table views.
 *
 * @param {Record<string, HTMLElement>} elements
 * @param {"charts" | "table"} mode
 * @returns {void}
 */
export function setViewMode(elements, mode) {
  const showCharts = mode === "charts";
  elements.chartsWrap.hidden = !showCharts;
  elements.tableWrap.hidden = showCharts;
  elements.btnCharts.classList.toggle("active", showCharts);
  elements.btnTable.classList.toggle("active", !showCharts);
}

/**
 * Switch between per-period and yearly schedule tables.
 *
 * @param {Record<string, HTMLElement>} elements
 * @param {"period" | "yearly"} mode
 * @returns {void}
 */
export function setTableMode(elements, mode) {
  const showPeriod = mode === "period";
  elements.periodTableWrap.hidden = !showPeriod;
  elements.yearlyTableWrap.hidden = showPeriod;
  elements.btnPeriod.classList.toggle("active", showPeriod);
  elements.btnYearly.classList.toggle("active", !showPeriod);
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
