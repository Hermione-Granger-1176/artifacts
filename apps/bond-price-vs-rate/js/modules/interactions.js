import { initSegmented } from "../../../../js/modules/segmented.js";
import { CURVE_BUTTON_IDS } from "./ui.js";

/** Reverse lookup from a preset button id back to its yield-curve key. */
const CURVE_KEY_BY_ID = Object.fromEntries(
  Object.entries(CURVE_BUTTON_IDS).map(([curveKey, id]) => [id, curveKey])
);

/**
 * Bind the explainer's controls: the three sliders, the yield-curve preset
 * segmented control, and the apply-curve-rate button. Every slider drag runs
 * the same recalc path; theme changes are wired separately through the shared
 * app shell in `app.js`. The shared initSegmented wiring owns the active class
 * and aria-pressed sync, so the caller only reacts to the selected preset. App
 * state mutations stay injected from the caller.
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

  initSegmented(elements.curveToggle, (button) => {
    onCurveSelect(CURVE_KEY_BY_ID[button.id]);
  });

  elements.btnApplyCurve.addEventListener("click", onApplyCurveRate);
}
