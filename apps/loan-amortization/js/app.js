import { runSchedule } from "./modules/amortization.js";
import { refreshPalette, renderCharts } from "./modules/charts.js";
import { initializeMatureApp } from "../../../js/modules/app-runtime.js";
import { initAppShell, renderAppShell } from "../../../js/modules/app-shell.js";
import { bindEvents } from "./modules/interactions.js";
import {
  createExtra,
  removeExtraById,
  renderExtras,
  setExtraType,
  summarizeExtra,
  updateExtraField
} from "./modules/extras.js";
import { formatCurrency, formatDollarTick, parseNumber } from "../../../js/modules/formatting.js";
import { renderMetrics } from "./modules/metrics.js";
import {
  getBiweeklyEmiOverride,
  getFrequencyParams,
  summarizeScheduleRows
} from "./modules/schedule-summary.js";
import {
  renderPeriodTable,
  renderTableSummary,
  renderYearlyTable
} from "./modules/tables.js";
import {
  cacheElements,
  getChartElements,
  setTableMode,
  setViewMode,
  syncBiweeklyModeUI,
  syncInputsFromSliders,
  updateBiweeklyMode as syncBiweeklyModeVisibility
} from "./modules/ui.js";

/**
 * @typedef {{
 *   selFreq: HTMLSelectElement,
 *   slPrincipal: HTMLInputElement,
 *   slRate: HTMLInputElement,
 *   slTenure: HTMLInputElement,
 *   extraList: HTMLElement,
 *   metrics: HTMLElement,
 *   chartsWrap: HTMLElement,
 *   tableWrap: HTMLElement,
 *   tableSummary: HTMLElement,
 *   tbody: HTMLElement,
 *   ybody: HTMLElement,
 *   [key: string]: HTMLElement
 * }} LoanElements
 */

/** @type {LoanElements} */
let elements = /** @type {LoanElements} */ (/** @type {unknown} */ ({}));
/** @type {ReturnType<typeof createExtra>[]} */
let extras = [];
let nextExtraId = 0;
let charts = {};
let bwMode = "true";
let pendingRecalcFrame = /** @type {number | null} */ (null);

renderAppShell();

initializeMatureApp({
  onErrorContext: "loan amortization initialization",
  run: () => {
    elements = /** @type {LoanElements} */ (/** @type {unknown} */ (cacheElements()));
    initAppShell({
      onThemeChange: () => {
        refreshPalette();
        recalc();
      }
    });
    bindLoanEvents();
    updateBiweeklyMode();
    syncInputsFromSliders(elements);
    renderExtrasSection();
    recalc();
  }
});

function bindLoanEvents() {
  const syncInputsAndRecalculate = () => {
    syncInputsFromSliders(elements);
    recalc();
  };

  bindEvents({
    elements,
    onSliderInput: () => {
      syncInputsFromSliders(elements);
      scheduleRecalc();
    },
    onPrincipalCommit: syncInputsAndRecalculate,
    onRateCommit: syncInputsAndRecalculate,
    onTenureCommit: syncInputsAndRecalculate,
    onFrequencyChange: () => {
      updateBiweeklyMode();
      renderExtrasSection();
      recalc();
    },
    onBiweeklyModeChange: setBiweeklyMode,
    onAddExtra: () => {
      extras.push(createExtra(nextExtraId));
      nextExtraId += 1;
      renderExtrasSection();
      recalc();
    },
    onExtraListClick: handleExtraListClick,
    onExtraListInput: handleExtraListInput,
    onViewModeChange: (mode) => {
      setViewMode(elements, mode);
      recalc();
    },
    onTableModeChange: (mode) => {
      setTableMode(elements, mode);
    },
    parseNumber
  });
}

function getFrequency() {
  return elements.selFreq.value;
}

/** @param {string} mode - Biweekly mode flag. */
function setBiweeklyMode(mode) {
  bwMode = mode;
  syncBiweeklyModeUI(elements, bwMode);
  recalc();
}

function updateBiweeklyMode() {
  syncBiweeklyModeVisibility(elements, getFrequency(), bwMode);
}

function renderExtrasSection() {
  renderExtras({
    container: elements.extraList,
    extras,
    periodLabel: getFrequencyParams(getFrequency()).label.toLowerCase()
  });
}

/** @param {Event} event - Delegated click event. */
function handleExtraListClick(event) {
  const target = /** @type {HTMLElement | null} */ (event.target);
  const button = /** @type {HTMLElement | null} */ (target?.closest("button[data-action]") ?? null);
  if (!button) {
    return;
  }

  const extraRow = /** @type {HTMLElement | null} */ (button.closest("[data-extra-id]"));
  const extraId = Number(extraRow?.dataset.extraId);
  if (Number.isNaN(extraId)) {
    return;
  }

  const actions = {
    "remove-extra": () => {
      extras = /** @type {ReturnType<typeof createExtra>[]} */ (removeExtraById(extras, extraId));
    },
    "set-type": () => {
      setExtraType(extras, extraId, button.dataset.type ?? "");
    }
  };

  const action = actions[/** @type {"remove-extra" | "set-type"} */ (button.dataset.action ?? "")];
  if (!action) {
    return;
  }

  action();
  renderExtrasSection();
  recalc();
}

/** @param {Event} event - Delegated input event. */
function handleExtraListInput(event) {
  const target = /** @type {HTMLElement | null} */ (event.target);
  const input = /** @type {HTMLInputElement | null} */ (target?.closest("input[data-field]") ?? null);
  if (!input) {
    return;
  }

  const extraRow = /** @type {HTMLElement | null} */ (input.closest("[data-extra-id]"));
  const extraId = Number(extraRow?.dataset.extraId);
  if (Number.isNaN(extraId)) {
    return;
  }

  updateExtraField(extras, extraId, input.dataset.field ?? "", input.value);
  const extra = extras.find((item) => item.id === extraId);
  const tip = /** @type {HTMLElement | null} */ (input.closest(".extra-item")?.querySelector(".info-tip") ?? null);
  if (!extra || !tip) {
    recalc();
    return;
  }

  const summary = summarizeExtra(extra, getFrequencyParams(getFrequency()).label.toLowerCase());
  tip.dataset.tip = summary;
  tip.setAttribute("aria-label", summary);
  recalc();
}

function scheduleRecalc() {
  if (pendingRecalcFrame !== null) {
    return;
  }

  pendingRecalcFrame = window.requestAnimationFrame(() => {
    pendingRecalcFrame = null;
    recalc();
  });
}

function recalc() {
  const principal = +elements.slPrincipal.value;
  const annualRate = +elements.slRate.value;
  const years = +elements.slTenure.value;
  const selectedFrequency = getFrequency();
  const frequency = getFrequencyParams(selectedFrequency);
  const ratePerPeriod = annualRate / 100 / frequency.periodsPerYear;
  const totalPeriods = years * frequency.periodsPerYear;
  const emiOverride = getBiweeklyEmiOverride({
    principal,
    annualRate,
    years,
    frequency: selectedFrequency,
    bwMode
  });

  const base = runSchedule(principal, ratePerPeriod, totalPeriods, {
    withExtras: false,
    emiOverride
  });
  const extra = runSchedule(principal, ratePerPeriod, totalPeriods, {
    withExtras: true,
    emiOverride,
    extras
  });

  const savings = base.totalInterest - extra.totalInterest;
  const periodsSaved = base.periods - extra.periods;
  const totalPaid = principal + extra.totalInterest;
  const costRatio = totalPaid / principal;

  renderMetrics(
    elements.metrics,
    {
      base,
      extra,
      savings,
      periodsSaved,
      totalPaid,
      costRatio,
      label: frequency.label
    },
    formatCurrency
  );

  if (!elements.chartsWrap.hidden) {
    charts = renderCharts({
      charts,
      elements: getChartElements(elements),
      base,
      extra,
      principal,
      interestSaved: savings,
      periodLabel: frequency.label,
      formatCurrency,
      formatDollarTick
    });
  }

  const { totalEmi, totalPrincipal, totalInterest, totalExtras } = summarizeScheduleRows(
    extra.rows
  );

  if (!elements.tableWrap.hidden) {
    renderTableSummary(elements.tableSummary, {
      totalEmi: formatCurrency(totalEmi),
      totalPrincipal: formatCurrency(totalPrincipal),
      totalInterest: formatCurrency(totalInterest),
      totalExtras: totalExtras > 0 ? formatCurrency(totalExtras) : "-",
      periods: String(extra.periods)
    });

    renderPeriodTable(elements.tbody, extra.rows, formatCurrency);
    renderYearlyTable(
      elements.ybody,
      extra.rows,
      principal,
      frequency.periodsPerYear,
      formatCurrency
    );
  }
}
