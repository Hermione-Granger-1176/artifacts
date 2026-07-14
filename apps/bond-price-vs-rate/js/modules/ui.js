import { cacheElements as cacheElementsByIds } from "../../../../js/modules/element-cache.js";

const ELEMENT_IDS = [
  "slRate",
  "slCoupon",
  "slYears",
  "rateValue",
  "couponValue",
  "yearsValue",
  "priceCaption",
  "priceValue",
  "regimeBadge",
  "rateArrow",
  "priceArrow",
  "heroExplain",
  "couponCompare",
  "mechanismExplain",
  "mathLegendCoupon",
  "mathLegendRate",
  "mathLegendYears",
  "mathLegendFace",
  "mathSchedule",
  "mathExplain",
  "sensitivityChart",
  "sensitivityExplain",
  "priceRateChart",
  "statCurrentYield",
  "statMacaulay",
  "statModified",
  "statConvexity",
  "pvSplit",
  "analystExplain",
  "btnCurveNormal",
  "btnCurveFlat",
  "btnCurveInverted",
  "btnApplyCurve",
  "yieldCurveChart",
  "curveExplain",
  "rippleExplain"
];

/** Map from curve key to its preset toggle button id. */
export const CURVE_BUTTON_IDS = {
  normal: "btnCurveNormal",
  flat: "btnCurveFlat",
  inverted: "btnCurveInverted"
};

/**
 * Cache the DOM nodes used by the bonds vs interest rates explainer.
 *
 * @param {Document} documentObj
 * @returns {Record<string, HTMLElement|null>}
 */
export function cacheElements(documentObj = document) {
  return cacheElementsByIds(ELEMENT_IDS, documentObj);
}

/**
 * Update the live value labels beside each slider.
 *
 * @param {Record<string, HTMLInputElement>} elements
 * @returns {void}
 */
export function syncSliderLabels(elements) {
  const rate = +elements.slRate.value;
  const coupon = +elements.slCoupon.value;
  const years = +elements.slYears.value;

  elements.rateValue.textContent = `${rate.toFixed(1)}%`;
  elements.couponValue.textContent = `${coupon.toFixed(1)}%`;
  elements.yearsValue.textContent = `${years} year${years === 1 ? "" : "s"}`;
}

/**
 * Reflect the selected yield-curve preset on the three toggle buttons.
 *
 * @param {Record<string, HTMLElement>} elements
 * @param {string} selectedKey - One of the CURVE_BUTTON_IDS keys.
 * @returns {void}
 */
export function syncCurveButtons(elements, selectedKey) {
  for (const [key, id] of Object.entries(CURVE_BUTTON_IDS)) {
    const isSelected = key === selectedKey;
    elements[id].classList.toggle("active", isSelected);
    elements[id].setAttribute("aria-pressed", String(isSelected));
  }
}

/**
 * Return the chart canvas nodes expected by the chart renderer.
 *
 * @param {Record<string, HTMLElement>} elements
 * @returns {{ priceRateChart: HTMLElement, sensitivityChart: HTMLElement, yieldCurveChart: HTMLElement }}
 */
export function getChartElements(elements) {
  return {
    priceRateChart: elements.priceRateChart,
    sensitivityChart: elements.sensitivityChart,
    yieldCurveChart: elements.yieldCurveChart
  };
}
