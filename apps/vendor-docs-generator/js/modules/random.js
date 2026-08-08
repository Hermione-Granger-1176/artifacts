/**
 * Seeded pseudo-random helpers.
 *
 * Every generated document is a pure function of one integer seed, so the
 * preview, the PNG, the text PDF, and the batch entry for a given seed all
 * agree. That rules out `Math.random()` anywhere inside document construction;
 * it is confined to `rollSeed`, which is the only place a new document is
 * chosen.
 *
 * @module random
 */

const MODULUS = 2_147_483_647;
const MULTIPLIER = 16_807;

/**
 * How many draws to discard before handing the stream to a caller.
 *
 * A raw Lehmer generator seeded with a small integer opens with a
 * correspondingly small value: seeds 907, 938 and 969 return 0.0071, 0.0073 and
 * 0.0076. Any caller that reads the first draw as a probability therefore takes
 * the same branch for every small seed, which is how a `random() < 0.2` freight
 * check managed to return "carriage paid" every single time. Discarding the
 * first few draws decorrelates the opening of the stream; four is enough to
 * scatter neighbouring seeds across the whole interval.
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
 * Produce a shuffled index list, so line items appear in a different order
 * from one document to the next even when they come from the same catalogue.
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
 * @returns {number} A six-digit-ish seed.
 */
export function rollSeed(randomSource = Math.random) {
  return Math.floor(randomSource() * 900_000) + 1_000;
}
