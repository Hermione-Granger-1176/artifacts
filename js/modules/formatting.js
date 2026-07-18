/**
 * Number formatting and parsing helpers shared by artifact apps.
 * @module formatting
 */

/**
 * Format a number as a compact dollar tick label (e.g. "$50k", "$2.5M").
 * @param {number} value - The value to format.
 * @returns {string} Compact dollar string for chart axis labels.
 */
export function formatDollarTick(value) {
  const absoluteValue = Math.abs(value);
  const sign = value < 0 ? "-" : "";

  if (absoluteValue >= 1000000) {
    return `${sign}$${(absoluteValue / 1000000).toFixed(1)}M`;
  }

  if (absoluteValue >= 10000) {
    return `${sign}$${Math.round(absoluteValue / 1000)}k`;
  }

  if (absoluteValue >= 1000) {
    return `${sign}$${(absoluteValue / 1000).toFixed(1)}k`;
  }

  return `${sign}$${Math.round(absoluteValue)}`;
}

/**
 * Format a number as a dollar string with grouped thousands.
 * @param {number} value - The value to format.
 * @param {number} [digits=0] - Fraction digits to show. 0 rounds to whole dollars.
 * @returns {string} Formatted currency string (e.g. "$1,234" or "$1,234.56").
 */
export function formatCurrency(value, digits = 0) {
  const magnitude = Math.abs(value).toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
  return `${value < 0 ? "-" : ""}$${magnitude}`;
}

/**
 * Format a number already expressed as a percent with a trailing percent sign.
 * @param {number} value - The value expressed as a percent (e.g. 5 for 5%).
 * @param {number} [digits=1] - Fraction digits to show.
 * @returns {string} Formatted percent string (e.g. "5.0%").
 */
export function formatPercent(value, digits = 1) {
  return `${value.toFixed(digits)}%`;
}

/**
 * Parse a string into a number, stripping non-numeric characters.
 * @param {string} value - Raw input string.
 * @returns {number} Parsed number, or 0 when nothing numeric remains.
 */
export function parseNumber(value) {
  const parsed = +String(value).replace(/[^0-9.\-]/g, "");
  return Number.isFinite(parsed) ? parsed : 0;
}
