import assert from 'node:assert/strict';
import test from 'node:test';

import {
  addDays,
  amountInWords,
  formatAmount,
  formatDate,
  formatMoney,
  formatRate,
  numberToWords,
  padNumber,
  roundCents
} from '../../../../apps/vendor-docs-generator/js/modules/format.js';

test('roundCents settles float drift onto whole cents', () => {
  assert.equal(roundCents(0.1 + 0.2), 0.3);
  assert.equal(roundCents(1.005), 1.01);
  assert.equal(roundCents(-1.005), -1.01);
  assert.equal(roundCents(1234.5678), 1234.57);
});

test('roundCents rounds every half cent away from zero, at any size', () => {
  // 522.295 is stored as 522.29499999999996, so binary rounding cut it to 522.29.
  assert.equal(roundCents(522.295), 522.3);
  assert.equal(roundCents(0.145), 0.15);
  assert.equal(roundCents(1.005), 1.01);
  assert.equal(roundCents(2.675), 2.68);
  assert.equal(roundCents(-2.675), -2.68);
  assert.equal(roundCents(-522.295), -522.3);
  assert.equal(roundCents(98_765.435), 98_765.44);
  assert.equal(roundCents(0.144), 0.14);
  assert.equal(roundCents(-0.004), 0);
  assert.ok(Object.is(roundCents(-0.004), 0), 'a negative that rounds to zero is plain zero');
});

test('roundCents decides on the printed digits, not on a re-parsed shift', () => {
  // The double just below 1.475 prints as 1.4749999999999999. Shifting that
  // string by `e2` re-parses to exactly 147.5 and would round it up.
  assert.equal(roundCents(1.4749999999999999), 1.47);
  assert.equal(roundCents(1.475), 1.48);
});

test('roundCents leaves whole numbers and two-decimal amounts unchanged', () => {
  for (const value of [0, 3, -4, 1.2, 7.5, -42.25, 1234.56, 99_999.99, 0.01, -0.01]) {
    assert.equal(roundCents(value), value);
  }

  assert.ok(Object.is(roundCents(-0), -0));
});

test('roundCents handles exponent notation and non-finite values', () => {
  assert.equal(roundCents(1e-7), 0);
  assert.equal(roundCents(-1e-7), 0);
  assert.equal(roundCents(1e21), 1e21);
  assert.equal(roundCents(-2.5e22), -2.5e22);
  assert.equal(roundCents(Number.POSITIVE_INFINITY), Number.POSITIVE_INFINITY);
  assert.ok(Number.isNaN(roundCents(Number.NaN)));
});

/**
 * Exact half-away-from-zero rounding of a value's shortest decimal string, in
 * integer cents, as the oracle for the sweep below.
 * @param {number} value - Finite amount below 1e21 and at least 1e-6 in size.
 * @returns {bigint} Rounded cents, signed.
 */
function exactCents(value) {
  const [whole, fraction = ''] = String(Math.abs(value)).split('.');
  const scaled = BigInt(whole + fraction.padEnd(3, '0').slice(0, 3));
  const cents = (scaled + 5n) / 10n;
  return value < 0 ? -cents : cents;
}

test('roundCents agrees with exact decimal rounding at and around every half cent', () => {
  const view = new DataView(new ArrayBuffer(8));
  /**
   * @param {number} value - Starting double.
   * @param {number} step - +1 for the next double up, -1 for the next one down.
   * @returns {number} The adjacent double.
   */
  const adjacent = (value, step) => {
    view.setFloat64(0, value);
    view.setBigInt64(0, view.getBigInt64(0) + BigInt(step));
    return view.getFloat64(0);
  };

  for (let cents = 0; cents < 2_000_000; cents += 7) {
    const half = (cents + 0.5) / 100;

    for (const value of [half, -half, adjacent(half, 1), adjacent(half, -1), cents / 100]) {
      assert.equal(BigInt(Math.round(roundCents(value) * 100)), exactCents(value), String(value));
    }
  }
});

test('formatAmount groups thousands and always keeps two decimals', () => {
  assert.equal(formatAmount(0), '0.00');
  assert.equal(formatAmount(7.5), '7.50');
  assert.equal(formatAmount(1234.5), '1,234.50');
  assert.equal(formatAmount(1_234_567.891), '1,234,567.89');
});

test('formatAmount keeps a sign for real negatives but not for negative zero', () => {
  assert.equal(formatAmount(-42.25), '-42.25');
  assert.equal(formatAmount(-0.001), '0.00');
});

test('formatMoney prefixes the grouped amount with a dollar sign', () => {
  assert.equal(formatMoney(1234.5), '$1,234.50');
  assert.equal(formatMoney(0), '$0.00');
});

test('formatMoney keeps a negative sign outside the currency symbol', () => {
  // `$-1,234.50` is what naive prefixing produces, and no ledger prints that.
  assert.equal(formatMoney(-1234.5), '-$1,234.50');
  assert.equal(formatMoney(-0.004), '$0.00');
});

test('formatMoney prints half cents rounded away from zero', () => {
  assert.equal(formatMoney(522.295), '$522.30');
  assert.equal(formatMoney(0.145), '$0.15');
  assert.equal(formatMoney(1.005), '$1.01');
  assert.equal(formatMoney(-2.675), '-$2.68');
  assert.equal(formatMoney(10_522.295), '$10,522.30');
});

test('padNumber zero-pads to the requested width', () => {
  assert.equal(padNumber(7), '00007');
  assert.equal(padNumber(7, 2), '07');
  // Values wider than the target are left alone rather than truncated.
  assert.equal(padNumber(123456, 3), '123456');
});

test('formatDate prints a locale-independent Mon DD, YYYY', () => {
  assert.equal(formatDate(new Date(2026, 0, 5)), 'Jan 05, 2026');
  assert.equal(formatDate(new Date(2025, 11, 31)), 'Dec 31, 2025');
});

test('addDays moves forwards and backwards without mutating the input', () => {
  const start = new Date(2026, 0, 5);
  assert.equal(formatDate(addDays(start, 30)), 'Feb 04, 2026');
  assert.equal(formatDate(addDays(start, -6)), 'Dec 30, 2025');
  assert.equal(formatDate(start), 'Jan 05, 2026');
});

test('addDays advances calendar dates across daylight saving transitions', () => {
  const originalTimeZone = process.env.TZ;
  process.env.TZ = 'America/New_York';

  try {
    const beforeFallBack = new Date(2026, 10, 1);
    assert.equal(formatDate(addDays(beforeFallBack, 1)), 'Nov 02, 2026');
  } finally {
    if (originalTimeZone === undefined) {
      delete process.env.TZ;
    } else {
      process.env.TZ = originalTimeZone;
    }
  }
});

test('formatRate renders a fraction as a percentage', () => {
  assert.equal(formatRate(0.0825), '8.25%');
  assert.equal(formatRate(0.0825, 1), '8.3%');
});

test('numberToWords covers zero, teens, tens, and every scale', () => {
  assert.equal(numberToWords(0), 'Zero');
  assert.equal(numberToWords(7), 'Seven');
  assert.equal(numberToWords(17), 'Seventeen');
  assert.equal(numberToWords(40), 'Forty');
  assert.equal(numberToWords(342), 'Three Hundred Forty Two');
  assert.equal(numberToWords(1000), 'One Thousand');
  assert.equal(numberToWords(1_234_567), 'One Million Two Hundred Thirty Four Thousand Five Hundred Sixty Seven');
  assert.equal(numberToWords(2_000_000_000), 'Two Billion');
});

test('amountInWords spells dollars and prints cents as a fraction', () => {
  assert.equal(amountInWords(1234.5), 'US Dollars One Thousand Two Hundred Thirty Four and 50/100 only');
  assert.equal(amountInWords(0), 'US Dollars Zero and 00/100 only');
  assert.equal(amountInWords(100.07), 'US Dollars One Hundred and 07/100 only');
  assert.equal(amountInWords(522.295), 'US Dollars Five Hundred Twenty Two and 30/100 only');
});
