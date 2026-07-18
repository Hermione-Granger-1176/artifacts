import { initAppShell, renderAppShell } from "../../../js/modules/app-shell.js";
import { initializeMatureApp } from "../../../js/modules/app-runtime.js";
import { cacheElements } from "../../../js/modules/element-cache.js";
import { initSectionNav, renderSectionNav } from "../../../js/modules/section-nav.js";
import { initSegmented } from "../../../js/modules/segmented.js";
import { refreshPalette, renderProbabilityChart } from "./modules/charts.js";
import { initAccordion } from "./modules/accordion.js";
import {
  renderDistribution,
  renderScenario,
  renderTabs,
  renderTokenExamples
} from "./modules/render.js";
import { buildTopPSelection, drawToken, tallyDraws } from "./modules/sampling.js";
import { scenarios } from "./modules/scenarios.js";

// Populated dynamically from ELEMENT_IDS via a string-keyed loop, so the shape
// is not statically known here; the render helpers assert the members they use.
/** @type {any} */
const elements = {};

let activeIndex = 0;
/** @type {any | null} */
let probabilityChart = null;
/** @type {number | null} */
let selectedTokenIndex = null;
/** @type {Map<number, number> | null} */
let sampleCounts = null;
let showWhitespace = false;
/** @type {number | null} */
let pickedTokenTimer = null;

const NAV_SECTIONS = [
  { id: "sec-tokens", label: "Tokens" },
  { id: "sec-sampling", label: "Sampling" },
  { id: "sec-distribution", label: "Distribution" },
  { id: "concepts", label: "Concepts" }
];

const ELEMENT_IDS = [
  "tabs",
  "scenario-type",
  "sentence-prefix",
  "sentence-completion",
  "temp-slider",
  "temp-val",
  "temp-note",
  "topp-slider",
  "topp-val",
  "sampling-presets",
  "pick-token",
  "sample-hundred",
  "reset-samples",
  "sample-status",
  "probability-chart",
  "token-pills",
  "insight-box",
  "token-examples",
  "whitespace-toggle",
  "concepts"
];

renderAppShell();

initializeMatureApp({
  onErrorContext: "tokenizer explorer initialization",
  run: () => {
    cacheAppElements();
    initAppShell({
      onThemeChange: () => {
        refreshPalette();
        render();
      }
    });
    initAccordion(elements.concepts);
    renderSectionNav(document.querySelector("[data-section-nav]"));
    initSectionNav(NAV_SECTIONS);
    bindEvents();
    const tabButtons = renderTabs(elements.tabs, scenarios, activeIndex);
    initSegmented(elements.tabs, (button) => selectScenario(tabButtons.indexOf(button)));
    renderTokenExamples(elements.tokenExamples, showWhitespace);
    render();
  }
});

function cacheAppElements() {
  const cached = cacheElements(ELEMENT_IDS);

  for (const [id, el] of Object.entries(cached)) {
    elements[id.replace(/-([a-z])/g, (_match, char) => char.toUpperCase())] = el;
  }
}

function bindEvents() {
  elements.tempSlider.addEventListener("input", handleDistributionChange);
  elements.toppSlider.addEventListener("input", handleDistributionChange);
  elements.samplingPresets.addEventListener("click", (event) => {
    const target = /** @type {Element | null} */ (event.target);
    const preset = target?.closest(".sampling-preset");
    if (!preset) {
      return;
    }

    const temperature = preset.getAttribute("data-temperature");
    const topP = preset.getAttribute("data-topp");
    if (!temperature || !topP) {
      return;
    }
    elements.tempSlider.value = String(Number(temperature) * 10);
    elements.toppSlider.value = String(Number(topP) * 100);
    handleDistributionChange();
  });
  elements.pickToken.addEventListener("click", pickNextToken);
  elements.sampleHundred.addEventListener("click", sampleOneHundredTimes);
  elements.resetSamples.addEventListener("click", resetSamples);
  elements.whitespaceToggle.addEventListener("click", () => {
    showWhitespace = !showWhitespace;
    elements.whitespaceToggle.setAttribute("aria-pressed", String(showWhitespace));
    elements.whitespaceToggle.textContent = showWhitespace ? "Hide whitespace" : "Show whitespace";
    renderTokenExamples(elements.tokenExamples, showWhitespace);
  });
}

function selectScenario(index) {
  activeIndex = index;
  clearSamplingFeedback();
  render();
}

function handleDistributionChange() {
  clearSamplingFeedback();
  render();
}

function clearSamplingFeedback() {
  selectedTokenIndex = null;
  sampleCounts = null;
  if (pickedTokenTimer !== null) {
    clearTimeout(pickedTokenTimer);
    pickedTokenTimer = null;
  }
}

function pickNextToken() {
  const state = currentSamplingState();
  selectedTokenIndex = drawToken(state.topTokens).idx;
  if (pickedTokenTimer !== null) {
    clearTimeout(pickedTokenTimer);
  }
  pickedTokenTimer = setTimeout(() => {
    selectedTokenIndex = null;
    pickedTokenTimer = null;
    render();
  }, 1800);
  render();
}

function sampleOneHundredTimes() {
  const state = currentSamplingState();
  selectedTokenIndex = null;
  sampleCounts = tallyDraws(state.topTokens, 100);
  if (pickedTokenTimer !== null) {
    clearTimeout(pickedTokenTimer);
    pickedTokenTimer = null;
  }
  render();
}

function resetSamples() {
  clearSamplingFeedback();
  render();
}

function currentSamplingState() {
  const temperature = Number.parseFloat(elements.tempSlider.value) / 10;
  const topP = Number.parseFloat(elements.toppSlider.value) / 100;
  const scenario = scenarios[activeIndex];
  return {
    ...buildTopPSelection(scenario.tokens, temperature, topP),
    temperature,
    topP
  };
}

function temperatureNote(temperature) {
  if (temperature === 0) {
    return "At 0, the model always picks the top token (greedy decoding).";
  }
  if (temperature <= 0.3) {
    return "Low temperature makes the highest score dominate the draw.";
  }
  if (temperature >= 2) {
    return "High temperature spreads probability across more surprising choices.";
  }
  return "A middle setting balances coherence and surprise.";
}

function render() {
  const state = currentSamplingState();
  const scenario = scenarios[activeIndex];
  const selectedToken = state.sorted.find((token) => token.idx === selectedTokenIndex) ?? null;

  elements.tempVal.textContent = state.temperature.toFixed(1);
  elements.tempNote.textContent = temperatureNote(state.temperature);
  elements.toppVal.textContent = state.topP.toFixed(2);
  renderScenario(elements, scenario, selectedToken?.word ?? null);
  probabilityChart = renderProbabilityChart(probabilityChart, elements.probabilityChart, {
    ...state,
    sampleCounts,
    selectedTokenIndex
  });
  renderDistribution(elements, {
    ...state,
    sampleCounts,
    selectedTokenIndex
  });
}
