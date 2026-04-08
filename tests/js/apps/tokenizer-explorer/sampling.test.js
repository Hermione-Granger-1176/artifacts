import assert from 'node:assert/strict';
import test from 'node:test';

import { softmax, buildTopPSelection } from '../../../../apps/tokenizer-explorer/js/modules/sampling.js';

test('softmax returns valid probability distribution', () => {
  const probs = softmax([1.0, 2.0, 3.0], 1.0);
  assert.equal(probs.length, 3);
  const sum = probs.reduce((a, b) => a + b, 0);
  assert.ok(Math.abs(sum - 1.0) < 1e-6, `sum should be ~1.0, got ${sum}`);
  // Higher logit should have higher probability
  assert.ok(probs[2] > probs[1]);
  assert.ok(probs[1] > probs[0]);
});

test('softmax handles zero temperature without producing NaN or Infinity', () => {
  const probs = softmax([1.0, 2.0, 3.0], 0);
  assert.equal(probs.length, 3);
  assert.ok(probs.every((p) => Number.isFinite(p)), 'all probabilities must be finite');
  const sum = probs.reduce((a, b) => a + b, 0);
  assert.ok(Math.abs(sum - 1.0) < 1e-6, `sum should be ~1.0, got ${sum}`);
});

test('softmax handles very small temperature', () => {
  const probs = softmax([1.0, 2.0, 3.0], 0.001);
  assert.ok(probs.every((p) => Number.isFinite(p)));
  // Highest logit should dominate
  assert.ok(probs[2] > 0.99);
});

test('buildTopPSelection produces a valid selection', () => {
  const tokens = [
    { token: 'A', baseLogit: 3.0 },
    { token: 'B', baseLogit: 1.0 },
    { token: 'C', baseLogit: 0.5 }
  ];
  const result = buildTopPSelection(tokens, 1.0, 0.9);
  assert.ok(Array.isArray(result.sorted));
  assert.ok(result.sorted.length > 0);
  assert.ok(result.inTopP instanceof Set);
  assert.ok(result.inTopP.size > 0);
  assert.ok(result.topTokenProbability > 0);
});
