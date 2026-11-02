import { formatPercent } from "../../../../js/modules/formatting.js";
import { buildCandidateRows, renderCandidateList } from "./candidates.js";
import { SAMPLE_DRAW_COUNT } from "./sampling.js";
import {
  formatTokenForDisplay,
  getTokenExampleStats,
  splitPromptTokens,
  tokenExamples
} from "./token-examples.js";

// Shared chip tone modifiers cycled across the illustrative token chips.
const CHIP_TONES = ["is-blue", "is-green", "is-amber", "is-purple", "is-red"];

const SAMPLE_STATUS_IDLE = `Run ${SAMPLE_DRAW_COUNT} draws to compare the observed tally with the distribution.`;
const SAMPLE_STATUS_TALLY =
  `Thin bars: tally from ${SAMPLE_DRAW_COUNT} draws of the renormalized pool, so a token can land above its blue bar.`;

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

/** A winner at or above this probability takes nearly every draw. */
const DOMINANT_PROBABILITY = 0.9;

/**
 * Describe the temperature by what it did to the distribution. The same
 * temperature can leave one scenario nearly certain and another wide open, so
 * the copy reads the winner's probability, not the slider value alone.
 *
 * @param {{ word: string, prob: number }} winner - Highest-probability token.
 * @param {number} temperature - Sampling temperature.
 * @returns {string} Explanatory copy.
 */
function temperatureInsight(winner, temperature) {
  if (temperature === 0) {
    return "At temperature 0, the model always picks the top token (greedy decoding).";
  }

  const value = temperature.toFixed(1);
  const odds = formatPercent(winner.prob * 100);
  if (winner.prob >= DOMINANT_PROBABILITY) {
    return `At temperature ${value}, "${winner.word}" holds ${odds} of the odds and wins nearly every draw. Great for code or facts where consistency matters.`;
  }
  if (temperature >= 2.0) {
    return `At temperature ${value}, probability spreads out widely. Unusual tokens become real contenders. Useful for creative tasks, risky for factual ones.`;
  }
  return `At temperature ${value}, "${winner.word}" leads with ${odds} of the odds, but other tokens still win draws. A solid balance between coherence and surprise.`;
}

/**
 * Describe the top P cut by how many tokens it kept. Whether a wide top P keeps
 * every token depends on temperature too, so the copy reads the kept count.
 *
 * @param {number} topP - Nucleus sampling threshold.
 * @param {number} keptCount - Tokens that survive the cut.
 * @param {number} totalCount - Tokens in the scenario.
 * @returns {string} Explanatory copy.
 */
function topPInsight(topP, keptCount, totalCount) {
  const value = topP.toFixed(2);
  if (keptCount === 1) {
    return `Top P=${value} keeps only the single most likely token.`;
  }
  if (keptCount === totalCount) {
    return `Top P=${value} keeps every token. Temperature does all of the shaping here.`;
  }
  if (topP <= 0.5) {
    return `Top P=${value} keeps a small, high-confidence pool of ${keptCount} tokens.`;
  }
  return `Top P=${value} keeps ${keptCount} tokens whose cumulative probability reaches that threshold.`;
}

/**
 * @param {{ word: string, prob: number }} winner - Highest-probability token.
 * @param {number} temperature - Sampling temperature.
 * @param {number} topP - Nucleus sampling threshold.
 * @param {number} keptCount - Tokens that survive the cut.
 * @param {number} totalCount - Tokens in the scenario.
 * @returns {string} The full insight line.
 */
function insightCopy(winner, temperature, topP, keptCount, totalCount) {
  return `${temperatureInsight(winner, temperature)} ${topPInsight(topP, keptCount, totalCount)}`;
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
  // One case per temperature line and one per top P line. The numbers are the
  // widest each line can print: "100.0%", a two-decimal setting, and the
  // largest token count.
  const temperatureCases = [
    { temperature: 0, prob: 1 },
    { temperature: 0.3, prob: 1 },
    { temperature: 2.5, prob: 0.5 },
    { temperature: 1, prob: 0.5 }
  ];
  const topPCases = [
    { topP: 0.05, keptCount: 1 },
    { topP: 0.99, keptCount: tokenCount },
    { topP: 0.4, keptCount: tokenCount - 1 },
    { topP: 0.8, keptCount: tokenCount - 1 }
  ];
  return temperatureCases.flatMap(({ temperature, prob }) =>
    topPCases.map(({ topP, keptCount }) =>
      insightCopy({ word: longest, prob }, temperature, topP, keptCount, tokenCount)
    )
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

  const winner = state.sorted[0];
  elements.insightBox.textContent = insightCopy(
    winner,
    state.temperature,
    state.topP,
    state.topTokens.length,
    state.sorted.length
  );

  if (elements.sampleStatus) {
    elements.sampleStatus.textContent = state.sampleCounts ? SAMPLE_STATUS_TALLY : SAMPLE_STATUS_IDLE;
  }
}
