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
  assert.equal(roundCents(1234.5678), 1234.57);
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
});
