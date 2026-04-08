/** Bind change and Enter-key handling for a text input paired with a slider. */
function bindTextInput(elements, { id, sliderId, min, max, parser, onCommit }) {
  elements[id].addEventListener("change", function onChange() {
    const value = parser(this.value);
    if (!Number.isNaN(value) && value > 0) {
      elements[sliderId].value = Math.min(Math.max(value, min), max);
      onCommit();
    }
  });

  elements[id].addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.currentTarget.blur();
    }
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
    parser: parseInt,
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
  elements.btnCharts.addEventListener("click", () => {
    onViewModeChange("charts");
  });
  elements.btnTable.addEventListener("click", () => {
    onViewModeChange("table");
  });
  elements.btnPeriod.addEventListener("click", () => {
    onTableModeChange("period");
  });
  elements.btnYearly.addEventListener("click", () => {
    onTableModeChange("yearly");
  });
}
