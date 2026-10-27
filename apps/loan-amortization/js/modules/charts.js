import { chartGlobal, createPaletteCache } from "../../../../js/modules/chart-theme.js";
import { createOffscreenDraws } from "../../../../js/modules/offscreen-draws.js";

/**
 * @typedef {import("chart.js").Chart} ChartInstance
 * @typedef {ReturnType<typeof colors>} Palette
 * @typedef {import("chartjs-plugin-datalabels/types/context").Context} DataLabelsContext
 * @typedef {import('./amortization.js').ScheduleResult} ScheduleResult
 * @typedef {{ type?: string, beginAtZero?: boolean, stacked?: boolean, title?: object, ticks?: object, grid?: object }} AxisConfig
 * @typedef {{
 *   annotation: object,
 *   base: ScheduleResult,
 *   extra: ScheduleResult,
 *   interestPaid: number,
 *   interestSaved: number,
 *   interestTotal: number,
 *   lineLabels: number[],
 *   maxPeriods: number,
 *   palette: Palette,
 *   periodLabel: string,
 *   principal: number
 * }} ChartState
 * @typedef {{ balance: ChartInstance, comparison: ChartInstance, savings: ChartInstance, cumulative: ChartInstance, period: ChartInstance }} Charts
 */

// Per-theme chart palette read from CSS custom properties; refreshPalette
// keeps the app's theme-change contract.
const { colors, refreshPalette } = createPaletteCache(({ css, cssAlpha }) => ({
  blue: css("--color-blue"),
  green: css("--color-green"),
  red: css("--color-red"),
  noteBlue: css("--note-blue"),
  noteGreen: css("--note-green"),
  noteRed: css("--note-red"),
  blueA(/** @type {number} */ alpha) {
    return cssAlpha("--note-blue", alpha);
  },
  greenA(/** @type {number} */ alpha) {
    return cssAlpha("--note-green", alpha);
  },
  redA(/** @type {number} */ alpha) {
    return cssAlpha("--note-red", alpha);
  },
  redText: css("--color-red-text"),
  greenText: css("--color-green-text"),
  redEmphasis: css("--color-red-emphasis"),
  greenEmphasis: css("--color-green-emphasis"),
  surface: css("--color-surface"),
  tick: css("--chart-tick"),
  grid: css("--chart-grid"),
  annotationBorder: css("--chart-annotation-border"),
  annotationBg: css("--chart-annotation-bg"),
  annotationText: css("--chart-annotation-text")
}));

export { refreshPalette };

/**
 * @param {number[]} values - Values to pad.
 * @param {number} length - Target length.
 * @returns {number[]} Padded values.
 */
function pad(values, length) {
  if (values.length >= length) {
    return [...values];
  }
  return [...values, ...new Array(length - values.length).fill(0)];
}

/**
 * @param {{ base: ScheduleResult, extra: ScheduleResult, principal: number, interestSaved: number, periodLabel: string }} params - Schedule inputs.
 * @returns {ChartState} Derived chart render state.
 */
function buildChartState({ base, extra, principal, interestSaved, periodLabel }) {
  const palette = colors();
  const maxPeriods = Math.max(base.periods, extra.periods);
  const lineLabels = Array.from({ length: maxPeriods }, (_, index) => index + 1);
  const interestPaid = Math.round(extra.totalInterest);
  const roundedInterestSaved = Math.max(0, Math.round(interestSaved));
  const interestTotal = interestPaid + roundedInterestSaved || 1;

  return {
    annotation:
      extra.breakEven
        ? {
            annotations: {
              breakEvenLine: {
                type: "line",
                xMin: extra.breakEven - 1,
                xMax: extra.breakEven - 1,
                borderColor: palette.annotationBorder,
                borderWidth: 1.5,
                borderDash: [4, 4],
                label: {
                  display: true,
                  content: "Break-even",
                  position: "start",
                  backgroundColor: palette.annotationBg,
                  color: palette.annotationText,
                  font: { size: 11 },
                  padding: 4
                }
              }
            }
          }
        : { annotations: {} },
    base,
    extra,
    interestPaid,
    interestSaved: roundedInterestSaved,
    interestTotal,
    lineLabels,
    maxPeriods,
    palette,
    periodLabel,
    principal
  };
}

/**
 * The axis setup each chart was last given. Rewriting the scale options makes
 * Chart.js resolve them again, so a slider tick that changes only the data skips it.
 * @type {WeakMap<ChartInstance, { palette: Palette, formatDollarTick: (value: number) => string, key: string }>}
 */
const appliedAxes = new WeakMap();

/**
 * @param {ChartInstance} chart - Chart whose scales to style.
 * @param {Palette} palette - Active color palette.
 * @param {string} periodLabel - Default x axis label.
 * @param {(value: number) => string} formatDollarTick - Y tick formatter.
 * @param {{ stackedY?: boolean, showXGrid?: boolean, xTitle?: string, yTitle?: string | null }} [options={}] - Axis options.
 * @returns {void}
 */
function applyAxes(chart, palette, periodLabel, formatDollarTick, options = {}) {
  const scales = chart.options.scales;
  if (!scales) {
    return;
  }
  const {
    stackedY = false,
    showXGrid = true,
    xTitle = periodLabel,
    yTitle = null
  } = options;
  const key = `${stackedY}|${showXGrid}|${xTitle}|${yTitle}`;
  const applied = appliedAxes.get(chart);
  if (applied?.palette === palette && applied.formatDollarTick === formatDollarTick && applied.key === key) {
    return;
  }
  appliedAxes.set(chart, { palette, formatDollarTick, key });
  const xScale = /** @type {AxisConfig} */ (scales.x);
  const yScale = /** @type {AxisConfig} */ (scales.y);

  xScale.title = { ...xScale.title, display: true, text: xTitle, color: palette.tick };
  xScale.ticks = { ...xScale.ticks, color: palette.tick, maxTicksLimit: 12 };
  xScale.grid = { ...xScale.grid, color: palette.grid, display: showXGrid };

  yScale.beginAtZero = true;
  yScale.stacked = stackedY;
  if (yTitle) {
    yScale.title = { ...yScale.title, display: true, text: yTitle, color: palette.tick };
  }
  yScale.ticks = { ...yScale.ticks, color: palette.tick, callback: formatDollarTick };
  yScale.grid = { ...yScale.grid, color: palette.grid };
}

/**
 * @param {import("chart.js").TooltipItem<"line" | "bar">} context - Tooltip item.
 * @returns {string} "Series: $1,234" tooltip label.
 */
function dollarTooltipLabel(context) {
  return `${context.dataset.label}: $${(context.parsed.y ?? 0).toLocaleString()}`;
}

/**
 * Options shared by the line and bar charts: responsive, no legend, dollar tooltips.
 * @param {object} scales - Axis skeletons that applyAxes fills in later.
 * @param {object} [plugins={}] - Extra plugin options.
 * @returns {object} Chart options.
 */
function dollarChartOptions(scales, plugins = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      ...plugins,
      tooltip: { callbacks: { label: dollarTooltipLabel } }
    },
    scales
  };
}

/**
 * A filled, point-free line series; colors are set on each sync.
 * @param {string} label - Series label.
 * @param {number} borderWidth - Line width.
 * @param {object} [extra={}] - Extra dataset options.
 * @returns {object} Dataset config.
 */
function areaDataset(label, borderWidth, extra = {}) {
  return { label, data: [], fill: true, pointRadius: 0, borderWidth, tension: 0.3, ...extra };
}

/**
 * Point one dataset at new data and colors.
 * @param {import("chart.js").ChartDataset} dataset - Dataset to update.
 * @param {number[]} data - Values.
 * @param {string} borderColor - Line color.
 * @param {string} backgroundColor - Fill color.
 * @returns {void}
 */
function paintDataset(dataset, data, borderColor, backgroundColor) {
  dataset.data = data;
  dataset.borderColor = borderColor;
  dataset.backgroundColor = backgroundColor;
}

/**
 * @param {HTMLCanvasElement} canvas - Target canvas element.
 * @returns {ChartInstance} The created chart.
 */
function createBalanceChart(canvas) {
  return new (chartGlobal().Chart)(canvas, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        areaDataset("Without extras", 2, { borderDash: [6, 3] }),
        areaDataset("With extras", 2.5)
      ]
    },
    options: dollarChartOptions({
      x: { title: {}, ticks: {}, grid: {} },
      y: { title: {}, ticks: {}, grid: {} }
    })
  });
}

/**
 * @param {ChartInstance} chart - Chart to update.
 * @param {ChartState} state - Current chart state.
 * @param {(value: number) => string} formatDollarTick - Y tick formatter.
 * @param {import("chart.js").UpdateMode} [mode] - Update mode; `"none"` skips the animation.
 * @returns {void}
 */
function syncBalanceChart(chart, state, formatDollarTick, mode) {
  const { base, extra, maxPeriods, lineLabels, palette, periodLabel } = state;
  chart.data.labels = lineLabels;
  const [withoutExtras, withExtras] = chart.data.datasets;
  paintDataset(withoutExtras, pad(base.balances, maxPeriods), palette.blue, palette.blueA(0.08));
  paintDataset(withExtras, pad(extra.balances, maxPeriods), palette.green, palette.greenA(0.08));
  applyAxes(chart, palette, periodLabel, formatDollarTick, {
    yTitle: "Balance"
  });
  chart.update(mode);
}

/**
 * @param {HTMLCanvasElement} canvas - Target canvas element.
 * @returns {ChartInstance} The created chart.
 */
function createComparisonChart(canvas) {
  return new (chartGlobal().Chart)(canvas, {
    type: "bar",
    data: {
      labels: ["Without extras", "With extras"],
      datasets: [
        { label: "Principal", data: [] },
        { label: "Interest", data: [] },
        { label: "Extras", data: [] }
      ]
    },
    options: dollarChartOptions({
      x: { ticks: {}, grid: {} },
      y: { ticks: {}, grid: {} }
    })
  });
}

/**
 * @param {ChartInstance} chart - Chart to update.
 * @param {ChartState} state - Current chart state.
 * @param {(value: number) => string} formatDollarTick - Y tick formatter.
 * @param {import("chart.js").UpdateMode} [mode] - Update mode; `"none"` skips the animation.
 * @returns {void}
 */
function syncComparisonChart(chart, state, formatDollarTick, mode) {
  const { base, extra, palette, principal } = state;
  chart.data.datasets[0].data = [principal, Math.max(0, Math.round(principal - extra.totalExtra))];
  chart.data.datasets[0].backgroundColor = palette.blue;
  chart.data.datasets[1].data = [Math.round(base.totalInterest), Math.round(extra.totalInterest)];
  chart.data.datasets[1].backgroundColor = palette.noteRed;
  chart.data.datasets[2].data = [0, Math.round(extra.totalExtra)];
  chart.data.datasets[2].backgroundColor = palette.noteGreen;
  applyAxes(chart, palette, state.periodLabel, formatDollarTick, {
    showXGrid: false,
    stackedY: true,
    xTitle: "Comparison"
  });
  const compScales = /** @type {Record<string, AxisConfig>} */ (/** @type {unknown} */ (chart.options.scales));
  compScales.x.stacked = true;
  chart.update(mode);
}

/**
 * @param {HTMLCanvasElement} canvas - Target canvas element.
 * @returns {ChartInstance} The created chart.
 */
function createSavingsChart(canvas) {
  return new (chartGlobal().Chart)(canvas, {
    type: "doughnut",
    data: {
      labels: ["Interest paid", "Interest saved"],
      datasets: [
        {
          data: [],
          borderWidth: 2,
          hoverOffset: 4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "55%",
      layout: {
        padding: { top: 30, right: 30, bottom: 30, left: 30 }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            /** @param {import("chart.js").TooltipItem<"doughnut">} context - Tooltip item. */
            label(context) {
              return `${context.label}: $${context.parsed.toLocaleString()}`;
            }
          }
        },
        datalabels: {
          /** @param {DataLabelsContext} context - Datalabels context. */
          display(context) {
            const value = /** @type {number} */ (context.dataset.data[context.dataIndex]);
            const total = context.chart.$artifactsInterestTotal || 1;
            return value > 0 && value / total <= 0.95;
          },
          anchor: "end",
          align: "end",
          offset: 8,
          /** @param {DataLabelsContext} context - Datalabels context. */
          color(context) {
            const palette = context.chart.$artifactsPalette;
            if (!palette) {
              return "currentColor";
            }
            return context.dataIndex === 0 ? palette.redEmphasis : palette.greenEmphasis;
          },
          font: { weight: 500, size: 12 },
          textAlign: "center",
          /**
           * @param {*} value - Datum value (untyped upstream).
           * @param {DataLabelsContext} context - Datalabels context.
           * @returns {string} Formatted label.
           */
          formatter(value, context) {
            const total = context.chart.$artifactsInterestTotal || 1;
            const percentage = Math.round((value / total) * 100);
            const formatCurrencyFn = context.chart.$artifactsFormatCurrency;
            if (typeof formatCurrencyFn !== "function") {
              return `${percentage}%`;
            }
            return `${percentage}%\n${formatCurrencyFn(value)}`;
          }
        }
      }
    },
    plugins: [chartGlobal().ChartDataLabels, {
      id: "centerText",
      /** @param {ChartInstance} chart - Chart being drawn. */
      afterDraw(chart) {
        const dataset = /** @type {number[]} */ (chart.data.datasets[0].data);
        const total = chart.$artifactsInterestTotal || dataset.reduce((sum, value) => sum + value, 0);
        const palette = chart.$artifactsPalette;
        const formatCurrencyFn = chart.$artifactsFormatCurrency;
        if (!palette || typeof formatCurrencyFn !== "function") {
          return;
        }
        if (total === 0) {
          return;
        }

        const dominantIndex = dataset.findIndex((value) => value / total > 0.95);
        if (dominantIndex === -1) {
          return;
        }

        const {
          ctx,
          chartArea: { left, right, top, bottom }
        } = chart;
        const centerX = (left + right) / 2;
        const centerY = (top + bottom) / 2;
        const percentage = `${Math.round((dataset[dominantIndex] / total) * 100)}%`;
        const amount = formatCurrencyFn(dataset[dominantIndex]);

        ctx.save();
        ctx.textAlign = "center";
        ctx.fillStyle = dominantIndex === 0 ? palette.redEmphasis : palette.greenEmphasis;
        ctx.font = '500 22px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.fillText(percentage, centerX, centerY - 4);
        ctx.font = '500 13px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.fillText(amount, centerX, centerY + 14);
        ctx.restore();
      }
    }]
  });
}

/**
 * @param {ChartInstance} chart - Chart to update.
 * @param {ChartState} state - Current chart state.
 * @param {(value: number) => string} formatCurrency - Currency formatter.
 * @param {import("chart.js").UpdateMode} [mode] - Update mode; `"none"` skips the animation.
 * @returns {void}
 */
function syncSavingsChart(chart, state, formatCurrency, mode) {
  const { interestPaid, interestSaved, interestTotal, palette } = state;
  chart.$artifactsFormatCurrency = formatCurrency;
  chart.$artifactsInterestTotal = interestTotal;
  chart.$artifactsPalette = palette;
  chart.data.datasets[0].data = [interestPaid, interestSaved];
  chart.data.datasets[0].backgroundColor = [palette.noteRed, palette.noteGreen];
  chart.data.datasets[0].borderColor = palette.surface;
  chart.update(mode);
}

/**
 * @param {HTMLCanvasElement} canvas - Target canvas element.
 * @returns {ChartInstance} The created chart.
 */
function createCumulativeChart(canvas) {
  return new (chartGlobal().Chart)(canvas, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        areaDataset("Cumulative principal", 2),
        areaDataset("Cumulative extras", 2),
        areaDataset("Cumulative interest", 2)
      ]
    },
    options: dollarChartOptions(
      {
        x: { title: {}, ticks: {}, grid: {} },
        y: { ticks: {}, grid: {} }
      },
      { annotation: { annotations: {} } }
    )
  });
}

/**
 * @param {ChartInstance} chart - Chart to update.
 * @param {ChartState} state - Current chart state.
 * @param {(value: number) => string} formatDollarTick - Y tick formatter.
 * @param {import("chart.js").UpdateMode} [mode] - Update mode; `"none"` skips the animation.
 * @returns {void}
 */
function syncCumulativeChart(chart, state, formatDollarTick, mode) {
  const { extra, palette, periodLabel } = state;
  chart.data.labels = extra.rows.map((row) => row.period);
  const [principalSeries, extraSeries, interestSeries] = chart.data.datasets;
  paintDataset(principalSeries, extra.cumulativePrincipal, palette.blue, palette.blueA(0.1));
  paintDataset(extraSeries, extra.cumulativeExtra, palette.green, palette.greenA(0.1));
  paintDataset(interestSeries, extra.cumulativeInterest, palette.red, palette.redA(0.1));
  /** @type {Record<string, unknown>} */ (chart.options.plugins).annotation = state.annotation;
  applyAxes(chart, palette, periodLabel, formatDollarTick);
  chart.update(mode);
}

/**
 * @param {HTMLCanvasElement} canvas - Target canvas element.
 * @returns {ChartInstance} The created chart.
 */
function createPeriodChart(canvas) {
  return new (chartGlobal().Chart)(canvas, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        areaDataset("Principal", 1.5, { order: 3 }),
        areaDataset("Extra payment", 1.5, { order: 2 }),
        areaDataset("Interest", 1.5, { order: 1 })
      ]
    },
    options: dollarChartOptions({
      x: { title: {}, ticks: {}, grid: {} },
      y: { ticks: {}, grid: {} }
    })
  });
}

/**
 * @param {ChartInstance} chart - Chart to update.
 * @param {ChartState} state - Current chart state.
 * @param {(value: number) => string} formatDollarTick - Y tick formatter.
 * @param {import("chart.js").UpdateMode} [mode] - Update mode; `"none"` skips the animation.
 * @returns {void}
 */
function syncPeriodChart(chart, state, formatDollarTick, mode) {
  const { extra, palette, periodLabel } = state;
  chart.data.labels = extra.rows.map((row) => row.period);
  const [principalSeries, extraSeries, interestSeries] = chart.data.datasets;
  paintDataset(principalSeries, extra.principalParts, palette.blue, palette.blueA(0.4));
  paintDataset(extraSeries, extra.extraParts, palette.green, palette.greenA(0.4));
  paintDataset(interestSeries, extra.interestParts, palette.red, palette.redA(0.45));
  applyAxes(chart, palette, periodLabel, formatDollarTick, {
    stackedY: true
  });
  chart.update(mode);
}

/**
 * @param {Record<string, HTMLElement>} elements - Canvas elements keyed by chart name.
 * @returns {Charts} Chart instances.
 */
function createCharts(elements) {
  return {
    balance: createBalanceChart(/** @type {HTMLCanvasElement} */ (elements.balanceChart)),
    comparison: createComparisonChart(/** @type {HTMLCanvasElement} */ (elements.compChart)),
    savings: createSavingsChart(/** @type {HTMLCanvasElement} */ (elements.savingsChart)),
    cumulative: createCumulativeChart(/** @type {HTMLCanvasElement} */ (elements.cumulChart)),
    period: createPeriodChart(/** @type {HTMLCanvasElement} */ (elements.periodChart))
  };
}

/**
 * @typedef {keyof Charts} ChartName
 * @typedef {{ formatCurrency: (value: number) => string, formatDollarTick: (value: number) => string }} Formatters
 * @typedef {{
 *   state: ChartState,
 *   formatters: Formatters,
 *   drawn: Set<ChartName>,
 *   offscreen: import("../../../../js/modules/offscreen-draws.js").OffscreenDraws
 * }} ChartsController
 */

/** @type {Record<ChartName, (chart: ChartInstance, state: ChartState, formatters: Formatters, mode?: import("chart.js").UpdateMode) => void>} */
const SYNCS = {
  balance: (chart, state, { formatDollarTick }, mode) => syncBalanceChart(chart, state, formatDollarTick, mode),
  comparison: (chart, state, { formatDollarTick }, mode) =>
    syncComparisonChart(chart, state, formatDollarTick, mode),
  savings: (chart, state, { formatCurrency }, mode) => syncSavingsChart(chart, state, formatCurrency, mode),
  cumulative: (chart, state, { formatDollarTick }, mode) =>
    syncCumulativeChart(chart, state, formatDollarTick, mode),
  period: (chart, state, { formatDollarTick }, mode) => syncPeriodChart(chart, state, formatDollarTick, mode)
};

/** @type {ChartName[]} */
const CHART_NAMES = ["balance", "comparison", "savings", "cumulative", "period"];

/** @type {WeakMap<Charts, ChartsController>} */
const controllers = new WeakMap();

/**
 * Draw one chart from the latest state. A chart's first draw keeps Chart.js's
 * entrance animation; every later draw is immediate, so a slider drag does not
 * replay a one second animation on each tick.
 *
 * @param {Charts} charts - Chart instances.
 * @param {ChartsController} controller - Latest state and per-chart bookkeeping.
 * @param {ChartName} name - Chart to draw.
 * @returns {void}
 */
function syncChart(charts, controller, name) {
  SYNCS[name](charts[name], controller.state, controller.formatters, controller.drawn.has(name) ? "none" : undefined);
  controller.drawn.add(name);
}

/**
 * @param {Charts} charts - Chart instances.
 * @param {ChartState} state - Initial chart state.
 * @param {Formatters} formatters - Value formatters.
 * @returns {ChartsController} The controller kept for these charts.
 */
function createController(charts, state, formatters) {
  /** @type {ChartsController} */
  const controller = {
    state,
    formatters,
    drawn: new Set(),
    offscreen: createOffscreenDraws(CHART_NAMES.map((name) => charts[name].canvas))
  };
  controllers.set(charts, controller);
  return controller;
}

/**
 * @typedef {{
 *   charts?: Partial<Charts>,
 *   elements: Record<string, HTMLElement>,
 *   base: import('./amortization.js').ScheduleResult,
 *   extra: import('./amortization.js').ScheduleResult,
 *   principal: number,
 *   interestSaved: number,
 *   periodLabel: string,
 *   formatCurrency: (value: number) => string,
 *   formatDollarTick: (value: number) => string,
 *   syncAll?: boolean
 * }} ChartRenderOptions
 */

/**
 * Create or update the loan amortization charts. Charts far off screen are not
 * redrawn: they keep their latest redraw until they scroll into view. The
 * first call, and calls with `syncAll` (such as showing the charts view again),
 * draw every chart.
 * @param {ChartRenderOptions} options - Chart data and formatting callbacks.
 * @returns {Charts} Chart instances keyed by name.
 */
export function renderCharts({
  charts = {},
  elements,
  base,
  extra,
  principal,
  interestSaved,
  periodLabel,
  formatCurrency,
  formatDollarTick,
  syncAll = false
}) {
  const created = !charts.balance;
  const nextCharts = created ? createCharts(elements) : /** @type {Charts} */ (charts);
  const state = buildChartState({
    base,
    extra,
    principal,
    interestSaved,
    periodLabel
  });
  const formatters = { formatCurrency, formatDollarTick };
  const controller = controllers.get(nextCharts) ?? createController(nextCharts, state, formatters);
  controller.state = state;
  controller.formatters = formatters;

  for (const name of CHART_NAMES) {
    controller.offscreen.draw(nextCharts[name].canvas, () => syncChart(nextCharts, controller, name), created || syncAll);
  }
  return nextCharts;
}
