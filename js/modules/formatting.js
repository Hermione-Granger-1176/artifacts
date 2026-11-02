/**
 * Number formatting and parsing helpers shared by artifact apps.
 * @module formatting
 */

/**
 * Format a number as a compact dollar tick label (e.g. "$50k", "$2.5k", "$2.5M").
 * Values from 1,000 to 9,999 keep one decimal. Values from 10,000 up round to whole thousands.
 * @param {number} value - The value to format.
 * @returns {string} Compact dollar string for chart axis labels.
 */
export function formatDollarTick(value) {
  const magnitude = dollarTickMagnitude(Math.abs(value));
  return `${signFor(value, magnitude)}$${magnitude}`;
}

/**
 * @param {number} absoluteValue - A non-negative value.
 * @returns {string} The compact magnitude for formatDollarTick, without sign or "$".
 */
function dollarTickMagnitude(absoluteValue) {
  if (absoluteValue >= 1000000) {
    return `${(absoluteValue / 1000000).toFixed(1)}M`;
  }

  if (absoluteValue >= 10000) {
    return `${Math.round(absoluteValue / 1000)}k`;
  }

  if (absoluteValue >= 1000) {
    return `${(absoluteValue / 1000).toFixed(1)}k`;
  }

  return String(Math.round(absoluteValue));
}

/**
 * Return the minus sign for a negative value, unless its formatted magnitude
 * rounds to zero. Float residue such as -0.004 then reads "$0.00", not "-$0.00".
 * @param {number} value - The value being formatted.
 * @param {string} magnitude - The formatted absolute value.
 * @returns {string} "-" or "".
 */
function signFor(value, magnitude) {
  return value < 0 && /[1-9]/.test(magnitude) ? "-" : "";
}

/**
 * Format a number as a dollar string with grouped thousands.
 * @param {number} value - The value to format.
 * @param {number} [digits=0] - Fraction digits to show. 0 rounds to whole dollars.
 * @returns {string} Formatted currency string (e.g. "$1,234" or "$1,234.56").
 */
export function formatCurrency(value, digits = 0) {
  const magnitude = groupedNumberFormat(digits).format(Math.abs(value));
  return `${signFor(value, magnitude)}$${magnitude}`;
}

/** @type {Map<number, Intl.NumberFormat>} */
const groupedNumberFormats = new Map();

/**
 * One cached formatter per fraction-digit count. `toLocaleString` with options
 * builds a new formatter on every call, which is orders of magnitude slower
 * than reusing one across the thousands of cells in a loan schedule.
 * @param {number} digits - Fraction digits to show.
 * @returns {Intl.NumberFormat} An en-US formatter with grouped thousands.
 */
function groupedNumberFormat(digits) {
  let format = groupedNumberFormats.get(digits);
  if (!format) {
    format = new Intl.NumberFormat("en-US", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    });
    groupedNumberFormats.set(digits, format);
  }
  return format;
}

/**
 * Format a number already expressed as a percent with a trailing percent sign.
 * @param {number} value - The value expressed as a percent (e.g. 5 for 5%).
 * @param {number} [digits=1] - Fraction digits to show.
 * @returns {string} Formatted percent string (e.g. "5.0%").
 */
export function formatPercent(value, digits = 1) {
  const magnitude = Math.abs(value).toFixed(digits);
  return `${signFor(value, magnitude)}${magnitude}%`;
}

/**
 * Format a number with compact k/M/B suffixes and no currency sign.
 * @param {number} value - The value to format.
 * @returns {string} Compact string (e.g. "30k", "2.5M", "3.0B").
 */
export function formatCompact(value) {
  const magnitude = compactMagnitude(Math.abs(value));
  return `${signFor(value, magnitude)}${magnitude}`;
}

/**
 * @param {number} absoluteValue - A non-negative value.
 * @returns {string} The compact magnitude for formatCompact, without a sign.
 */
function compactMagnitude(absoluteValue) {
  if (absoluteValue >= 1e9) {
    return `${(absoluteValue / 1e9).toFixed(1)}B`;
  }

  if (absoluteValue >= 1e6) {
    return `${(absoluteValue / 1e6).toFixed(1)}M`;
  }

  if (absoluteValue >= 1e3) {
    return `${Math.round(absoluteValue / 1e3)}k`;
  }

  return String(Math.round(absoluteValue));
}

/**
 * Parse a string into a number after removing every character except digits,
 * ".", and "-". Input such as "1-2" or "-" leaves no valid number.
 * @param {string} value - Raw input string.
 * @returns {number} Parsed number, or 0 when the remaining text is not a finite number.
 */
export function parseNumber(value) {
  const parsed = +String(value).replace(/[^0-9.\-]/g, "");
  return Number.isFinite(parsed) ? parsed : 0;
}
