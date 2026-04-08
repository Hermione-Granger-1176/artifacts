function css(propertyName) {
  return getComputedStyle(document.documentElement).getPropertyValue(propertyName).trim();
}

function alphaColor(color, alpha) {
  const matches = color.match(/\d+/g);
  if (!matches || matches.length < 3) {
    return color;
  }
  return `rgba(${matches[0]}, ${matches[1]}, ${matches[2]}, ${alpha})`;
}

function palette() {
  return [
    css("--color-blue"),
    css("--color-green"),
    css("--color-amber"),
    css("--note-red"),
    css("--color-purple"),
    css("--note-amber"),
    css("--note-purple"),
    css("--color-text-tertiary")
  ];
}

function temperatureInsight(winner, temperature) {
  const value = temperature.toFixed(1);
  if (temperature <= 0.3) {
    return `At temperature ${value}, the model is almost deterministic. "${winner.word}" wins nearly every time. Great for code or facts where consistency matters.`;
  }
  if (temperature >= 2.0) {
    return `At temperature ${value}, probability spreads out widely. Unusual tokens become real contenders. Useful for creative tasks, risky for factual ones.`;
  }
  return `At temperature ${value}, "${winner.word}" is the favourite but there is real variety. A solid balance between coherence and surprise.`;
}

function topPInsight(topP, tokenCount) {
  const value = topP.toFixed(2);
  if (topP <= 0.1) {
    return ` Top P=${value} is very tight. Only the single most likely token makes the cut.`;
  }
  if (topP <= 0.5) {
    return ` Top P=${value} keeps a small, high-confidence pool. Only the safest tokens are in play.`;
  }
  if (topP >= 0.99) {
    return ` Top P=${value} is wide enough that nearly every token stays in play. Temperature does most of the shaping here.`;
  }
  return ` Top P=${value} keeps ${tokenCount} token${tokenCount !== 1 ? "s" : ""} whose cumulative probability reaches that threshold.`;
}

/**
 * Render the scenario tabs and wire each button to the provided selection callback.
 *
 * @param {HTMLElement} container
 * @param {{ label: string }[]} scenarios
 * @param {number} activeIndex
 * @param {(index: number) => void} onSelect
 * @returns {void}
 */
export function renderTabs(container, scenarios, activeIndex, onSelect) {
  container.innerHTML = "";
  scenarios.forEach((scenario, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `tab${index === activeIndex ? " active" : ""}`;
    button.textContent = scenario.label;
    button.addEventListener("click", () => onSelect(index));
    container.appendChild(button);
  });
}

/**
 * Render the current scenario label and sentence prefix.
 *
 * @param {{ scenarioType: HTMLElement, sentencePrefix: HTMLElement }} elements
 * @param {{ prefix: string, type: string }} scenario
 * @returns {void}
 */
export function renderScenario(elements, scenario) {
  elements.scenarioType.textContent = scenario.type;
  elements.sentencePrefix.textContent = scenario.prefix;
}

/**
 * Render the token probability chart, top-p pills, and explanatory insight copy.
 *
 * @param {{ bars: HTMLElement, insightBox: HTMLElement, tokenPills: HTMLElement }} elements
 * @param {{
 *   inTopP: Set<number>,
 *   sorted: Array<{ idx: number, prob: number, word: string }>,
 *   temperature: number,
 *   topP: number,
 *   topTokenProbability: number,
 *   topTokens: Array<{ prob: number, word: string }>
 * }} state
 * @returns {void}
 */
export function renderDistribution(elements, state) {
  const colors = palette();
  const bars = elements.bars;
  const pills = elements.tokenPills;
  const insight = elements.insightBox;

  bars.innerHTML = "";
  state.sorted.forEach((token, rank) => {
    const excluded = !state.inTopP.has(token.idx);
    const percent = (token.prob * 100).toFixed(1);
    const row = document.createElement("div");
    row.className = `bar-wrap${excluded ? " excluded" : ""}`;

    const label = document.createElement("span");
    label.className = "bar-label";
    label.title = token.word;
    label.textContent = token.word;

    const track = document.createElement("div");
    track.className = "bar-track";

    const fill = document.createElement("div");
    fill.className = "bar-fill";
    fill.style.width = `${percent}%`;
    fill.style.background = colors[rank % colors.length];
    track.appendChild(fill);

    const percentCopy = document.createElement("span");
    percentCopy.className = "bar-pct";
    percentCopy.textContent = `${percent}%`;

    row.append(label, track, percentCopy);
    bars.appendChild(row);
  });

  pills.innerHTML = "";
  state.topTokens.forEach((token, index) => {
    const renormalized = ((token.prob / state.topTokenProbability) * 100).toFixed(1);
    const pill = document.createElement("span");
    pill.className = `pill${index === 0 ? " winner" : ""}`;
    if (index !== 0) {
      const color = colors[index % colors.length];
      pill.style.background = alphaColor(color, 0.18);
      pill.style.borderColor = alphaColor(color, 0.4);
      pill.style.color = css("--color-text");
    }
    pill.textContent = `${token.word} ${renormalized}%`;
    pills.appendChild(pill);
  });

  const winner = state.topTokens[0];
  insight.textContent = temperatureInsight(winner, state.temperature) + topPInsight(state.topP, state.topTokens.length);
}
