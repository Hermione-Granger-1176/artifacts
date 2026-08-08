import assert from 'node:assert/strict';
import test from 'node:test';

import {
  createSeededRandom,
  pickCount,
  pickFrom,
  rollSeed,
  shuffleIndices
} from '../../../../apps/vendor-docs-generator/js/modules/random.js';

test('createSeededRandom is deterministic for a given seed', () => {
  const first = createSeededRandom(4242);
  const second = createSeededRandom(4242);
  const draws = Array.from({ length: 8 }, () => first());
  assert.deepEqual(draws, Array.from({ length: 8 }, () => second()));
});

test('createSeededRandom stays inside the open unit interval', () => {
  const random = createSeededRandom(99);

  for (let index = 0; index < 500; index += 1) {
    const value = random();
    assert.ok(value > 0 && value < 1, `draw ${value} left the unit interval`);
  }
});

test('createSeededRandom normalises seeds that would stall the generator', () => {
  // A zero state would be a fixed point, so it has to be lifted into range.
  for (const seed of [0, -0, 2_147_483_647]) {
    const value = createSeededRandom(seed)();
    assert.ok(value > 0 && value < 1, `seed ${seed} produced ${value}`);
  }
});

test('createSeededRandom treats negative seeds as their magnitude', () => {
  assert.equal(createSeededRandom(-1234)(), createSeededRandom(1234)());
});

test('pickCount stays within the inclusive range and repeats for a seed', () => {
  for (let seed = 1; seed < 400; seed += 1) {
    const count = pickCount(seed, 3, 6);
    assert.ok(count >= 3 && count <= 6, `seed ${seed} gave ${count}`);
    assert.equal(count, pickCount(seed, 3, 6));
  }
});

test('pickCount can return a single fixed value', () => {
  assert.equal(pickCount(12, 4, 4), 4);
});

test('pickFrom indexes by seed and handles negatives', () => {
  const items = ['a', 'b', 'c'];
  assert.equal(pickFrom(items, 0), 'a');
  assert.equal(pickFrom(items, 4), 'b');
  assert.equal(pickFrom(items, -4), 'b');
});

test('shuffleIndices returns a permutation of every index', () => {
  const random = createSeededRandom(7);
  const order = shuffleIndices(6, random);
  assert.equal(order.length, 6);
  assert.deepEqual([...order].sort((a, b) => a - b), [0, 1, 2, 3, 4, 5]);
});

test('shuffleIndices actually reorders for at least some seeds', () => {
  const shuffled = [1, 2, 3, 4, 5].map((seed) =>
    shuffleIndices(6, createSeededRandom(seed)).join('')
  );
  assert.ok(
    shuffled.some((order) => order !== '012345'),
    'every seed left the catalogue in its original order'
  );
});

test('shuffleIndices handles the degenerate single-element case', () => {
  assert.deepEqual(shuffleIndices(1, createSeededRandom(3)), [0]);
});

test('rollSeed draws from the injected source and stays in range', () => {
  assert.equal(rollSeed(() => 0), 1000);
  assert.equal(rollSeed(() => 0.5), 451_000);
  const natural = rollSeed();
  assert.ok(natural >= 1000 && natural < 901_000, `seed ${natural} left the range`);
});
