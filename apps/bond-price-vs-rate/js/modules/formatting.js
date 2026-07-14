/**
 * Number and currency formatting helpers for the bonds vs interest rates explainer.
 * @module formatting
 */

/**
 * Format a number as a currency string with commas and fixed decimals.
 * @param {number} value - The value to format.
 * @param {number} [digits=2] - Fraction digits to show.
 * @returns {string} Formatted currency string (e.g. "$1,170.60").
 */
export function formatCurrency(value, digits = 2) {
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  })}`;
}

/**
 * Format a percentage value with a trailing percent sign.
 * @param {number} value - The value already expressed as a percent (e.g. 5 for 5%).
 * @param {number} [digits=1] - Fraction digits to show.
 * @returns {string} Formatted percent string (e.g. "5.0%").
 */
export function formatPercent(value, digits = 1) {
  return `${value.toFixed(digits)}%`;
}

export { formatDollarTick } from '../../../../js/modules/formatting.js';
