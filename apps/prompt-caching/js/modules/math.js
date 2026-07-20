/* Pure, framework-free math for the Prompt Caching explainer.
 *
 * Every export is a deterministic function with no DOM access, so the demos'
 * numerical behavior can be unit-tested directly.
 */

import { WHOLE_TOKENS, SUB_PIECES } from "./data.js";

/* GPT-2-style pre-tokenization: contractions split off, a single leading space
 * attaches to the following word/number/punctuation run, and whitespace runs
 * keep their last space for the next word. */
const GPT_SPLIT_RE = /'(?:[sdmt]|ll|ve|re)| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+/gu;

/**
 * Greedy BPE-style tokenizer with GPT-2-style pre-tokenization: leading spaces
 * attach to the following token, contractions ('s, 'll, ...) become their own
 * tokens, digit runs chunk into groups of three, known whole words stay intact,
 * and unknown words split into the longest matching subword pieces (falling
 * back to single characters).
 * @param {string} text
 * @returns {string[]} ordered tokens (whitespace-run tokens included)
 */
export function bpeTokenize(text) {
  if (!text) {
    return [];
  }

  const tokens = [];

  for (const part of text.match(GPT_SPLIT_RE) || []) {
    if (/^\s+$/.test(part)) {
      tokens.push(part);
      continue;
    }

    if (/^ ?[^\s\p{L}\p{N}]/u.test(part)) {
      tokens.push(part);
      continue;
    }

    const space = part.startsWith(" ") ? " " : "";
    const core = space ? part.slice(1) : part;

    if (/^\p{N}+$/u.test(core)) {
      for (let i = 0; i < core.length; i += 3) {
        tokens.push((i === 0 ? space : "") + core.slice(i, i + 3));
      }
      continue;
    }

    if (WHOLE_TOKENS.has(core) || WHOLE_TOKENS.has(core.toLowerCase())) {
      tokens.push(part);
      continue;
    }

    let i = 0;
    let first = true;
    const lower = core.toLowerCase();
    while (i < core.length) {
      let matched = false;
      for (const piece of SUB_PIECES) {
        if (i + piece.length <= core.length && lower.slice(i, i + piece.length) === piece) {
          tokens.push((first ? space : "") + core.slice(i, i + piece.length));
          i += piece.length;
          matched = true;
          first = false;
          break;
        }
      }
      if (!matched) {
        tokens.push((first ? space : "") + core[i]);
        i += 1;
        first = false;
      }
    }
  }

  return tokens;
}

/**
 * Deterministic djb2-style hash mapped into a 5-digit pseudo token ID.
 * @param {string} value
 * @returns {number}
 */
export function hashToken(value) {
  let h = 5381;
  for (let i = 0; i < value.length; i += 1) {
    h = ((h << 5) + h + value.charCodeAt(i)) & 0x7fffffff;
  }
  return 100 + (h % 99900);
}

/**
 * Cosine similarity between two equal-length vectors. Returns 0 when either
 * vector has zero magnitude.
 * @param {number[]} a - First vector.
 * @param {number[]} b - Second vector.
 * @returns {number} Cosine similarity.
 */
export function cosineSim(a, b) {
  let dot = 0;
  let magA = 0;
  let magB = 0;
  for (let i = 0; i < a.length; i += 1) {
    dot += a[i] * b[i];
    magA += a[i] * a[i];
    magB += b[i] * b[i];
  }
  const denom = Math.sqrt(magA) * Math.sqrt(magB);
  return denom === 0 ? 0 : dot / denom;
}

/**
 * Euclidean distance between two equal-length vectors.
 * @param {number[]} a - First vector.
 * @param {number[]} b - Second vector.
 * @returns {number} Euclidean distance.
 */
export function eucDist(a, b) {
  let sum = 0;
  for (let i = 0; i < a.length; i += 1) {
    sum += (a[i] - b[i]) ** 2;
  }
  return Math.sqrt(sum);
}

/**
 * Numerically stable softmax over raw scores. `-Infinity` scores map to weight 0
 * (used by the causal mask). Always sums to ~1 when at least one score is finite.
 * @param {number[]} scores - Raw scores.
 * @returns {number[]} Softmax weights.
 */
export function softmax(scores) {
  const finiteScores = scores.filter(Number.isFinite);
  if (finiteScores.length === 0) {
    return scores.map(() => 0);
  }
  const maxScore = Math.max(...finiteScores);
  const exps = scores.map((s) => (Number.isFinite(s) ? Math.exp(s - maxScore) : 0));
  const sum = exps.reduce((acc, value) => acc + value, 0);
  if (sum === 0) {
    return scores.map(() => 0);
  }
  return exps.map((value) => value / sum);
}

/**
 * Monthly spend with and without prompt caching for a steady workload.
 * @param {{sys:number, req:number, hitFraction:number, price:number}} params
 * @returns {{without:number, withCache:number, savings:number}} dollars/month
 */
export function savingsMonthly({ sys, req, hitFraction, price }) {
  const tokensPerMonth = sys * req * 30;
  const without = (tokensPerMonth / 1e6) * price;
  const cached = tokensPerMonth * hitFraction;
  const uncached = tokensPerMonth * (1 - hitFraction);
  const withCache = (uncached / 1e6) * price + (cached / 1e6) * (price / 10);
  return { without, withCache, savings: without - withCache };
}

/**
 * Format a remaining-seconds count as `m:ss`, or "expired" once it runs out.
 * @param {number} seconds - Remaining seconds.
 * @returns {string} Formatted time.
 */
export function formatTTL(seconds) {
  if (seconds <= 0) {
    return "expired";
  }
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/**
 * Human verdict + accent tone for a cosine similarity score.
 * @param {number} sim - Cosine similarity score.
 * @returns {{label:string, tone:string}}
 */
export function verdictForSimilarity(sim) {
  if (sim > 0.9) {
    return { label: "Very similar", tone: "teal" };
  }
  if (sim > 0.7) {
    return { label: "Similar", tone: "accent" };
  }
  if (sim > 0.4) {
    return { label: "Somewhat related", tone: "warm" };
  }
  if (sim > 0.1) {
    return { label: "Weakly related", tone: "secondary" };
  }
  if (sim > -0.2) {
    return { label: "Unrelated", tone: "tertiary" };
  }
  return { label: "Opposites", tone: "rose" };
}

/**
 * Project every word vector onto two axes chosen to best separate words A and B:
 * axis 1 is the A→B direction, axis 2 is the highest-variance orthogonal axis.
 * @param {number[]} vecA
 * @param {number[]} vecB
 * @param {Record<string, number[]>} vecs all word vectors keyed by word
 * @returns {{word:string, x:number, y:number}[]}
 */
export function project2D(vecA, vecB, vecs) {
  const words = Object.keys(vecs);
  const dims = vecA.length;

  const diff = vecA.map((value, i) => vecB[i] - value);
  const diffMag = Math.sqrt(diff.reduce((sum, value) => sum + value * value, 0)) || 1;
  const ax1 = diff.map((value) => value / diffMag);

  const ax2 = new Array(dims).fill(0);
  let bestDim = 0;
  let bestVar = 0;
  for (let d = 0; d < dims; d += 1) {
    const mean = words.reduce((sum, word) => sum + vecs[word][d], 0) / words.length;
    let variance = 0;
    for (const word of words) {
      variance += (vecs[word][d] - mean) ** 2;
    }
    const adjusted = variance * (1 - ax1[d] * ax1[d]);
    if (adjusted > bestVar) {
      bestVar = adjusted;
      bestDim = d;
    }
  }
  ax2[bestDim] = 1;

  const dot12 = ax1.reduce((sum, value, i) => sum + value * ax2[i], 0);
  for (let i = 0; i < dims; i += 1) {
    ax2[i] -= dot12 * ax1[i];
  }
  const mag2 = Math.sqrt(ax2.reduce((sum, value) => sum + value * value, 0)) || 1;
  for (let i = 0; i < dims; i += 1) {
    ax2[i] /= mag2;
  }

  return words.map((word) => ({
    word,
    x: vecs[word].reduce((sum, value, i) => sum + value * ax1[i], 0),
    y: vecs[word].reduce((sum, value, i) => sum + value * ax2[i], 0)
  }));
}
