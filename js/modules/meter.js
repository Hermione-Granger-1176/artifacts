/**
 * Shared meter-fill control for artifact apps. The shared .meter-fill is full
 * width and scaled from its left edge with the scale property, so moving the bar is a
 * compositor-only transform instead of a layout-triggering width change.
 * @module meter
 */

import { skipFirstTransition } from "./dom-sync.js";

/**
 * Set how full a .meter-fill is.
 * @param {HTMLElement} fill - The .meter-fill element.
 * @param {number} fraction - Fill between 0 and 1; out-of-range values and NaN are clamped.
 * @returns {number} The fraction applied after clamping.
 */
export function setMeterValue(fill, fraction) {
  const value = Number.isFinite(fraction) ? Math.min(1, Math.max(0, fraction)) : 0;
  skipFirstTransition(fill);
  fill.style.scale = `${value} 1`;
  return value;
}
