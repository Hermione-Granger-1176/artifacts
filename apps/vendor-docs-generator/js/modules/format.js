/**
 * Deterministic formatting helpers for generated vendor documents.
 *
 * Nothing here uses `toLocaleString` or `toLocaleDateString`. A given seed
 * produces byte-identical text in the browser, in Node tests, and in the CI
 * thumbnail run, and locale data is not guaranteed to match across those. Grouping
 * and month names are hand-rolled.
 *
 * @module format
 */

const MONTH_ABBREVIATIONS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec"
];

const ONES = [
  "",
  "One",
  "Two",
  "Three",
  "Four",
  "Five",
  "Six",
  "Seven",
  "Eight",
  "Nine",
  "Ten",
  "Eleven",
  "Twelve",
  "Thirteen",
  "Fourteen",
  "Fifteen",
  "Sixteen",
  "Seventeen",
  "Eighteen",
  "Nineteen"
];

const TENS = [
  "",
  "",
  "Twenty",
  "Thirty",
  "Forty",
  "Fifty",
  "Sixty",
  "Seventy",
  "Eighty",
  "Ninety"
];

const SCALES = /** @type {[string, number][]} */ ([
  ["Billion", 1_000_000_000],
  ["Million", 1_000_000],
  ["Thousand", 1_000]
]);

/**
 * Round a value to whole cents, half away from zero, using the decimal digits
 * the value prints as.
 *
 * The decision reads the digits of the shortest decimal string, so the third
 * decimal digit alone decides whether the dropped part is at least half a cent.
 * @param {number} value - Raw amount.
 * @returns {number} Amount rounded to two decimal places.
 */
export function roundCents(value) {
  const magnitude = Math.abs(value);
  const text = String(magnitude);

  // Exponent notation means below 1e-6, which is zero cents, or at least 1e21,
  // which is already a whole number.
  if (text.includes("e")) {
    return magnitude < 1 ? 0 : value;
  }

  const [whole, fraction = ""] = text.split(".");

  // Whole cents already, and also `Infinity` and `NaN`, which have no point.
  if (fraction.length <= 2) {
    return value;
  }

  // A third decimal only prints for values below 2^46, so the cent count stays
  // below 2^53 and is an exact integer. Dividing it by 100 gives the nearest
  // double to the printed cents.
  const cents = Number(whole + fraction.slice(0, 2)) + (fraction.charAt(2) >= "5" ? 1 : 0);

  // A negative amount that rounds to zero comes back as plain zero, not -0.
  return value < 0 && cents !== 0 ? -cents / 100 : cents / 100;
}

/**
 * Format a number with US thousands separators and exactly two decimals.
 * @param {number} value - Amount to format.
 * @returns {string} Grouped amount without a currency symbol.
 */
export function formatAmount(value) {
  const rounded = roundCents(Math.abs(value));
  const [whole, fraction] = rounded.toFixed(2).split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const sign = value < 0 && rounded !== 0 ? "-" : "";
  return `${sign}${grouped}.${fraction}`;
}

/**
 * Format a number as US dollars.
 *
 * A negative amount reads `-$1,234.50`, with the sign before the symbol.
 *
 * @param {number} value - Amount to format.
 * @returns {string} Dollar-prefixed amount, for example `$1,234.50`.
 */
export function formatMoney(value) {
  const formatted = formatAmount(value);
  return formatted.startsWith("-") ? `-$${formatted.slice(1)}` : `$${formatted}`;
}

/**
 * Left-pad a number with zeroes to a fixed width.
 * @param {number} value - Number to pad.
 * @param {number} [length=5] - Target width.
 * @returns {string} Zero-padded string.
 */
export function padNumber(value, length = 5) {
  return String(value).padStart(length, "0");
}

/**
 * Format a date the way US commercial paperwork usually prints it.
 * @param {Date} date - Date to format.
 * @returns {string} Date as `Mon DD, YYYY`.
 */
export function formatDate(date) {
  return `${MONTH_ABBREVIATIONS[date.getMonth()]} ${padNumber(date.getDate(), 2)}, ${date.getFullYear()}`;
}

/**
 * Format a date as a calendar date in ISO 8601.
 *
 * Reads the local calendar fields, so the value matches the date printed on the
 * page. `toISOString` is not used because it converts to UTC first and can
 * return the previous day.
 * @param {Date} date - Date to format.
 * @returns {string} Date as `YYYY-MM-DD`.
 */
export function isoDate(date) {
  return `${date.getFullYear()}-${padNumber(date.getMonth() + 1, 2)}-${padNumber(date.getDate(), 2)}`;
}

/**
 * Shift a date by a whole number of days.
 * @param {Date} date - Starting date.
 * @param {number} days - Days to add; negative values move backwards.
 * @returns {Date} A new date instance.
 */
export function addDays(date, days) {
  const shifted = new Date(date.getTime());
  shifted.setDate(shifted.getDate() + days);
  return shifted;
}

/**
 * Format a percentage rate for display.
 * @param {number} rate - Rate as a fraction, for example `0.0825`.
 * @param {number} [digits=2] - Decimal places to keep.
 * @returns {string} Percentage string including the sign, for example `8.25%`.
 */
export function formatRate(rate, digits = 2) {
  return `${(rate * 100).toFixed(digits)}%`;
}

/**
 * Spell out a non-negative integer below one trillion.
 * @param {number} value - Whole number to spell out.
 * @returns {string} English words, for example `One Thousand Two Hundred`.
 */
export function numberToWords(value) {
  const whole = Math.floor(Math.abs(value));

  if (whole === 0) {
    return "Zero";
  }

  /**
   * @param {number} part - Value below one thousand.
   * @returns {string} Words for that part, without trailing space.
   */
  function belowThousand(part) {
    const words = [];
    let rest = part;

    if (rest >= 100) {
      words.push(ONES[Math.floor(rest / 100)], "Hundred");
      rest %= 100;
    }

    if (rest >= 20) {
      words.push(TENS[Math.floor(rest / 10)]);
      rest %= 10;
    }

    if (rest > 0) {
      words.push(ONES[rest]);
    }

    return words.join(" ");
  }

  const words = [];
  let rest = whole;

  for (const [name, size] of SCALES) {
    if (rest >= size) {
      words.push(belowThousand(Math.floor(rest / size)), name);
      rest %= size;
    }
  }

  if (rest > 0) {
    words.push(belowThousand(rest));
  }

  return words.join(" ");
}

/**
 * Render a money amount the way a tax invoice spells its grand total.
 * @param {number} value - Amount in dollars.
 * @returns {string} For example `US Dollars One Hundred and 50/100 only`.
 */
export function amountInWords(value) {
  const rounded = roundCents(Math.abs(value));
  const dollars = Math.floor(rounded);
  const cents = Math.round((rounded - dollars) * 100);
  return `US Dollars ${numberToWords(dollars)} and ${padNumber(cents, 2)}/100 only`;
}

/**
 * First letters of the first two words of a name.
 *
 * Used by both renderers for the monogram tile.
 * @param {string} name - Vendor name.
 * @returns {string} Up to two upper-case initials.
 */
export function initialsOf(name) {
  return name
    .split(" ")
    .slice(0, 2)
    .map((word) => word.charAt(0))
    .join("")
    .toUpperCase();
}

/** Logo styles that set the vendor name in capitals. */
const CAPITALISED_LOGO_STYLES = new Set(["stripe", "thin"]);

/**
 * The document title as the page prints it. The capitals are part of the text
 * itself, not a CSS text-transform, so the sidecar, the boxes, and the pixels
 * carry the same string.
 * @param {string} title - Document title, such as "Delivery challan".
 * @returns {string} The printed title, such as "DELIVERY CHALLAN".
 */
export function printedTitle(title) {
  return title.toUpperCase();
}

/**
 * The vendor name as the logo prints it. The stripe and thin logos set the
 * name in capitals. The other logos print it as written.
 * @param {{ name: string, logoStyle: string }} vendor - Vendor whose name to print.
 * @returns {string} The printed name.
 */
export function printedVendorName(vendor) {
  return CAPITALISED_LOGO_STYLES.has(vendor.logoStyle) ? vendor.name.toUpperCase() : vendor.name;
}
