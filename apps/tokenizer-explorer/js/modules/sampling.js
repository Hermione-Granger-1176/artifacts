/**
 * Return a one-hot distribution for greedy decoding. Ties resolve to the
 * first highest logit, matching the stable order of the scenario data.
 *
 * @param {number[]} logits
 * @returns {number[]}
 */
function greedyProbabilities(logits) {
  const highest = Math.max(...logits);
  const winnerIndex = logits.findIndex((logit) => logit === highest);
  return logits.map((_logit, index) => (index === winnerIndex ? 1 : 0));
}

/**
 * Convert raw logits into normalized probabilities at one temperature.
 * Temperature zero is greedy decoding, so it returns a one-hot distribution
 * instead of attempting to divide logits by zero.
 *
 * @param {number[]} logits
 * @param {number} temperature
 * @returns {number[]}
 */
export function softmax(logits, temperature) {
  if (logits.length === 0) {
    return [];
  }
  if (temperature <= 0) {
    return greedyProbabilities(logits);
  }

  const scaled = logits.map((logit) => logit / temperature);
  const maxLogit = Math.max(...scaled);
  const exponentials = scaled.map((logit) => Math.exp(logit - maxLogit));
  const total = exponentials.reduce((sum, value) => sum + value, 0);
  return exponentials.map((value) => value / total);
}

/**
 * Build the sorted distribution, retain the smallest top-p nucleus, and
 * renormalize its probabilities for the distribution that sampling uses.
 *
 * @param {{ word: string, baseLogit: number }[]} tokens
 * @param {number} temperature
 * @param {number} topP
 * @returns {{
 *   sorted: Array<{ word: string, baseLogit: number, idx: number, prob: number, adjustedProb: number }>,
 *   inTopP: Set<number>,
 *   topTokens: Array<{ word: string, baseLogit: number, idx: number, prob: number, adjustedProb: number }>,
 *   retainedProbabilityMass: number
 * }}
 */
export function buildTopPSelection(tokens, temperature, topP) {
  const logits = tokens.map((token) => token.baseLogit);
  const probabilities = softmax(logits, temperature);
  const indexed = tokens.map((token, index) => ({ ...token, prob: probabilities[index], idx: index }));
  const sorted = [...indexed].sort((left, right) => right.prob - left.prob);

  let cumulative = 0;
  const inTopP = new Set();
  for (const token of sorted) {
    inTopP.add(token.idx);
    cumulative += token.prob;
    if (cumulative >= topP) {
      break;
    }
  }

  const retainedProbabilityMass = cumulative;
  const adjustedSorted = sorted.map((token) => ({
    ...token,
    adjustedProb: inTopP.has(token.idx) ? token.prob / retainedProbabilityMass : 0
  }));
  const topTokens = adjustedSorted.filter((token) => inTopP.has(token.idx));

  return {
    sorted: adjustedSorted,
    inTopP,
    topTokens,
    retainedProbabilityMass
  };
}

/**
 * Draw one token from a renormalized probability distribution.
 *
 * @template T
 * @param {Array<T & { adjustedProb: number }>} tokens
 * @param {() => number} [random=Math.random]
 * @returns {T}
 */
export function drawToken(tokens, random = Math.random) {
  if (tokens.length === 0) {
    throw new Error("Cannot draw from an empty token distribution.");
  }

  const roll = random();
  let cumulative = 0;
  for (const token of tokens) {
    cumulative += token.adjustedProb;
    if (roll < cumulative) {
      return token;
    }
  }

  return tokens[tokens.length - 1];
}

/**
 * Draw repeatedly and return a count keyed by each token's stable index.
 * The injectable random callback makes demonstrations and tests reproducible.
 *
 * @param {Array<{ idx: number, adjustedProb: number }>} tokens
 * @param {number} drawCount
 * @param {() => number} [random=Math.random]
 * @returns {Map<number, number>}
 */
export function tallyDraws(tokens, drawCount, random = Math.random) {
  const tallies = new Map(tokens.map((token) => [token.idx, 0]));
  for (let draw = 0; draw < drawCount; draw += 1) {
    const token = drawToken(tokens, random);
    tallies.set(token.idx, (tallies.get(token.idx) ?? 0) + 1);
  }
  return tallies;
}
