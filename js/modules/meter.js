/**
 * Shared meter-fill control for artifact apps. The shared .meter-fill is full
 * width and is scaled from its left edge with the `scale` property, not `width`.
 * @module meter
 */

import { skipFirstTransition } from "./dom-sync.js";

/**
 * Set how full a .meter-fill is.
 * @param {HTMLElement} fill - The .meter-fill element.
 * @param {number} fraction - Fill between 0 and 1. Out-of-range values are clamped; non-finite values become 0.
 * @returns {number} The fraction applied after clamping.
 */
export function setMeterValue(fill, fraction) {
  const value = Number.isFinite(fraction) ? Math.min(1, Math.max(0, fraction)) : 0;
  skipFirstTransition(fill);
  fill.style.scale = `${value} 1`;
  return value;
}
