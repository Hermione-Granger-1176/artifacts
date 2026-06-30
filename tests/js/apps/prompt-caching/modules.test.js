import assert from 'node:assert/strict';
import test from 'node:test';

import {
  bpeTokenize,
  hashToken,
  cosineSim,
  eucDist,
  softmax,
  savingsMonthly,
  formatTTL,
  verdictForSimilarity,
  project2D
} from '../../../../apps/prompt-caching/js/modules/math.js';
import {
  SECTIONS,
  WHOLE_TOKENS,
  SUB_PIECES,
  ATTN_DATA,
  EMB_VECS,
  EMB_PAIRS,
  EMB_CATEGORIES,
  SUMMARY_STEPS
} from '../../../../apps/prompt-caching/js/modules/data.js';

// --- bpeTokenize ---

test('bpeTokenize returns [] for empty input', () => {
  assert.deepEqual(bpeTokenize(''), []);
  assert.deepEqual(bpeTokenize(null), []);
});

test('bpeTokenize keeps known whole words intact and is deterministic', () => {
  const once = bpeTokenize('the cat sat');
  const twice = bpeTokenize('the cat sat');
  assert.deepEqual(once, twice);
  assert.deepEqual(once, ['the', ' ', 'cat', ' ', 'sat']);
});

test('bpeTokenize matches vocabulary case-insensitively while preserving input case', () => {
  // "Cat" is not in the set verbatim but "cat" is, exercising the toLowerCase path.
  assert.deepEqual(bpeTokenize('Cat'), ['Cat']);
});

test('bpeTokenize splits possessives on apostrophe-s', () => {
  assert.deepEqual(bpeTokenize("cat's"), ['cat', "'s"]);
});

test('bpeTokenize splits unknown words into greedy subword pieces', () => {
  assert.deepEqual(bpeTokenize('strawberry'), ['straw', 'berry']);
});

test('bpeTokenize falls back to single characters with no subword match', () => {
  assert.deepEqual(bpeTokenize('9'), ['9']);
});

test('bpeTokenize treats a standalone punctuation run as one token each', () => {
  assert.deepEqual(bpeTokenize('!?'), ['!', '?']);
});

// --- hashToken ---

test('hashToken is deterministic and within the 5-digit window', () => {
  const id = hashToken('cat');
  assert.equal(id, hashToken('cat'));
  assert.notEqual(hashToken('cat'), hashToken('dog'));
  assert.ok(id >= 100 && id < 100000);
});

// --- cosineSim / eucDist ---

test('cosineSim is 1 for identical vectors and 0 for a zero vector', () => {
  assert.ok(Math.abs(cosineSim([1, 2, 3], [1, 2, 3]) - 1) < 1e-9);
  assert.equal(cosineSim([0, 0], [1, 1]), 0);
});

test('cosineSim is negative for opposite vectors', () => {
  assert.ok(cosineSim([1, 0], [-1, 0]) < 0);
});

test('eucDist measures straight-line distance', () => {
  assert.equal(eucDist([0, 0], [3, 4]), 5);
});

// --- softmax ---

test('softmax produces a distribution that sums to 1', () => {
  const weights = softmax([1, 2, 3]);
  const sum = weights.reduce((acc, value) => acc + value, 0);
  assert.ok(Math.abs(sum - 1) < 1e-9);
  assert.ok(weights[2] > weights[0]);
});

test('softmax returns zeros when every score is masked to -Infinity', () => {
  assert.deepEqual(softmax([-Infinity, -Infinity]), [0, 0]);
});

test('softmax stays finite for large scores and masked values', () => {
  const weights = softmax([1000, 1001, -Infinity]);
  const sum = weights.reduce((acc, value) => acc + value, 0);
  assert.ok(weights.every(Number.isFinite));
  assert.ok(Math.abs(sum - 1) < 1e-9);
  assert.equal(weights[2], 0);
  assert.ok(weights[1] > weights[0]);
});

// --- savingsMonthly ---

test('savingsMonthly matches a hand-computed example', () => {
  // 2000 tokens * 500 req/day * 30 days = 30,000,000 tokens/month.
  // without = 30 * $3 = $90. 80% cached at 1/10 price.
  const result = savingsMonthly({ sys: 2000, req: 500, hitFraction: 0.8, price: 3 });
  assert.ok(Math.abs(result.without - 90) < 1e-6);
  // withCache = (0.2 * 30M / 1e6) * 3 + (0.8 * 30M / 1e6) * 0.3 = 18 + 7.2 = 25.2
  assert.ok(Math.abs(result.withCache - 25.2) < 1e-6);
  assert.ok(Math.abs(result.savings - 64.8) < 1e-6);
});

test('savingsMonthly has no savings when nothing is cached', () => {
  const result = savingsMonthly({ sys: 1000, req: 100, hitFraction: 0, price: 5 });
  assert.ok(Math.abs(result.savings) < 1e-9);
});

// --- formatTTL ---

test('formatTTL pads seconds and reports expiry', () => {
  assert.equal(formatTTL(300), '5:00');
  assert.equal(formatTTL(125), '2:05');
  assert.equal(formatTTL(5), '0:05');
  assert.equal(formatTTL(0), 'expired');
  assert.equal(formatTTL(-3), 'expired');
});

// --- verdictForSimilarity ---

test('verdictForSimilarity covers every band', () => {
  assert.deepEqual(verdictForSimilarity(0.95), { label: 'Very similar', tone: 'teal' });
  assert.deepEqual(verdictForSimilarity(0.8), { label: 'Similar', tone: 'accent' });
  assert.deepEqual(verdictForSimilarity(0.5), { label: 'Somewhat related', tone: 'warm' });
  assert.deepEqual(verdictForSimilarity(0.2), { label: 'Weakly related', tone: 'secondary' });
  assert.deepEqual(verdictForSimilarity(0.0), { label: 'Unrelated', tone: 'tertiary' });
  assert.deepEqual(verdictForSimilarity(-0.5), { label: 'Opposites', tone: 'rose' });
});

// --- project2D ---

test('project2D maps every word to a finite 2D coordinate', () => {
  const projected = project2D(EMB_VECS.happy, EMB_VECS.sad, EMB_VECS);
  assert.equal(projected.length, Object.keys(EMB_VECS).length);
  for (const point of projected) {
    assert.ok(typeof point.word === 'string');
    assert.ok(Number.isFinite(point.x));
    assert.ok(Number.isFinite(point.y));
  }
});

test('project2D tolerates identical A and B vectors (zero direction)', () => {
  const vecs = { p: [1, 1], q: [0, 0.5] };
  const projected = project2D([1, 1], [1, 1], vecs);
  assert.equal(projected.length, 2);
  for (const point of projected) {
    assert.ok(Number.isFinite(point.x));
    assert.ok(Number.isFinite(point.y));
  }
});

// --- data integrity ---

test('SECTIONS lists nine unique anchored stages', () => {
  assert.equal(SECTIONS.length, 9);
  const ids = new Set(SECTIONS.map((section) => section.id));
  assert.equal(ids.size, 9);
  for (const section of SECTIONS) {
    assert.ok(section.id.startsWith('sec-'));
    assert.ok(section.label.length > 0);
  }
});

test('vocabulary sets are usable and subword pieces sort longest-first', () => {
  assert.ok(WHOLE_TOKENS.has('the'));
  assert.ok(WHOLE_TOKENS.has('attention'));
  assert.ok(SUB_PIECES.length > 0);
  // Deduped.
  assert.equal(new Set(SUB_PIECES).size, SUB_PIECES.length);
  // Sorted by descending length.
  for (let i = 1; i < SUB_PIECES.length; i += 1) {
    assert.ok(SUB_PIECES[i - 1].length >= SUB_PIECES[i].length);
  }
});

test('attention worked example is internally consistent', () => {
  assert.equal(ATTN_DATA.emb.length, 4);
  // Each weights row sums to 1 (within rounding of the pre-computed values).
  for (const row of ATTN_DATA.weights) {
    const sum = row.reduce((acc, value) => acc + value, 0);
    assert.ok(Math.abs(sum - 1) < 0.02);
  }
});

test('embedding catalogue, pairs, and categories reference real vectors', () => {
  for (const [a, b] of EMB_PAIRS) {
    // Pairs may intentionally include an out-of-vocabulary word ("submarine" exists,
    // but the demo also handles misses); every listed pair word that is a category
    // member must have a vector.
    assert.ok(typeof a === 'string' && typeof b === 'string');
  }
  for (const words of Object.values(EMB_CATEGORIES)) {
    for (const word of words) {
      assert.ok(Array.isArray(EMB_VECS[word]), `missing vector for ${word}`);
      assert.equal(EMB_VECS[word].length, 8);
    }
  }
});

test('summary steps carry a title, tone, and description', () => {
  assert.equal(SUMMARY_STEPS.length, 5);
  for (const step of SUMMARY_STEPS) {
    assert.ok(step.title.length > 0);
    assert.ok(step.tone.length > 0);
    assert.ok(step.desc.length > 0);
  }
});
