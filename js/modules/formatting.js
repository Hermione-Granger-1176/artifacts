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
 * Parse a string into a number, stripping non-numeric characters.
 * @param {string} value - Raw input string.
 * @returns {number} Parsed number (NaN if empty after stripping).
 */
export function parseNumber(value) {
  return +String(value).replace(/[^0-9.\-]/g, "");
}
