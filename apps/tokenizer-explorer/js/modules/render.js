import { buildCandidateRows, renderCandidateList } from "./candidates.js";
import {
  formatTokenForDisplay,
  getTokenExampleStats,
  splitPromptTokens,
  tokenExamples
} from "./token-examples.js";

// Shared chip tone modifiers cycled across the illustrative token chips.
const CHIP_TONES = ["is-blue", "is-green", "is-amber", "is-purple", "is-red"];

const SAMPLE_STATUS_IDLE = "Run 100 draws to compare the observed tally with the distribution.";
const SAMPLE_STATUS_TALLY =
  "Thin bars: tally from 100 draws of the renormalized pool, so a token can land above its blue bar.";

// One setting per branch of the two insight copies, used to size the hidden
// copies that reserve the insight's height. Keep them in step with the branches
// in temperatureInsight and topPInsight; the tests check that every setting
// reachable from the sliders has a reserved copy.
const INSIGHT_TEMPERATURES = [0, 0.3, 1, 2];
const INSIGHT_TOP_PS = [0.1, 0.5, 0.7, 0.99];

/**
 * @param {string} token - Raw token text.
 * @param {string} className - Chip classes, including its tone.
 * @param {boolean} showWhitespace - Whether to draw whitespace as visible glyphs.
 * @returns {HTMLElement} Token chip whose title keeps the raw token.
 */
function createTokenChip(token, className, showWhitespace) {
  const chip = document.createElement("span");
  chip.className = className;
  chip.title = token;
  chip.textContent = formatTokenForDisplay(token, showWhitespace);
  return chip;
}

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
 * @param {{ word: string }} winner - Highest-probability token.
 * @param {number} temperature - Sampling temperature.
 * @param {number} topP - Nucleus sampling threshold.
 * @param {number} tokenCount - Number of tokens in the pool.
 * @returns {string} The full insight line.
 */
function insightCopy(winner, temperature, topP, tokenCount) {
  return `${temperatureInsight(winner, temperature)} ${topPInsight(topP, tokenCount)}`;
}

/**
 * @param {{ tokens: { word: string }[] }} scenario
 * @returns {number} Characters in the scenario's longest candidate word.
 */
function longestWordLength(scenario) {
  return Math.max(0, ...scenario.tokens.map((token) => token.word.length));
}

/**
 * @param {string} tag
 * @param {string} className
 * @param {string} text
 * @returns {HTMLElement}
 */
function createText(tag, className, text) {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
}

/**
 * Every insight line the sliders can produce, written for the longest candidate
 * word. They are stacked out of sight in one grid cell so the insight box is as
 * tall as the longest, at whatever width the card has.
 *
 * @param {{ tokens: { word: string }[] }[]} scenarios
 * @returns {string[]}
 */
export function insightReserveCopies(scenarios) {
  const words = scenarios.flatMap((scenario) => scenario.tokens.map((token) => token.word));
  const longest = words.reduce((best, word) => (word.length > best.length ? word : best), "");
  const tokenCount = Math.max(...scenarios.map((scenario) => scenario.tokens.length));
  return INSIGHT_TEMPERATURES.flatMap((temperature) =>
    INSIGHT_TOP_PS.map((topP) => insightCopy({ word: longest }, temperature, topP, tokenCount))
  );
}

/**
 * Reserve the height of the longest insight and sample status copy. The live
 * text sits in the same grid cell as hidden copies of every possible text, so
 * the buttons and sliders below never move when the copy changes length.
 *
 * @param {{ insightReserve: HTMLElement, statusReserve: HTMLElement }} elements
 * @param {{ tokens: { word: string }[] }[]} scenarios
 * @returns {void}
 */
export function renderCopyReserves(elements, scenarios) {
  elements.insightReserve.replaceChildren(
    ...insightReserveCopies(scenarios).map((text) => createText("span", "tk-insight", text))
  );
  elements.statusReserve.replaceChildren(
    ...[SAMPLE_STATUS_IDLE, SAMPLE_STATUS_TALLY].map((text) => createText("span", "tk-status", text))
  );
}

/**
 * Reserve the height of the tallest prompt. A hidden copy of every scenario's
 * prompt shares one grid cell with the live prompt, so the cell is as tall as
 * the tallest at the current width and a new scenario never moves what follows.
 *
 * @param {HTMLElement} container
 * @param {{ prefix: string, tokens: { word: string }[] }[]} scenarios
 * @returns {void}
 */
export function renderPromptReserve(container, scenarios) {
  container.replaceChildren(
    ...scenarios.map((scenario) => {
      const line = document.createElement("div");
      const blank = createText("span", "blank", "");
      blank.style.setProperty("--blank-chars", String(longestWordLength(scenario)));
      line.append(
        ...splitPromptTokens(scenario.prefix).map((token, index) =>
          createTokenChip(token, `chip is-mono token-chip prompt-chip ${CHIP_TONES[index % CHIP_TONES.length]}`, false)
        ),
        blank
      );
      return line;
    })
  );
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
 * @param {{ prefix: string, type: string, tokens: { word: string }[] }} scenario
 * @param {string | null} [chosenWord=null]
 * @param {boolean} [showWhitespace=false]
 * @returns {void}
 */
export function renderScenario(elements, scenario, chosenWord = null, showWhitespace = false) {
  elements.scenarioType.textContent = scenario.type;
  elements.sentencePrefix.replaceChildren(
    ...splitPromptTokens(scenario.prefix).map((token, index) =>
      createTokenChip(token, `chip is-mono token-chip prompt-chip ${CHIP_TONES[index % CHIP_TONES.length]}`, showWhitespace)
    )
  );
  if (elements.sentenceCompletion) {
    elements.sentenceCompletion.style.setProperty("--blank-chars", String(longestWordLength(scenario)));
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
      const tone = CHIP_TONES[(exampleIndex + tokenIndex) % CHIP_TONES.length];
      chips.appendChild(createTokenChip(token, `chip is-mono token-chip ${tone}`, showWhitespace));
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
  elements.insightBox.textContent = insightCopy(winner, state.temperature, state.topP, state.topTokens.length);

  if (elements.sampleStatus) {
    elements.sampleStatus.textContent = state.sampleCounts ? SAMPLE_STATUS_TALLY : SAMPLE_STATUS_IDLE;
  }
}
