/**
 * Deterministic formatting helpers for generated vendor documents.
 *
 * Everything here avoids `toLocaleString`/`toLocaleDateString` on purpose: the
 * same seed has to produce byte-identical text in the browser, in Node tests,
 * and in the CI thumbnail run, and locale data is not guaranteed to match
 * across those three. Hand-rolled grouping and month names keep output stable.
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

const MILLISECONDS_PER_DAY = 86_400_000;

/**
 * Round a value to whole cents, avoiding the float drift that makes repeated
 * addition of `x.xx5` values disagree between runs.
 * @param {number} value - Raw amount.
 * @returns {number} Amount rounded to two decimal places.
 */
export function roundCents(value) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
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
 * A negative amount reads `-$1,234.50`, with the sign outside the symbol.
 * Prefixing `$` to the already-signed output of `formatAmount` would print
 * `$-1,234.50`, which no accounting document does.
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
  const month = MONTH_ABBREVIATIONS[date.getMonth()];
  const day = String(date.getDate()).padStart(2, "0");
  return `${month} ${day}, ${date.getFullYear()}`;
}

/**
 * Shift a date by a whole number of days.
 * @param {Date} date - Starting date.
 * @param {number} days - Days to add; negative values move backwards.
 * @returns {Date} A new date instance.
 */
export function addDays(date, days) {
  return new Date(date.getTime() + days * MILLISECONDS_PER_DAY);
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
 * Shared by both renderers so the monogram tile reads the same in the export as
 * it does on screen; it used to exist only in the paper renderer, and the PDF
 * drew no mark at all.
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
