/**
 * Format a number as a rounded dollar string with commas.
 * @param {number} value - The value to format.
 * @returns {string} Formatted currency string (e.g. "$1,234").
 */
export function formatCurrency(value) {
  return `$${Math.round(value).toLocaleString("en-US")}`;
}

export { formatDollarTick, parseNumber } from '../../../../js/modules/formatting.js';
export { escapeAttribute } from '../../../../js/modules/html-escape.js';
