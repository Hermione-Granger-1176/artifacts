import { chartGlobal, createPaletteCache } from "../../../../js/modules/chart-theme.js";
import { formatCurrency, formatPercent } from "../../../../js/modules/formatting.js";
import { createOffscreenDraws } from "../../../../js/modules/offscreen-draws.js";

/**
 * @typedef {import("chart.js").Chart} ChartInstance
 * @typedef {ReturnType<typeof colors>} Palette
 * @typedef {{ priceRate: ChartInstance, sensitivity: ChartInstance, yieldCurve: ChartInstance }} Charts
 * @typedef {keyof Charts} ChartName
 * @typedef {"none" | undefined} UpdateMode
 * @typedef {{ type?: string, title?: object, ticks?: object, grid?: object }} AxisConfig
 * @typedef {{
 *   palette: Palette,
 *   priceRate: MarkedSeries,
 *   sensitivity: SensitivityBars,
 *   yieldCurve: MarkedSeries
 * }} ChartState
 * @typedef {{ labels: string[], prices: number[], losses: number[], currentIndex: number }} SensitivityBars
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

// Chart palette read from CSS custom properties and cached per theme. Call
// refreshPalette after a theme change.
const { colors, refreshPalette } = createPaletteCache(({ css, cssAlpha }) => ({
  blue: css("--color-blue"),
  green: css("--color-green"),
  red: css("--color-red"),
  amber: css("--color-amber"),
  noteRed: css("--color-note-2"),
  heading: css("--color-text-heading"),
  blueA(/** @type {number} */ alpha) {
    return cssAlpha("--color-note-3", alpha);
  },
  redA(/** @type {number} */ alpha) {
    return cssAlpha("--color-note-2", alpha);
  },
  amberA(/** @type {number} */ alpha) {
    return cssAlpha("--color-note-5", alpha);
  },
  surface: css("--color-surface"),
  tick: css("--chart-tick"),
  grid: css("--chart-grid")
}));

export { refreshPalette };

/**
 * The axis setup each chart was last given. Rewriting the scale options makes
 * Chart.js resolve them again, so a slider tick that changes only the data skips it.
 * @type {WeakMap<ChartInstance, { palette: Palette, formatY: (value: number) => string, key: string }>}
 */
const appliedAxes = new WeakMap();

/**
 * @param {ChartInstance} chart - Chart whose scales to style.
 * @param {Palette} palette - Active color palette.
 * @param {{ xTitle: string, yTitle: string, xType?: string, formatY: (value: number) => string }} axisOptions - Axis titles, x scale type, and y tick formatter.
 * @returns {void}
 */
function applyAxes(chart, palette, { xTitle, yTitle, xType = "category", formatY }) {
  const key = `${xTitle}|${yTitle}|${xType}`;
  const applied = appliedAxes.get(chart);
  if (applied?.palette === palette && applied.formatY === formatY && applied.key === key) {
    return;
  }
  appliedAxes.set(chart, { palette, formatY, key });
  // createMarkedSeriesChart gives every chart that reaches here x and y scale skeletons.
  const { x: xScale, y: yScale } = /** @type {Record<"x" | "y", AxisConfig>} */ (
    /** @type {unknown} */ (chart.options.scales)
  );

  xScale.type = xType;
  xScale.title = { ...xScale.title, display: true, text: xTitle, color: palette.tick };
  xScale.ticks = { ...xScale.ticks, color: palette.tick, maxTicksLimit: 12 };
  xScale.grid = { ...xScale.grid, color: palette.grid };

  yScale.title = { ...yScale.title, display: true, text: yTitle, color: palette.tick };
  yScale.ticks = { ...yScale.ticks, color: palette.tick, callback: formatY };
  yScale.grid = { ...yScale.grid, color: palette.grid };
}

/**
 * Create a line chart of one curve plus a single marker for the reader's bond.
 * @param {HTMLCanvasElement} canvas - Target canvas element.
 * @param {{ curveLabel: string, markerLabel: string, formatValue: (value: number) => string }} labels - Series labels and the tooltip value formatter.
 * @returns {ChartInstance} The created chart.
 */
function createMarkedSeriesChart(canvas, { curveLabel, markerLabel, formatValue }) {
  return new (chartGlobal().Chart)(canvas, {
    type: "line",
    data: {
      datasets: [
        {
          label: curveLabel,
          data: [],
          fill: true,
          pointRadius: 0,
          borderWidth: 2.5,
          tension: 0.25,
          order: 2
        },
        {
          label: markerLabel,
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
              return `${context.dataset.label}: ${formatValue(/** @type {number} */ (context.parsed.y))}`;
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
 * Point a marked-series chart at new data and colors, then redraw it.
 * @param {ChartInstance} chart - Chart to update.
 * @param {MarkedSeries} series - Curve points and the marker point.
 * @param {Palette} palette - Active color palette.
 * @param {{ lineColor: string, fillColor: string, xTitle: string, yTitle: string, formatY: (value: number) => string }} style - Curve colors and axis setup.
 * @param {UpdateMode} mode - Chart.js update mode: "none" redraws at once, undefined animates.
 * @returns {void}
 */
function syncMarkedSeriesChart(chart, series, palette, { lineColor, fillColor, xTitle, yTitle, formatY }, mode) {
  chart.data.datasets[0].data = series.curve;
  chart.data.datasets[0].borderColor = lineColor;
  chart.data.datasets[0].backgroundColor = fillColor;
  chart.data.datasets[1].data = [series.current];
  chart.data.datasets[1].backgroundColor = palette.green;
  chart.data.datasets[1].borderColor = palette.surface;

  applyAxes(chart, palette, { xTitle, yTitle, xType: "linear", formatY });
  chart.update(mode);
}

/**
 * @param {HTMLCanvasElement} canvas - Target canvas element.
 * @returns {ChartInstance} The created chart.
 */
function createPriceRateChart(canvas) {
  return createMarkedSeriesChart(canvas, {
    curveLabel: "Price",
    markerLabel: "Your bond",
    formatValue: (value) => `$${value.toLocaleString()}`
  });
}

/**
 * @param {ChartInstance} chart - Chart to update.
 * @param {ChartState} state - Current chart state.
 * @param {(value: number) => string} formatDollarTick - Dollar tick formatter.
 * @param {UpdateMode} mode - Chart.js update mode.
 * @returns {void}
 */
function syncPriceRateChart(chart, state, formatDollarTick, mode) {
  const { palette } = state;
  syncMarkedSeriesChart(
    chart,
    state.priceRate,
    palette,
    {
      lineColor: palette.blue,
      fillColor: palette.blueA(0.08),
      xTitle: "Market interest rate (%)",
      yTitle: "Price",
      formatY: formatDollarTick
    },
    mode
  );
}

/**
 * @param {HTMLCanvasElement} canvas - Target canvas element.
 * @returns {ChartInstance} The created chart.
 */
function createYieldCurveChart(canvas) {
  return createMarkedSeriesChart(canvas, {
    curveLabel: "Curve yield",
    markerLabel: "Your maturity",
    formatValue: (value) => `${value.toFixed(2)}%`
  });
}

/**
 * @param {ChartInstance} chart - Chart to update.
 * @param {ChartState} state - Current chart state.
 * @param {UpdateMode} mode - Chart.js update mode.
 * @returns {void}
 */
function syncYieldCurveChart(chart, state, mode) {
  const { palette } = state;
  syncMarkedSeriesChart(
    chart,
    state.yieldCurve,
    palette,
    {
      lineColor: palette.amber,
      fillColor: palette.amberA(0.08),
      xTitle: "Years to maturity",
      yTitle: "Yield (%)",
      formatY: formatPercentTick
    },
    mode
  );
}

/** Space between a bar's end and its label, and the room kept right of the bars for the widest label. */
const BAR_LABEL_GAP = 8;
const BAR_LABEL_ROOM = 112;

/**
 * What each sensitivity chart was last given: the bars and the label colors,
 * keyed by its canvas. createSensitivityChart seeds an empty entry before
 * Chart.js first draws, and every sync replaces it. The end labels, tick
 * styling, and tooltip read it at draw time.
 * @type {WeakMap<HTMLCanvasElement, { bars: SensitivityBars, palette: Palette }>}
 */
const barStates = new WeakMap();

/**
 * @param {{ canvas: HTMLCanvasElement }} chart - Sensitivity chart.
 * @returns {{ bars: SensitivityBars, palette: Palette }} Its latest bars and colors.
 */
function barState(chart) {
  return /** @type {{ bars: SensitivityBars, palette: Palette }} */ (barStates.get(chart.canvas));
}

/**
 * The label beside a sensitivity bar: the price after the rise and the dollars lost.
 * @param {SensitivityBars} bars - Sensitivity bars.
 * @param {number} index - Bar index.
 * @returns {string} Label text, e.g. "$926 (-$74)".
 */
function barEndLabel(bars, index) {
  return `${formatCurrency(bars.prices[index])} (-${formatCurrency(bars.losses[index])})`;
}

/**
 * Whether a bar is the reader's bond.
 * @param {{ canvas: HTMLCanvasElement }} chart - Sensitivity chart.
 * @param {number} index - Bar index.
 * @returns {boolean} True for the highlighted bar.
 */
function isCurrentBar(chart, index) {
  return barState(chart).bars.currentIndex === index;
}

/**
 * Draws each bar's label just past its end. The page carries no datalabels
 * plugin, so this one chart gets a small inline plugin instead.
 * @type {import("chart.js").Plugin<"bar">}
 */
const barEndLabels = {
  id: "brBarEndLabels",
  afterDatasetsDraw(chart) {
    const state = barState(chart);
    // Chart.js resolves options.font through Chart.defaults.font, which sets both.
    const { family, size } = /** @type {import("chart.js").FontSpec} */ (chart.options.font);
    const { ctx } = chart;
    ctx.save();
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    chart.getDatasetMeta(0).data.forEach((bar, index) => {
      const current = index === state.bars.currentIndex;
      ctx.font = `${current ? 600 : 400} ${size}px ${family}`;
      ctx.fillStyle = current ? state.palette.heading : state.palette.tick;
      ctx.fillText(barEndLabel(state.bars, index), bar.x + BAR_LABEL_GAP, bar.y);
    });
    ctx.restore();
  }
};

/**
 * A horizontal bar per maturity, as long as the dollars a one-point rate rise
 * costs, with the new price and the loss written at its end. The value axis is
 * hidden because every bar carries its own number.
 * @param {HTMLCanvasElement} canvas - Target canvas element.
 * @returns {ChartInstance} The created chart.
 */
function createSensitivityChart(canvas) {
  barStates.set(canvas, { bars: { labels: [], prices: [], losses: [], currentIndex: -1 }, palette: colors() });
  return new (chartGlobal().Chart)(canvas, {
    type: "bar",
    data: {
      labels: [],
      datasets: [{ label: "Dollars lost", data: [], borderWidth: 1.5, maxBarThickness: 24 }]
    },
    plugins: [barEndLabels],
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { right: BAR_LABEL_ROOM } },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            /** @param {import("chart.js").TooltipItem<"bar">} context - Tooltip item. */
            label(context) {
              const state = barState(context.chart);
              const price = state.bars.prices[context.dataIndex];
              const loss = state.bars.losses[context.dataIndex];
              return `Worth ${formatCurrency(price)}, down ${formatPercent((loss / (price + loss)) * 100)}`;
            }
          }
        }
      },
      scales: {
        x: { display: false, beginAtZero: true },
        y: {
          border: { display: false },
          grid: { display: false },
          ticks: {
            /** @param {import("chart.js").ScriptableScaleContext} context - Tick context. */
            color(context) {
              const { palette } = barState(context.chart);
              return isCurrentBar(context.chart, context.index) ? palette.heading : palette.tick;
            },
            /** @param {import("chart.js").ScriptableScaleContext} context - Tick context. */
            font(context) {
              return { weight: isCurrentBar(context.chart, context.index) ? 600 : 400 };
            }
          }
        }
      }
    }
  });
}

/**
 * @param {ChartInstance} chart - Chart to update.
 * @param {ChartState} state - Current chart state.
 * @param {UpdateMode} mode - Chart.js update mode.
 * @returns {void}
 */
function syncSensitivityChart(chart, state, mode) {
  const { palette, sensitivity } = state;
  barStates.set(chart.canvas, { bars: sensitivity, palette });
  chart.data.labels = sensitivity.labels;
  chart.data.datasets[0].data = sensitivity.losses;
  chart.data.datasets[0].backgroundColor = sensitivity.losses.map((/** @type {number} */ _value, /** @type {number} */ index) =>
    index === sensitivity.currentIndex ? palette.red : palette.redA(0.45)
  );
  chart.data.datasets[0].borderColor = palette.noteRed;
  chart.update(mode);
}

/**
 * @param {Record<string, HTMLElement>} elements - Canvas elements keyed by chart name.
 * @returns {Charts} Chart instances.
 */
function createCharts(elements) {
  const charts = {
    priceRate: createPriceRateChart(/** @type {HTMLCanvasElement} */ (elements.priceRateChart)),
    sensitivity: createSensitivityChart(/** @type {HTMLCanvasElement} */ (elements.sensitivityChart)),
    yieldCurve: createYieldCurveChart(/** @type {HTMLCanvasElement} */ (elements.yieldCurveChart))
  };
  offscreenDraws.set(charts, createOffscreenDraws(CHART_NAMES.map((name) => charts[name].canvas)));
  return charts;
}

/** Chart names in drawing order. */
const CHART_NAMES = /** @type {ChartName[]} */ (["priceRate", "sensitivity", "yieldCurve"]);

/** @type {Record<ChartName, (chart: ChartInstance, state: ChartState, formatDollarTick: (value: number) => string, mode: UpdateMode) => void>} */
const SYNCS = {
  priceRate: syncPriceRateChart,
  sensitivity: (chart, state, _formatDollarTick, mode) => syncSensitivityChart(chart, state, mode),
  yieldCurve: (chart, state, _formatDollarTick, mode) => syncYieldCurveChart(chart, state, mode)
};

/** Each chart set's off-screen gate: a chart off screen keeps its latest redraw until it scrolls in. */
const offscreenDraws = /** @type {WeakMap<Charts, import("../../../../js/modules/offscreen-draws.js").OffscreenDraws>} */ (
  new WeakMap()
);

/** @returns {boolean} Whether the reader asked for reduced motion. */
function prefersReducedMotion() {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * @typedef {{ curve: Array<{ x: number, y: number }>, current: { x: number, y: number } }} MarkedSeries
 * @typedef {{
 *   charts?: Partial<Charts>,
 *   elements: Record<string, HTMLElement>,
 *   priceRate?: MarkedSeries,
 *   sensitivity?: SensitivityBars,
 *   yieldCurve?: MarkedSeries,
 *   formatDollarTick: (value: number) => string,
 *   animate?: Partial<Record<ChartName, boolean>>
 * }} ChartRenderOptions
 */

/**
 * Redraw one chart now when it is on screen, or keep the redraw pending until it is.
 * @param {Charts} charts - Chart instances.
 * @param {ChartName} name - Chart to redraw.
 * @param {(mode: UpdateMode) => void} run - Redraw with the given update mode.
 * @param {boolean} animate - Whether this change is worth the chart's own animation.
 * @returns {void}
 */
function drawOrDefer(charts, name, run, animate) {
  const mode = animate && !prefersReducedMotion() ? undefined : "none";
  /** @type {import("../../../../js/modules/offscreen-draws.js").OffscreenDraws} */ (offscreenDraws.get(charts)).draw(
    charts[name].canvas,
    () => {
      // An instant redraw cancels any ease still running, such as the first
      // draw's, which would otherwise finish later and put back the old bars.
      if (mode === "none") {
        charts[name].stop();
      }
      run(mode);
    }
  );
}

/**
 * Create the three explainer charts on the first call, then redraw only the ones
 * given new data. Input-driven redraws skip Chart.js's animation so a slider drag
 * follows the pointer; pass `animate` for a change that should ease (the first
 * draw and a curve switch). A chart that is off screen redraws once it scrolls in.
 * @param {ChartRenderOptions} options - Chart data, formatting callbacks, and which charts to redraw.
 * @returns {Charts} Chart instances keyed by name.
 */
export function renderCharts({
  charts = {},
  elements,
  priceRate,
  sensitivity,
  yieldCurve,
  formatDollarTick,
  animate = {}
}) {
  const created = !charts.priceRate;
  const nextCharts = created ? createCharts(elements) : /** @type {Charts} */ (charts);
  const palette = colors();

  const updates = { priceRate, sensitivity, yieldCurve };

  for (const name of CHART_NAMES) {
    if (!updates[name]) {
      continue;
    }
    const state = /** @type {ChartState} */ ({ palette, [name]: updates[name] });
    drawOrDefer(
      nextCharts,
      name,
      (mode) => SYNCS[name](nextCharts[name], state, formatDollarTick, mode),
      created || Boolean(animate[name])
    );
  }
  return nextCharts;
}
