import { buildCandidateRows, renderCandidateList } from "./candidates.js";
import {
  formatTokenForDisplay,
  getTokenExampleStats,
  splitPromptTokens,
  tokenExamples
} from "./token-examples.js";

// Shared chip tone modifiers cycled across the illustrative token chips.
const CHIP_TONES = ["is-blue", "is-green", "is-amber", "is-purple", "is-red"];

/**
 * @param {{ word: string }} winner - Highest-probability token.
 * @param {number} temperature - Sampling temperature.
 * @returns {string} Explanatory copy.
 */
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

/**
 * @param {number} topP - Nucleus sampling threshold.
 * @param {number} tokenCount - Number of tokens in the pool.
 * @returns {string} Explanatory copy.
 */
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
 * Fill the scenario dropdown with one option per scenario, showing the label
 * only (the prefix sentence lives in the prompt card).
 *
 * @param {HTMLSelectElement} select
 * @param {{ label: string }[]} scenarios
 * @param {number} activeIndex
 * @returns {void}
 */
export function renderScenarioOptions(select, scenarios, activeIndex) {
  select.replaceChildren(
    ...scenarios.map((scenario, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = scenario.label;
      return option;
    })
  );
  select.value = String(activeIndex);
}

/**
 * Render the scenario type, the prompt as coloured token chips, and the
 * completion blank that sits inline after the last chip.
 *
 * @param {{ scenarioType: HTMLElement, sentencePrefix: HTMLElement, sentenceCompletion?: HTMLElement }} elements
 * @param {{ prefix: string, type: string }} scenario
 * @param {string | null} [chosenWord=null]
 * @param {boolean} [showWhitespace=false]
 * @returns {void}
 */
export function renderScenario(elements, scenario, chosenWord = null, showWhitespace = false) {
  elements.scenarioType.textContent = scenario.type;
  elements.sentencePrefix.replaceChildren(
    ...splitPromptTokens(scenario.prefix).map((token, index) => {
      const chip = document.createElement("span");
      chip.className = `chip is-mono token-chip prompt-chip ${CHIP_TONES[index % CHIP_TONES.length]}`;
      chip.title = token;
      chip.textContent = formatTokenForDisplay(token, showWhitespace);
      return chip;
    })
  );
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
      const tone = CHIP_TONES[(exampleIndex + tokenIndex) % CHIP_TONES.length];
      chip.className = `chip is-mono token-chip ${tone}`;
      chip.title = token;
      chip.textContent = formatTokenForDisplay(token, showWhitespace);
      chips.appendChild(chip);
    });

    row.append(header, description, chips);
    container.appendChild(row);
  });
}

/**
 * Render the candidate list, the insight line, and the sample status. The
 * list owns its own rows (see candidates.js) so slider updates can animate
 * the existing bars.
 *
 * @param {{ candidateList: HTMLElement, insightBox: HTMLElement, sampleStatus?: HTMLElement }} elements
 * @param {{
 *   inTopP: Set<number>,
 *   selectedTokenIndex: number | null,
 *   sorted: Array<{ adjustedProb: number, idx: number, prob: number, word: string }>,
 *   temperature: number,
 *   topP: number,
 *   topTokens: Array<{ adjustedProb: number, idx: number, word: string }>,
 *   sampleCounts: Map<number, number> | null
 * }} state
 * @returns {void}
 */
export function renderDistribution(elements, state) {
  renderCandidateList(elements.candidateList, buildCandidateRows(state));

  const winner = state.topTokens[0];
  elements.insightBox.textContent = `${temperatureInsight(winner, state.temperature)} ${topPInsight(
    state.topP,
    state.topTokens.length
  )}`;

  if (elements.sampleStatus) {
    elements.sampleStatus.textContent = state.sampleCounts
      ? "Thin bars: tally from 100 draws of the renormalized pool, so a token can land above its blue bar."
      : "Run 100 draws to compare the observed tally with the distribution.";
  }
}
