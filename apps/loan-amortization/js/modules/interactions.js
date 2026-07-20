import { initSegmented } from "../../../../js/modules/segmented.js";

/**
 * Bind change and Enter-key handling for a text input paired with a slider.
 * @param {Record<string, HTMLElement>} elements - Cached app elements.
 * @param {{ id: string, sliderId: string, min: number, max: number, parser: (value: string) => number, onCommit: () => void }} config - Input binding config.
 * @returns {void}
 */
function bindTextInput(elements, { id, sliderId, min, max, parser, onCommit }) {
  elements[id].addEventListener(
    "change",
    /** @this {HTMLInputElement} */ function onChange() {
      const value = parser(this.value);
      if (!Number.isNaN(value) && value > 0) {
        const slider = /** @type {HTMLInputElement} */ (elements[sliderId]);
        slider.value = String(Math.min(Math.max(value, min), max));
        onCommit();
      }
    },
  );

  elements[id].addEventListener("keydown", (/** @type {KeyboardEvent} */ event) => {
    if (event.key !== "Enter") {
      return;
    }

    /** @type {HTMLElement} */ (event.currentTarget).blur();
  });
}

/**
 * Bind the loan app interactions with injected callbacks for state updates.
 *
 * @param {object} options
 * @param {Record<string, HTMLElement>} options.elements
 * @param {() => void} options.onSliderInput
 * @param {() => void} options.onPrincipalCommit
 * @param {() => void} options.onRateCommit
 * @param {() => void} options.onTenureCommit
 * @param {() => void} options.onFrequencyChange
 * @param {(mode: string) => void} options.onBiweeklyModeChange
 * @param {() => void} options.onAddExtra
 * @param {(event: Event) => void} options.onExtraListClick
 * @param {(event: Event) => void} options.onExtraListInput
 * @param {(mode: "charts" | "table") => void} options.onViewModeChange
 * @param {(mode: "period" | "yearly") => void} options.onTableModeChange
 * @param {(value: string) => number} options.parseNumber
 * @returns {void}
 */
export function bindEvents({
  elements,
  onSliderInput,
  onPrincipalCommit,
  onRateCommit,
  onTenureCommit,
  onFrequencyChange,
  onBiweeklyModeChange,
  onAddExtra,
  onExtraListClick,
  onExtraListInput,
  onViewModeChange,
  onTableModeChange,
  parseNumber
}) {
  for (const id of ["slPrincipal", "slRate", "slTenure"]) {
    elements[id].addEventListener("input", onSliderInput);
  }

  bindTextInput(elements, {
    id: "inPrincipal",
    sliderId: "slPrincipal",
    min: 5000,
    max: 500000,
    parser: parseNumber,
    onCommit: onPrincipalCommit
  });
  bindTextInput(elements, {
    id: "inRate",
    sliderId: "slRate",
    min: 1,
    max: 20,
    parser: parseFloat,
    onCommit: onRateCommit
  });
  bindTextInput(elements, {
    id: "inTenure",
    sliderId: "slTenure",
    min: 1,
    max: 30,
    parser: (/** @type {string} */ value) => parseInt(value, 10),
    onCommit: onTenureCommit
  });

  elements.selFreq.addEventListener("change", onFrequencyChange);
  elements.bwTrue.addEventListener("click", () => {
    onBiweeklyModeChange("true");
  });
  elements.bwAccel.addEventListener("click", () => {
    onBiweeklyModeChange("accelerated");
  });
  elements.btnAdd.addEventListener("click", onAddExtra);
  elements.extraList.addEventListener("click", onExtraListClick);
  elements.extraList.addEventListener("input", onExtraListInput);
  initSegmented(elements.viewToggle, (/** @type {HTMLElement} */ button) => {
    onViewModeChange(button.id === "btnCharts" ? "charts" : "table");
  });
  initSegmented(elements.tableToggle, (/** @type {HTMLElement} */ button) => {
    onTableModeChange(button.id === "btnPeriod" ? "period" : "yearly");
  });
}
