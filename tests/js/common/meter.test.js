import test from 'node:test';
import assert from 'node:assert/strict';

import { setMeterValue } from '../../../js/modules/meter.js';

function createFill() {
  return { style: { scale: '' } };
}

test('setMeterValue scales the fill by the fraction', () => {
  const fill = createFill();
  assert.equal(setMeterValue(fill, 0.4), 0.4);
  assert.equal(fill.style.scale, '0.4 1');
});

test('setMeterValue clamps out-of-range and non-finite fractions', () => {
  const fill = createFill();
  assert.equal(setMeterValue(fill, 1.7), 1);
  assert.equal(fill.style.scale, '1 1');
  assert.equal(setMeterValue(fill, -3), 0);
  assert.equal(fill.style.scale, '0 1');
  assert.equal(setMeterValue(fill, Number.NaN), 0);
  assert.equal(setMeterValue(fill, Infinity), 0);
});
