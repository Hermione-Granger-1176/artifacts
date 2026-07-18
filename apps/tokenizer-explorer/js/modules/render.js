import { createPaletteCache, cssAlpha, cssValue } from "../../../../js/modules/chart-theme.js";
import { formatTokenForDisplay, getTokenExampleStats, tokenExamples } from "./token-examples.js";

const { colors, refreshPalette } = createPaletteCache(() => ({
  pillBackgrounds: [
    cssAlpha("--color-blue", 0.16),
    cssAlpha("--color-green", 0.16),
    cssAlpha("--color-amber", 0.16),
    cssAlpha("--color-purple", 0.16)
  ],
  pillBorders: [
    cssAlpha("--color-blue", 0.42),
    cssAlpha("--color-green", 0.42),
    cssAlpha("--color-amber", 0.42),
    cssAlpha("--color-purple", 0.42)
  ],
  text: cssValue("--color-text")
}));

export { refreshPalette as refreshRenderPalette };

function temperatureInsight(winner, temperature) {
  if (temperature === 0) {
    return "At temperature 0, the model always picks the top token (greedy decoding).";
  }

  const value = temperature.toFixed(1);
  if (temperature <= 0.3) {
    return `At temperature ${value}, the model is almost deterministic. "${winner.word}" wins nearly every time. Great for code or facts where consistency matters.`;
  }
  if (temperature >= 2.0) {
    return `At temperature ${value}, probability spreads out widely. Unusual tokens become real contenders. Useful for creative tasks, risky for factual ones.`;
  }
  return `At temperature ${value}, "${winner.word}" is the favorite but there is real variety. A solid balance between coherence and surprise.`;
}

function topPInsight(topP, tokenCount) {
  const value = topP.toFixed(2);
  if (topP <= 0.1) {
    return `Top P=${value} is very tight. Only the single most likely token makes the cut.`;
  }
  if (topP <= 0.5) {
    return `Top P=${value} keeps a small, high-confidence pool. Only the safest tokens are in play.`;
  }
  if (topP >= 0.99) {
    return `Top P=${value} is wide enough that nearly every token stays in play. Temperature does most of the shaping here.`;
  }
  return `Top P=${value} keeps ${tokenCount} token${tokenCount !== 1 ? "s" : ""} whose cumulative probability reaches that threshold.`;
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
    button.className = `btn tab${index === activeIndex ? " active" : ""}`;
    button.textContent = scenario.label;
    button.addEventListener("click", () => onSelect(index));
    container.appendChild(button);
  });
}

/**
 * Render the current scenario label and sentence prefix.
 *
 * @param {{ scenarioType: HTMLElement, sentencePrefix: HTMLElement, sentenceCompletion?: HTMLElement }} elements
 * @param {{ prefix: string, type: string }} scenario
 * @param {string | null} [chosenWord=null]
 * @returns {void}
 */
export function renderScenario(elements, scenario, chosenWord = null) {
  elements.scenarioType.textContent = scenario.type;
  elements.sentencePrefix.textContent = scenario.prefix;
  if (elements.sentenceCompletion) {
    elements.sentenceCompletion.textContent = chosenWord ?? "";
    elements.sentenceCompletion.classList.toggle("has-choice", Boolean(chosenWord));
  }
}

/**
 * Render canned token chunks and their counts. The supplied examples are
 * deliberately static so the section explains the idea without claiming to
 * reproduce one particular model's tokenizer.
 *
 * @param {HTMLElement} container
 * @param {boolean} showWhitespace
 * @returns {void}
 */
export function renderTokenExamples(container, showWhitespace) {
  container.innerHTML = "";
  tokenExamples.forEach((example, exampleIndex) => {
    const row = document.createElement("article");
    row.className = "token-example";

    const header = document.createElement("div");
    header.className = "token-example-header";
    const label = document.createElement("h3");
    label.textContent = example.label;
    const stats = getTokenExampleStats(example);
    const count = document.createElement("span");
    count.className = "token-example-count";
    count.textContent = `${stats.tokenCount} tokens, ${stats.characterCount} characters`;
    header.append(label, count);

    const description = document.createElement("p");
    description.textContent = example.description;

    const chips = document.createElement("div");
    chips.className = "token-chips";
    example.tokens.forEach((token, tokenIndex) => {
      const chip = document.createElement("span");
      chip.className = `token-chip tone-${(exampleIndex + tokenIndex) % 5}`;
      chip.title = token;
      chip.textContent = formatTokenForDisplay(token, showWhitespace);
      chips.appendChild(chip);
    });

    row.append(header, description, chips);
    container.appendChild(row);
  });
}

/**
 * Render top-p pills and explanatory insight copy. The chart itself lives in
 * charts.js so slider updates can animate an existing Chart.js instance.
 *
 * @param {{ insightBox: HTMLElement, sampleStatus?: HTMLElement, tokenPills: HTMLElement }} elements
 * @param {{
 *   selectedTokenIndex: number | null,
 *   temperature: number,
 *   topP: number,
 *   topTokens: Array<{ adjustedProb: number, idx: number, word: string }>,
 *   sampleCounts: Map<number, number> | null
 * }} state
 * @returns {void}
 */
export function renderDistribution(elements, state) {
  const palette = colors();
  const pills = elements.tokenPills;
  const insight = elements.insightBox;

  pills.innerHTML = "";
  state.topTokens.forEach((token, index) => {
    const selected = token.idx === state.selectedTokenIndex;
    const pill = document.createElement("span");
    pill.className = `pill${selected ? " winner" : ""}`;
    if (!selected) {
      const colorIndex = index % palette.pillBackgrounds.length;
      pill.style.background = palette.pillBackgrounds[colorIndex];
      pill.style.borderColor = palette.pillBorders[colorIndex];
      pill.style.color = palette.text;
    }
    pill.textContent = `${token.word} ${(token.adjustedProb * 100).toFixed(1)}%`;
    pills.appendChild(pill);
  });

  const winner = state.topTokens[0];
  insight.textContent = `${temperatureInsight(winner, state.temperature)} ${topPInsight(
    state.topP,
    state.topTokens.length
  )}`;

  if (elements.sampleStatus) {
    elements.sampleStatus.textContent = state.sampleCounts
      ? "The amber bars show the tally from 100 draws. Draws follow the renormalized pool, so a surviving token can land above its blue bar."
      : "Run 100 draws to compare the observed tally with the distribution.";
  }
}
