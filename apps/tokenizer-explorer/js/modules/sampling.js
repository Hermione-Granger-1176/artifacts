export function softmax(logits, temperature) {
  const scaled = logits.map((logit) => logit / temperature);
  const maxLogit = Math.max(...scaled);
  const exponentials = scaled.map((logit) => Math.exp(logit - maxLogit));
  const total = exponentials.reduce((sum, value) => sum + value, 0);
  return exponentials.map((value) => value / total);
}

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
