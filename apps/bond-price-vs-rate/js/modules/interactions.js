import { CURVE_BUTTON_IDS } from "./ui.js";

/**
 * Bind the explainer's controls: the three sliders, the three yield-curve
 * preset buttons, and the apply-curve-rate button. Every slider drag runs the
 * same recalc path; theme changes are wired separately through the shared app
 * shell in `app.js`. App state mutations stay injected from the caller.
 *
 * @param {object} options
 * @param {Record<string, HTMLElement>} options.elements
 * @param {() => void} options.onSliderInput
 * @param {(curveKey: string) => void} options.onCurveSelect
 * @param {() => void} options.onApplyCurveRate
 * @returns {void}
 */
export function bindEvents({ elements, onSliderInput, onCurveSelect, onApplyCurveRate }) {
  for (const id of ["slRate", "slCoupon", "slYears"]) {
    elements[id].addEventListener("input", onSliderInput);
  }

  for (const [curveKey, id] of Object.entries(CURVE_BUTTON_IDS)) {
    elements[id].addEventListener("click", () => onCurveSelect(curveKey));
  }

  elements.btnApplyCurve.addEventListener("click", onApplyCurveRate);
}
