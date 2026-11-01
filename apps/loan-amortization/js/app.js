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
import { createFrameScheduler } from "../../../js/modules/frame-scheduler.js";
import { setText } from "../../../js/modules/dom-sync.js";
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
/**
 * The latest base schedule and the terms it was built from; see getBaseSchedule.
 * @type {{ key: string, base: ReturnType<typeof runSchedule> } | null}
 */
let baseSchedule = null;
/**
 * Inputs of the latest calculation, kept so a view that was hidden can be drawn
 * when it is shown.
 * @type {(import("./modules/metrics.js").LoanMetrics & { principal: number }) | null}
 */
let latest = null;
/** Table bodies behind the latest calculation. Only the visible table is redrawn. */
const staleTables = { period: true, yearly: true };

const scheduleRecalc = createFrameScheduler(() => recalc());

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
      renderResults({ syncAll: true });
    },
    onTableModeChange: (mode) => {
      setTableMode(elements, mode);
      renderResults();
    },
    parseNumber
  });
}

function getFrequency() {
  return elements.selFreq.value;
}

/** @returns {string} Lower-case period noun for the selected cadence, such as "month". */
function getPeriodLabel() {
  return getFrequencyParams(getFrequency()).label.toLowerCase();
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
    periodLabel: getPeriodLabel()
  });
}

/**
 * @param {HTMLElement} control - Control inside an extra-payment row.
 * @returns {number} The row's extra id, or NaN outside a row.
 */
function getExtraId(control) {
  const extraRow = /** @type {HTMLElement | null} */ (control.closest("[data-extra-id]"));
  return Number(extraRow?.dataset.extraId);
}

/** @param {Event} event - Delegated click event. */
function handleExtraListClick(event) {
  const target = /** @type {HTMLElement | null} */ (event.target);
  const button = /** @type {HTMLElement | null} */ (target?.closest("button[data-action]") ?? null);
  if (!button) {
    return;
  }

  const extraId = getExtraId(button);
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

  const extraId = getExtraId(input);
  if (Number.isNaN(extraId)) {
    return;
  }

  updateExtraField(extras, extraId, input.dataset.field ?? "", input.value);
  const extra = extras.find((item) => item.id === extraId);
  const summaryNode = /** @type {HTMLElement | null} */ (
    input.closest(".extra-item")?.querySelector(".extra-summary") ?? null
  );
  if (extra && summaryNode) {
    setText(summaryNode, summarizeExtra(extra, getPeriodLabel()));
  }

  scheduleRecalc();
}

/**
 * @typedef {{
 *   principal: number,
 *   annualRate: number,
 *   years: number,
 *   selectedFrequency: string,
 *   frequency: ReturnType<typeof getFrequencyParams>,
 *   ratePerPeriod: number,
 *   totalPeriods: number,
 *   emiOverride: ReturnType<typeof getBiweeklyEmiOverride>
 * }} LoanTerms
 */

/**
 * Read the loan terms from the controls and derive the per-period schedule inputs.
 * @returns {LoanTerms} Current loan terms.
 */
function readLoanTerms() {
  const principal = +elements.slPrincipal.value;
  const annualRate = +elements.slRate.value;
  const years = +elements.slTenure.value;
  const selectedFrequency = getFrequency();
  const frequency = getFrequencyParams(selectedFrequency);
  return {
    principal,
    annualRate,
    years,
    selectedFrequency,
    frequency,
    ratePerPeriod: annualRate / 100 / frequency.periodsPerYear,
    totalPeriods: years * frequency.periodsPerYear,
    emiOverride: getBiweeklyEmiOverride({
      principal,
      annualRate,
      years,
      frequency: selectedFrequency,
      bwMode
    })
  };
}

/**
 * The schedule without extras. It depends only on the loan terms, so it is
 * rebuilt only when they change, and typing in an extra-payment field reuses it.
 * @param {LoanTerms} terms - Current loan terms.
 * @returns {ReturnType<typeof runSchedule>} The base schedule.
 */
function getBaseSchedule({ principal, annualRate, years, selectedFrequency, ratePerPeriod, totalPeriods, emiOverride }) {
  const baseKey = [principal, annualRate, years, selectedFrequency, bwMode].join("|");
  if (baseSchedule?.key !== baseKey) {
    baseSchedule = {
      key: baseKey,
      base: runSchedule(principal, ratePerPeriod, totalPeriods, {
        withExtras: false,
        emiOverride
      })
    };
  }
  return baseSchedule.base;
}

/**
 * Compare the schedule with extras against the base schedule.
 * @param {LoanTerms} terms - Current loan terms.
 * @param {ReturnType<typeof runSchedule>} base - Schedule without extras.
 * @param {ReturnType<typeof runSchedule>} extra - Schedule with extras.
 * @returns {import("./modules/metrics.js").LoanMetrics} Savings, payoff, and cost figures.
 */
function buildLoanMetrics({ principal, frequency }, base, extra) {
  const totalPaid = principal + extra.totalInterest;
  return {
    base,
    extra,
    savings: base.totalInterest - extra.totalInterest,
    periodsSaved: base.periods - extra.periods,
    totalPaid,
    costRatio: totalPaid / principal,
    label: frequency.label,
    periodsPerYear: frequency.periodsPerYear
  };
}

function recalc() {
  const terms = readLoanTerms();
  const base = getBaseSchedule(terms);
  const extra = runSchedule(terms.principal, terms.ratePerPeriod, terms.totalPeriods, {
    withExtras: true,
    emiOverride: terms.emiOverride,
    extras
  });
  const metrics = buildLoanMetrics(terms, base, extra);

  renderMetrics(elements.metrics, metrics, formatCurrency);

  latest = { ...metrics, principal: terms.principal };
  staleTables.period = true;
  staleTables.yearly = true;
  renderResults();
}

/**
 * Draw the visible results view from the latest calculation: the charts, or
 * the summary and only the visible table. The hidden view is redrawn when it
 * is shown.
 *
 * @param {{ syncAll?: boolean }} [options] - `syncAll` also redraws charts that are off screen.
 * @returns {void}
 */
function renderResults({ syncAll = false } = {}) {
  if (!latest) {
    return;
  }

  const { base, extra, principal, savings, label, periodsPerYear } = latest;
  if (!elements.chartsWrap.hidden) {
    charts = renderCharts({
      charts,
      elements: getChartElements(elements),
      base,
      extra,
      principal,
      interestSaved: savings,
      periodLabel: label,
      formatCurrency,
      formatDollarTick,
      syncAll
    });
    return;
  }

  const { totalEmi, totalPrincipal, totalInterest, totalExtras } = summarizeScheduleRows(
    extra.rows
  );
  renderTableSummary(elements.tableSummary, {
    totalEmi: formatCurrency(totalEmi),
    totalPrincipal: formatCurrency(totalPrincipal),
    totalInterest: formatCurrency(totalInterest),
    totalExtras: totalExtras > 0 ? formatCurrency(totalExtras) : "-",
    periods: String(extra.periods)
  });

  const mode = elements.periodTableWrap.hidden ? "yearly" : "period";
  if (!staleTables[mode]) {
    return;
  }

  if (mode === "period") {
    renderPeriodTable(elements.tbody, extra.rows, formatCurrency);
  } else {
    renderYearlyTable(elements.ybody, extra.rows, principal, periodsPerYear, formatCurrency);
  }
  staleTables[mode] = false;
}
