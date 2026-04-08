import { initAppShell, renderAppShell } from "../../../js/modules/app-shell.js";
import { initializeMatureApp } from "../../../js/modules/app-runtime.js";
import { cacheElements } from "../../../js/modules/element-cache.js";
import { initAccordion } from "./modules/accordion.js";
import { renderDistribution, renderScenario, renderTabs } from "./modules/render.js";
import { scenarios } from "./modules/scenarios.js";
import { buildTopPSelection } from "./modules/sampling.js";

const elements = {};

let activeIndex = 0;

renderAppShell();

initializeMatureApp({
  onErrorContext: "tokenizer explorer initialization",
  run: () => {
    cacheAppElements();
    initAppShell({ onThemeChange: () => render() });
    initAccordion(elements.concepts);
    bindEvents();
    renderTabs(elements.tabs, scenarios, activeIndex, selectScenario);
    render();
  }
});

const ELEMENT_IDS = [
  "tabs",
  "scenario-type",
  "sentence-prefix",
  "temp-slider",
  "temp-val",
  "topp-slider",
  "topp-val",
  "bars",
  "token-pills",
  "insight-box",
  "concepts"
];

function cacheAppElements() {
  const cached = cacheElements(ELEMENT_IDS);

  for (const [id, el] of Object.entries(cached)) {
    elements[id.replace(/-([a-z])/g, (_, char) => char.toUpperCase())] = el;
  }
}

function bindEvents() {
  elements.tempSlider.addEventListener("input", render);
  elements.toppSlider.addEventListener("input", render);
}

function selectScenario(index) {
  activeIndex = index;
  renderTabs(elements.tabs, scenarios, activeIndex, selectScenario);
  render();
}

function render() {
  const temperature = Number.parseFloat(elements.tempSlider.value) / 10;
  const topP = Number.parseFloat(elements.toppSlider.value) / 100;
  const scenario = scenarios[activeIndex];
  const state = buildTopPSelection(scenario.tokens, temperature, topP);

  elements.tempVal.textContent = temperature.toFixed(1);
  elements.toppVal.textContent = topP.toFixed(2);
  renderScenario(elements, scenario);
  renderDistribution(elements, {
    ...state,
    temperature,
    topP
  });
}
