/**
 * Convert raw logits into normalized probabilities at one temperature.
 *
 * @param {number[]} logits
 * @param {number} temperature
 * @returns {number[]}
 */
export function softmax(logits, temperature) {
  const safeTemp = Math.max(temperature, 1e-8);
  const scaled = logits.map((logit) => logit / safeTemp);
  const maxLogit = Math.max(...scaled);
  const exponentials = scaled.map((logit) => Math.exp(logit - maxLogit));
  const total = exponentials.reduce((sum, value) => sum + value, 0);
  return exponentials.map((value) => value / total);
}

/**
 * Build the sorted token distribution and the cumulative top-p selection set.
 *
 * @param {{ word: string, baseLogit: number }[]} tokens
 * @param {number} temperature
 * @param {number} topP
 * @returns {{
 *   sorted: Array<{ word: string, baseLogit: number, idx: number, prob: number }>,
 *   inTopP: Set<number>,
 *   topTokens: Array<{ word: string, baseLogit: number, idx: number, prob: number }>,
 *   topTokenProbability: number
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

  const topTokens = sorted.filter((token) => inTopP.has(token.idx));
  const topTokenProbability = topTokens.reduce((sum, token) => sum + token.prob, 0);

  return {
    sorted,
    inTopP,
    topTokens,
    topTokenProbability
  };
}
