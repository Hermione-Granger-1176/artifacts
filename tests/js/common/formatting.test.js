import assert from 'node:assert/strict';
import test from 'node:test';

import { formatDollarTick, parseNumber } from '../../../js/modules/formatting.js';

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
  assert.equal(parseNumber('abc'), 0);
  assert.equal(parseNumber('-$42'), -42);
});
