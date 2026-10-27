import { cacheElements as cacheElementsByIds } from "../../../../js/modules/element-cache.js";
import { setText } from "../../../../js/modules/dom-sync.js";

// One formatter for the principal field, so a slider drag does not build one per
// tick (which is what toLocaleString does on every call).
const PRINCIPAL_FORMAT = new Intl.NumberFormat("en-US");

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
  inputs.inPrincipal.value = PRINCIPAL_FORMAT.format(Math.round(+inputs.slPrincipal.value));
  inputs.inRate.value = (+inputs.slRate.value).toFixed(2);
  inputs.inTenure.value = inputs.slTenure.value;
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
  elements.bwTrue.classList.toggle("active", bwMode === "true");
  elements.bwAccel.classList.toggle("active", bwMode === "accelerated");
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
