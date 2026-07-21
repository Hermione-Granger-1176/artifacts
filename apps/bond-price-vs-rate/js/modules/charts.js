import { chartGlobal, createPaletteCache } from "../../../../js/modules/chart-theme.js";

/**
 * @typedef {import("chart.js").Chart} ChartInstance
 * @typedef {ReturnType<typeof colors>} Palette
 * @typedef {{ priceRate: ChartInstance, sensitivity: ChartInstance, yieldCurve: ChartInstance }} Charts
 * @typedef {{ type?: string, title?: object, ticks?: object, grid?: object }} AxisConfig
 * @typedef {{
 *   palette: Palette,
 *   priceRate: MarkedSeries,
 *   sensitivity: { labels: string[], values: number[], currentIndex: number },
 *   yieldCurve: MarkedSeries
 * }} ChartState
 */

/**
 * Format an axis tick as a percent with exactly two decimals, so Chart.js
 * auto-generated steps never leak floating-point noise and every tick lines
 * up (e.g. 4.800000000000001 renders as "4.80%" and 5 as "5.00%").
 * @param {number} value - Raw tick value.
 * @returns {string} Fixed two-decimal percent label.
 */
function formatPercentTick(value) {
  return `${value.toFixed(2)}%`;
}

// Per-theme chart palette read from CSS custom properties; refreshPalette
// keeps the app's theme-change contract.
const { colors, refreshPalette } = createPaletteCache(({ css, cssAlpha }) => ({
  blue: css("--color-blue"),
  green: css("--color-green"),
  red: css("--color-red"),
  amber: css("--color-amber"),
  noteRed: css("--note-red"),
  blueA(/** @type {number} */ alpha) {
    return cssAlpha("--note-blue", alpha);
  },
  redA(/** @type {number} */ alpha) {
    return cssAlpha("--note-red", alpha);
  },
  amberA(/** @type {number} */ alpha) {
    return cssAlpha("--note-amber", alpha);
  },
  surface: css("--color-surface"),
  tick: css("--chart-tick"),
  grid: css("--chart-grid")
}));

export { refreshPalette };

/**
 * @param {import("chart.js").ChartOptions["scales"]} scales - Chart scale options.
 * @param {Palette} palette - Active color palette.
 * @param {{ xTitle: string, yTitle: string, xType?: string, formatY: (value: number) => string }} axisOptions - Axis titles, x scale type, and y tick formatter.
 * @returns {void}
 */
function applyAxes(scales, palette, { xTitle, yTitle, xType = "category", formatY }) {
  if (!scales) {
    return;
  }
  const xScale = /** @type {AxisConfig} */ (scales.x);
  const yScale = /** @type {AxisConfig} */ (scales.y);

  xScale.type = xType;
  xScale.title = { ...xScale.title, display: true, text: xTitle, color: palette.tick };
  xScale.ticks = { ...xScale.ticks, color: palette.tick, maxTicksLimit: 12 };
  xScale.grid = { ...xScale.grid, color: palette.grid };

  yScale.title = { ...yScale.title, display: true, text: yTitle, color: palette.tick };
  yScale.ticks = { ...yScale.ticks, color: palette.tick, callback: formatY };
  yScale.grid = { ...yScale.grid, color: palette.grid };
}

/**
 * @param {HTMLCanvasElement} canvas - Target canvas element.
 * @returns {ChartInstance} The created chart.
 */
function createPriceRateChart(canvas) {
  return new (chartGlobal().Chart)(canvas, {
    type: "line",
    data: {
      datasets: [
        {
          label: "Price",
          data: [],
          fill: true,
          pointRadius: 0,
          borderWidth: 2.5,
          tension: 0.25,
          order: 2
        },
        {
          label: "Your bond",
          data: [],
          showLine: false,
          pointRadius: 6,
          pointHoverRadius: 7,
          pointBorderWidth: 2,
          order: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      parsing: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            /** @param {import("chart.js").TooltipItem<"line">} context - Tooltip item. */
            label(context) {
              return `${context.dataset.label}: $${(context.parsed.y ?? 0).toLocaleString()}`;
            }
          }
        }
      },
      scales: {
        x: { type: "linear", title: {}, ticks: {}, grid: {} },
        y: { title: {}, ticks: {}, grid: {} }
      }
    }
  });
}

/**
 * @param {ChartInstance} chart - Chart to update.
 * @param {ChartState} state - Current chart state.
 * @param {(value: number) => string} formatDollarTick - Dollar tick formatter.
 * @returns {void}
 */
function syncPriceRateChart(chart, state, formatDollarTick) {
  const { palette, priceRate } = state;
  chart.data.datasets[0].data = priceRate.curve;
  chart.data.datasets[0].borderColor = palette.blue;
  chart.data.datasets[0].backgroundColor = palette.blueA(0.08);
  chart.data.datasets[1].data = [priceRate.current];
  chart.data.datasets[1].backgroundColor = palette.green;
  chart.data.datasets[1].borderColor = palette.surface;

  applyAxes(chart.options.scales, palette, {
    xTitle: "Market interest rate (%)",
    yTitle: "Price",
    xType: "linear",
    formatY: formatDollarTick
  });
  chart.update();
}

/**
 * @param {HTMLCanvasElement} canvas - Target canvas element.
 * @returns {ChartInstance} The created chart.
 */
function createYieldCurveChart(canvas) {
  return new (chartGlobal().Chart)(canvas, {
    type: "line",
    data: {
      datasets: [
        {
          label: "Curve yield",
          data: [],
          fill: true,
          pointRadius: 0,
          borderWidth: 2.5,
          tension: 0.25,
          order: 2
        },
        {
          label: "Your maturity",
          data: [],
          showLine: false,
          pointRadius: 6,
          pointHoverRadius: 7,
          pointBorderWidth: 2,
          order: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      parsing: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            /** @param {import("chart.js").TooltipItem<"line">} context - Tooltip item. */
            label(context) {
              return `${context.dataset.label}: ${(context.parsed.y ?? 0).toFixed(2)}%`;
            }
          }
        }
      },
      scales: {
        x: { type: "linear", title: {}, ticks: {}, grid: {} },
        y: { title: {}, ticks: {}, grid: {} }
      }
    }
  });
}

/**
 * @param {ChartInstance} chart - Chart to update.
 * @param {ChartState} state - Current chart state.
 * @returns {void}
 */
function syncYieldCurveChart(chart, state) {
  const { palette, yieldCurve } = state;
  chart.data.datasets[0].data = yieldCurve.curve;
  chart.data.datasets[0].borderColor = palette.amber;
  chart.data.datasets[0].backgroundColor = palette.amberA(0.08);
  chart.data.datasets[1].data = [yieldCurve.current];
  chart.data.datasets[1].backgroundColor = palette.green;
  chart.data.datasets[1].borderColor = palette.surface;

  applyAxes(chart.options.scales, palette, {
    xTitle: "Years to maturity",
    yTitle: "Yield (%)",
    xType: "linear",
    formatY: formatPercentTick
  });
  chart.update();
}

/**
 * @param {HTMLCanvasElement} canvas - Target canvas element.
 * @returns {ChartInstance} The created chart.
 */
function createSensitivityChart(canvas) {
  return new (chartGlobal().Chart)(canvas, {
    type: "bar",
    data: {
      labels: [],
      datasets: [{ label: "Price change", data: [], borderWidth: 1.5 }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            /** @param {import("chart.js").TooltipItem<"bar">} context - Tooltip item. */
            label(context) {
              return `${(context.parsed.y ?? 0).toFixed(1)}%`;
            }
          }
        }
      },
      scales: {
        x: { title: {}, ticks: {}, grid: {} },
        y: { title: {}, ticks: {}, grid: {} }
      }
    }
  });
}

/**
 * @param {ChartInstance} chart - Chart to update.
 * @param {ChartState} state - Current chart state.
 * @returns {void}
 */
function syncSensitivityChart(chart, state) {
  const { palette, sensitivity } = state;
  chart.data.labels = sensitivity.labels;
  chart.data.datasets[0].data = sensitivity.values;
  chart.data.datasets[0].backgroundColor = sensitivity.values.map((/** @type {number} */ _value, /** @type {number} */ index) =>
    index === sensitivity.currentIndex ? palette.red : palette.redA(0.45)
  );
  chart.data.datasets[0].borderColor = palette.noteRed;
  applyAxes(chart.options.scales, palette, {
    xTitle: "Years to maturity",
    yTitle: "Price change (%)",
    formatY: formatPercentTick
  });
  chart.update();
}

/**
 * @param {Record<string, HTMLElement>} elements - Canvas elements keyed by chart name.
 * @returns {Charts} Chart instances.
 */
function createCharts(elements) {
  return {
    priceRate: createPriceRateChart(/** @type {HTMLCanvasElement} */ (elements.priceRateChart)),
    sensitivity: createSensitivityChart(/** @type {HTMLCanvasElement} */ (elements.sensitivityChart)),
    yieldCurve: createYieldCurveChart(/** @type {HTMLCanvasElement} */ (elements.yieldCurveChart))
  };
}

/**
 * @param {Charts} charts - Chart instances.
 * @param {ChartState} state - Current chart state.
 * @param {(value: number) => string} formatDollarTick - Dollar tick formatter.
 * @returns {void}
 */
function syncCharts(charts, state, formatDollarTick) {
  syncPriceRateChart(charts.priceRate, state, formatDollarTick);
  syncSensitivityChart(charts.sensitivity, state);
  syncYieldCurveChart(charts.yieldCurve, state);
}

/**
 * @typedef {{ curve: Array<{ x: number, y: number }>, current: { x: number, y: number } }} MarkedSeries
 * @typedef {{
 *   charts?: Partial<Charts>,
 *   elements: Record<string, HTMLElement>,
 *   priceRate: MarkedSeries,
 *   sensitivity: { labels: string[], values: number[], currentIndex: number },
 *   yieldCurve: MarkedSeries,
 *   formatDollarTick: (value: number) => string
 * }} ChartRenderOptions
 */

/**
 * Create or update the three explainer chart instances.
 * @param {ChartRenderOptions} options - Chart data and formatting callbacks.
 * @returns {Charts} Chart instances keyed by name.
 */
export function renderCharts({
  charts = {},
  elements,
  priceRate,
  sensitivity,
  yieldCurve,
  formatDollarTick
}) {
  const nextCharts = charts.priceRate ? /** @type {Charts} */ (charts) : createCharts(elements);
  const state = { palette: colors(), priceRate, sensitivity, yieldCurve };
  syncCharts(nextCharts, state, formatDollarTick);
  return nextCharts;
}
