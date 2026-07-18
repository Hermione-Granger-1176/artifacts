import assert from 'node:assert/strict';
import test from 'node:test';

import { formatCurrency, formatDollarTick, parseNumber } from '../../../js/modules/formatting.js';

test('formatCurrency rounds to whole dollars by default', () => {
  assert.equal(formatCurrency(1234), '$1,234');
  assert.equal(formatCurrency(99.7), '$100');
});

test('formatCurrency honors an explicit fraction-digit count', () => {
  assert.equal(formatCurrency(1234.5, 2), '$1,234.50');
  assert.equal(formatCurrency(1234.567, 2), '$1,234.57');
});

test('formatCurrency handles negative, zero, and large values', () => {
  assert.equal(formatCurrency(-42), '-$42');
  assert.equal(formatCurrency(-1234.5, 2), '-$1,234.50');
  assert.equal(formatCurrency(0), '$0');
  assert.equal(formatCurrency(1234567), '$1,234,567');
});

test('formatDollarTick handles millions, thousands, and small values', () => {
  assert.equal(formatDollarTick(2500000), '$2.5M');
  assert.equal(formatDollarTick(50000), '$50k');
  assert.equal(formatDollarTick(1500), '$1.5k');
  assert.equal(formatDollarTick(500), '$500');
  assert.equal(formatDollarTick(-50000), '-$50k');
  assert.equal(formatDollarTick(0), '$0');
});

test('parseNumber strips non-numeric characters', () => {
  assert.equal(parseNumber('$1,234.56'), 1234.56);
  assert.equal(parseNumber('-$42'), -42);
});

test('parseNumber returns 0 when nothing numeric remains', () => {
  assert.equal(parseNumber('abc'), 0);
  assert.equal(parseNumber(''), 0);
  assert.equal(parseNumber('-'), 0);
});
