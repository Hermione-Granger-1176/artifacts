import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildTopPSelection,
  drawToken,
  softmax,
  tallyDraws
} from '../../../../apps/tokenizer-explorer/js/modules/sampling.js';
import { scenarios } from '../../../../apps/tokenizer-explorer/js/modules/scenarios.js';

test('softmax returns a normalized distribution ordered by logit', () => {
  const probabilities = softmax([1, 2, 3], 1);
  assert.equal(probabilities.length, 3);
  assert.ok(Math.abs(probabilities.reduce((sum, value) => sum + value, 0) - 1) < 1e-12);
  assert.ok(probabilities[2] > probabilities[1]);
  assert.ok(probabilities[1] > probabilities[0]);
});

test('softmax returns an empty distribution for no logits', () => {
  assert.deepEqual(softmax([], 1), []);
});

test('temperature zero uses greedy decoding with a stable tie break', () => {
  assert.deepEqual(softmax([1, 3, 2], 0), [0, 1, 0]);
  assert.deepEqual(softmax([3, 3, 1], 0), [1, 0, 0]);
});

test('very small positive temperatures still sharpen without NaN values', () => {
  const probabilities = softmax([1, 2, 3], 0.001);
  assert.ok(probabilities.every(Number.isFinite));
  assert.ok(probabilities[2] > 0.99);
});

test('top-p selection renormalizes the retained nucleus and zeros exclusions', () => {
  const tokens = [
    { word: 'A', baseLogit: 2 },
    { word: 'B', baseLogit: 1 },
    { word: 'C', baseLogit: 0 }
  ];
  const result = buildTopPSelection(tokens, 1, 0.9);

  assert.deepEqual(result.topTokens.map((token) => token.word), ['A', 'B']);
  assert.ok(result.retainedProbabilityMass > 0.9);
  assert.ok(result.retainedProbabilityMass < 1);
  assert.ok(Math.abs(result.topTokens.reduce((sum, token) => sum + token.adjustedProb, 0) - 1) < 1e-12);
  assert.equal(result.sorted.find((token) => token.word === 'C')?.adjustedProb, 0);
});

test('top-p selection at temperature zero retains only the greedy token', () => {
  const result = buildTopPSelection(
    [
      { word: 'top', baseLogit: 5 },
      { word: 'tail', baseLogit: 1 }
    ],
    0,
    1
  );

  assert.equal(result.topTokens.length, 1);
  assert.equal(result.topTokens[0].word, 'top');
  assert.equal(result.topTokens[0].adjustedProb, 1);
});

test('default scenario matches the hand-checked temperature and top-p percentages', () => {
  const result = buildTopPSelection(scenarios[0].tokens, 1, 0.7);
  const mat = result.sorted.find((token) => token.word === 'mat');
  const floor = result.sorted.find((token) => token.word === 'floor');

  assert.ok(Math.abs((mat?.prob ?? 0) - 0.6427) < 0.001);
  assert.ok(Math.abs((floor?.prob ?? 0) - 0.2139) < 0.001);
  assert.deepEqual(result.topTokens.map((token) => token.word), ['mat', 'floor']);
  assert.ok(Math.abs((mat?.adjustedProb ?? 0) - 0.7503) < 0.001);
  assert.ok(Math.abs((floor?.adjustedProb ?? 0) - 0.2497) < 0.001);
});

test('drawToken follows injected random rolls and rejects an empty distribution', () => {
  const tokens = [
    { idx: 1, adjustedProb: 0.7 },
    { idx: 2, adjustedProb: 0.3 }
  ];
  assert.equal(drawToken(tokens, () => 0).idx, 1);
  assert.equal(drawToken(tokens, () => 0.699).idx, 1);
  assert.equal(drawToken(tokens, () => 0.7).idx, 2);
  assert.equal(drawToken(tokens, () => 1).idx, 2);
  assert.throws(() => drawToken([], () => 0), /empty token distribution/);
});

test('tallyDraws aggregates deterministic sampled token counts', () => {
  const rolls = [0.1, 0.2, 0.8, 0.9, 0.4];
  let index = 0;
  const tallies = tallyDraws(
    [
      { idx: 3, adjustedProb: 0.6 },
      { idx: 4, adjustedProb: 0.4 }
    ],
    rolls.length,
    () => rolls[index++]
  );

  assert.equal(tallies.get(3), 3);
  assert.equal(tallies.get(4), 2);
  assert.equal([...tallies.values()].reduce((sum, count) => sum + count, 0), rolls.length);
});
