/**
 * Seeded pseudo-random helpers.
 *
 * Every random choice inside a generated document is a pure function of one
 * integer seed. The preview, the PNG, the text PDF, and the batch entry for a
 * given seed and reference date therefore match. `Math.random()` is not used
 * during document construction. It is used only when `rollSeed` chooses a new
 * document and when `planBatch` uses its default seed and style sources.
 *
 * @module random
 */

const MODULUS = 2_147_483_647;
const MULTIPLIER = 16_807;

/**
 * How many draws to discard before handing the stream to a caller.
 *
 * A raw Lehmer generator seeded with a small integer returns a small first
 * value. Discarding the first few draws spreads neighbouring seeds across the
 * whole interval.
 */
const WARMUP_DRAWS = 4;

/**
 * Build a Lehmer generator over the given seed.
 * @param {number} seed - Any integer; normalised into the generator's range.
 * @returns {() => number} Function returning successive values in (0, 1).
 */
export function createSeededRandom(seed) {
  let state = Math.trunc(Math.abs(seed)) % MODULUS;

  if (state <= 0) {
    state += MODULUS - 1;
  }

  const next = () => {
    state = (state * MULTIPLIER) % MODULUS;
    return state / MODULUS;
  };

  for (let index = 0; index < WARMUP_DRAWS; index += 1) {
    next();
  }

  return next;
}

/**
 * Pick an inclusive integer in `[min, max]` from a seed.
 * @param {number} seed - Seed for the draw.
 * @param {number} min - Lowest allowed value.
 * @param {number} max - Highest allowed value.
 * @returns {number} Integer within the range.
 */
export function pickCount(seed, min, max) {
  const draw = createSeededRandom(seed + 701)();
  return min + Math.floor(draw * (max - min + 1));
}

/**
 * Pick an element from a list using a seed.
 * @template T
 * @param {readonly T[]} items - Non-empty list to choose from.
 * @param {number} seed - Seed driving the choice.
 * @returns {T} The chosen element.
 */
export function pickFrom(items, seed) {
  return items[Math.abs(Math.trunc(seed)) % items.length];
}

/**
 * Produce a shuffled index list, used to reorder line items between documents
 * that draw on the same catalogue.
 * @param {number} length - Number of indices to shuffle.
 * @param {() => number} random - Source of randomness.
 * @returns {number[]} Indices `0..length-1` in shuffled order.
 */
export function shuffleIndices(length, random) {
  const order = Array.from({ length }, (_value, index) => index);

  for (let index = order.length - 1; index > 0; index -= 1) {
    const swap = Math.floor(random() * (index + 1));
    [order[index], order[swap]] = [order[swap], order[index]];
  }

  return order;
}

/**
 * Roll a fresh document seed.
 * @param {() => number} [randomSource=Math.random] - Injectable for tests.
 * @returns {number} An integer from 1,000 to 900,999.
 */
export function rollSeed(randomSource = Math.random) {
  return Math.floor(randomSource() * 900_000) + 1_000;
}
