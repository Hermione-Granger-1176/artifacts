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
import { formatCurrency, formatDollarTick, parseNumber } from "./modules/formatting.js";
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

let elements = {};
let extras = [];
let nextExtraId = 0;
let charts = {};
let bwMode = "true";
let pendingRecalcFrame = null;

renderAppShell();

initializeMatureApp({
  onErrorContext: "loan amortization initialization",
  run: () => {
    elements = cacheElements();
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
  bindEvents({
    elements,
    onSliderInput: () => {
      syncInputsFromSliders(elements);
      scheduleRecalc();
    },
    onPrincipalCommit: () => {
      syncInputsFromSliders(elements);
      recalc();
    },
    onRateCommit: () => {
      syncInputsFromSliders(elements);
      recalc();
    },
    onTenureCommit: () => {
      syncInputsFromSliders(elements);
      recalc();
    },
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

function handleExtraListClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) {
    return;
  }

  const extraId = Number(button.closest("[data-extra-id]")?.dataset.extraId);
  if (Number.isNaN(extraId)) {
    return;
  }

  const actions = {
    "remove-extra": () => {
      extras = removeExtraById(extras, extraId);
    },
    "set-type": () => {
      setExtraType(extras, extraId, button.dataset.type);
    }
  };

  const action = actions[button.dataset.action];
  if (!action) {
    return;
  }

  action();
  renderExtrasSection();
  recalc();
}

function handleExtraListInput(event) {
  const input = event.target.closest("input[data-field]");
  if (!input) {
    return;
  }

  const extraId = Number(input.closest("[data-extra-id]")?.dataset.extraId);
  if (Number.isNaN(extraId)) {
    return;
  }

  updateExtraField(extras, extraId, input.dataset.field, input.value);
  const extra = extras.find((item) => item.id === extraId);
  const tip = input.closest(".extra-item")?.querySelector(".info-tip");
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
