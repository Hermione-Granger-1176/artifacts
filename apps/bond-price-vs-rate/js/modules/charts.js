import { chartGlobal, createPaletteCache } from "../../../../js/modules/chart-theme.js";

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
  blueA(alpha) {
    return cssAlpha("--note-blue", alpha);
  },
  redA(alpha) {
    return cssAlpha("--note-red", alpha);
  },
  amberA(alpha) {
    return cssAlpha("--note-amber", alpha);
  },
  surface: css("--color-surface"),
  tick: css("--chart-tick"),
  grid: css("--chart-grid")
}));

export { refreshPalette };

function applyAxes(scales, palette, { xTitle, yTitle, xType = "category", formatY }) {
  const xScale = scales.x;
  const yScale = scales.y;

  xScale.type = xType;
  xScale.title = { ...xScale.title, display: true, text: xTitle, color: palette.tick };
  xScale.ticks = { ...xScale.ticks, color: palette.tick, maxTicksLimit: 12 };
  xScale.grid = { ...xScale.grid, color: palette.grid };

  yScale.title = { ...yScale.title, display: true, text: yTitle, color: palette.tick };
  yScale.ticks = { ...yScale.ticks, color: palette.tick, callback: formatY };
  yScale.grid = { ...yScale.grid, color: palette.grid };
}

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
            label(context) {
              return `${context.dataset.label}: $${context.parsed.y.toLocaleString()}`;
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
            label(context) {
              return `${context.dataset.label}: ${context.parsed.y.toFixed(2)}%`;
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
            label(context) {
              return `${context.parsed.y.toFixed(1)}%`;
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

function syncSensitivityChart(chart, state) {
  const { palette, sensitivity } = state;
  chart.data.labels = sensitivity.labels;
  chart.data.datasets[0].data = sensitivity.values;
  chart.data.datasets[0].backgroundColor = sensitivity.values.map((_value, index) =>
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

function createCharts(elements) {
  return {
    priceRate: createPriceRateChart(elements.priceRateChart),
    sensitivity: createSensitivityChart(elements.sensitivityChart),
    yieldCurve: createYieldCurveChart(elements.yieldCurveChart)
  };
}

function syncCharts(charts, state, formatDollarTick) {
  syncPriceRateChart(charts.priceRate, state, formatDollarTick);
  syncSensitivityChart(charts.sensitivity, state);
  syncYieldCurveChart(charts.yieldCurve, state);
}

/**
 * @typedef {{ curve: Array<{ x: number, y: number }>, current: { x: number, y: number } }} MarkedSeries
 * @typedef {{
 *   charts?: Record<string, any>,
 *   elements: Record<string, any>,
 *   priceRate: MarkedSeries,
 *   sensitivity: { labels: string[], values: number[], currentIndex: number },
 *   yieldCurve: MarkedSeries,
 *   formatDollarTick: (value: number) => string
 * }} ChartRenderOptions
 */

/**
 * Create or update the three explainer chart instances.
 * @param {ChartRenderOptions} options - Chart data and formatting callbacks.
 * @returns {Record<string, any>} Chart instances keyed by name.
 */
export function renderCharts({
  charts = {},
  elements,
  priceRate,
  sensitivity,
  yieldCurve,
  formatDollarTick
}) {
  const nextCharts = charts.priceRate ? charts : createCharts(elements);
  const state = { palette: colors(), priceRate, sensitivity, yieldCurve };
  syncCharts(nextCharts, state, formatDollarTick);
  return nextCharts;
}
