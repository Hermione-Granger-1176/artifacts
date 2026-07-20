import { chartGlobal, createPaletteCache, cssAlpha, cssValue } from "../../../../js/modules/chart-theme.js";
import { formatPercent } from "../../../../js/modules/formatting.js";

/**
 * @typedef {import("chart.js").Chart} ChartInstance
 * @typedef {ReturnType<typeof colors>} Palette
 * @typedef {{
 *   inTopP: Set<number>,
 *   sampleCounts: Map<number, number> | null,
 *   selectedTokenIndex: number | null,
 *   sorted: Array<{ adjustedProb: number, idx: number, prob: number, word: string }>
 * }} ProbState
 * @typedef {import("chart.js").ChartDataset & {
 *   cutIndexes?: boolean[],
 *   adjustedPercentages?: number[],
 *   sampleCounts?: number[]
 * }} ProbDataset
 * @typedef {{
 *   plugins: { legend: { display: boolean, labels: { color: string } } },
 *   scales: { x: Record<string, unknown>, y: Record<string, unknown> },
 *   animation: object
 * }} MutableChartOptions
 */

const { colors, refreshPalette } = createPaletteCache(() => ({
  amber: cssValue("--color-amber"),
  blue: cssValue("--color-blue"),
  blueSoft: cssAlpha("--color-blue", 0.72),
  green: cssValue("--color-green"),
  grid: cssValue("--chart-grid"),
  muted: cssAlpha("--color-text-tertiary", 0.38),
  mutedBorder: cssAlpha("--color-text-tertiary", 0.68),
  surface: cssValue("--color-surface"),
  tick: cssValue("--chart-tick")
}));

export { refreshPalette };

/**
 * Derive the label and data arrays used by the horizontal probability chart.
 * The bars always show the temperature-shaped distribution: top-p never
 * changes a bar's length, it only disables excluded tokens, so the two
 * controls stay visually distinct. Renormalized pool values ride along for
 * tooltips and for comparison against the observed tally.
 *
 * @param {{
 *   inTopP: Set<number>,
 *   sampleCounts: Map<number, number> | null,
 *   sorted: Array<{ adjustedProb: number, idx: number, prob: number, word: string }>
 * }} state
 * @returns {{
 *   adjustedPercentages: number[],
 *   empiricalCounts: number[] | null,
 *   empiricalPercentages: number[] | null,
 *   labels: string[],
 *   shapedPercentages: number[]
 * }}
 */
export function buildProbabilityChartData(state) {
  const empiricalCounts = state.sampleCounts
    ? state.sorted.map((token) => state.sampleCounts?.get(token.idx) ?? 0)
    : null;
  const drawTotal = empiricalCounts?.reduce((sum, count) => sum + count, 0) ?? 0;

  return {
    adjustedPercentages: state.sorted.map((token) => token.adjustedProb * 100),
    empiricalCounts,
    empiricalPercentages:
      empiricalCounts?.map((count) => (drawTotal > 0 ? (count / drawTotal) * 100 : 0)) ?? null,
    labels: state.sorted.map((token) =>
      state.inTopP.has(token.idx) ? token.word : `${token.word} (off)`
    ),
    shapedPercentages: state.sorted.map((token) => token.prob * 100)
  };
}

/**
 * @param {HTMLCanvasElement} canvas - Target canvas element.
 * @returns {ChartInstance} The created chart.
 */
function createProbabilityChart(canvas) {
  return new (chartGlobal().Chart)(canvas, {
    type: "bar",
    data: {
      labels: [],
      datasets: [
        { label: "After temperature", data: [], borderWidth: 1.25 },
        { label: "Observed in 100 draws", data: [], borderWidth: 1.25, hidden: true }
      ]
    },
    options: {
      animation: { duration: 280, easing: "easeOutQuart" },
      indexAxis: "y",
      maintainAspectRatio: false,
      responsive: true,
      plugins: {
        legend: { display: false, labels: { color: "" } },
        tooltip: {
          callbacks: {
            /** @param {import("chart.js").TooltipItem<"bar">} context - Tooltip item. */
            label(context) {
              const dataset = /** @type {ProbDataset} */ (context.dataset);
              const percentage = formatPercent(Number(context.parsed.x ?? 0), 2);
              if (context.datasetIndex === 1) {
                const count = dataset.sampleCounts?.[context.dataIndex] ?? 0;
                return `${dataset.label}: ${percentage} (${count} of 100 draws)`;
              }

              if (dataset.cutIndexes?.[context.dataIndex]) {
                return `${dataset.label}: ${percentage}, disabled by Top P`;
              }
              const adjusted = dataset.adjustedPercentages?.[context.dataIndex] ?? 0;
              return `${dataset.label}: ${percentage}, renormalized to ${formatPercent(adjusted, 2)} in the pool`;
            }
          }
        }
      },
      scales: {
        x: { beginAtZero: true, max: 100, title: {}, ticks: {}, grid: {} },
        y: { title: {}, ticks: {}, grid: {} }
      }
    }
  });
}

/**
 * @param {ChartInstance} chart - Chart to update.
 * @param {ProbState} state - Current chart state.
 * @returns {void}
 */
function syncProbabilityChart(chart, state) {
  const palette = colors();
  const data = buildProbabilityChartData(state);
  const hasSamples = data.empiricalCounts !== null;
  const theoretical = /** @type {ProbDataset} */ (chart.data.datasets[0]);
  const observed = /** @type {ProbDataset} */ (chart.data.datasets[1]);
  const options = /** @type {MutableChartOptions} */ (/** @type {unknown} */ (chart.options));

  chart.data.labels = data.labels;
  theoretical.data = data.shapedPercentages;
  theoretical.backgroundColor = state.sorted.map((token) => {
    if (!state.inTopP.has(token.idx)) {
      return palette.muted;
    }
    return token.idx === state.selectedTokenIndex ? palette.green : palette.blueSoft;
  });
  theoretical.borderColor = state.sorted.map((token) => {
    if (!state.inTopP.has(token.idx)) {
      return palette.mutedBorder;
    }
    return token.idx === state.selectedTokenIndex ? palette.green : palette.blue;
  });
  theoretical.cutIndexes = state.sorted.map((token) => !state.inTopP.has(token.idx));
  theoretical.adjustedPercentages = data.adjustedPercentages;

  observed.data = data.empiricalPercentages ?? [];
  observed.backgroundColor = palette.amber;
  observed.borderColor = palette.amber;
  observed.hidden = !hasSamples;
  observed.sampleCounts = data.empiricalCounts ?? [];

  options.plugins.legend.display = hasSamples;
  options.plugins.legend.labels.color = palette.tick;
  options.scales.x.title = {
    display: true,
    text: "Probability after temperature (%)",
    color: palette.tick
  };
  options.scales.x.ticks = {
    color: palette.tick,
    /** @param {number | string} value - Tick value. */
    callback(value) {
      return `${value}%`;
    }
  };
  options.scales.x.grid = { color: palette.grid };
  options.scales.y.title = { display: false, text: "", color: palette.tick };
  options.scales.y.ticks = { color: palette.tick };
  options.scales.y.grid = { display: false };
  options.animation = { duration: 280, easing: "easeOutQuart" };
  chart.update();
}

/**
 * Create once, then update the same Chart.js instance as controls change.
 *
 * @param {ChartInstance | null} chart
 * @param {HTMLCanvasElement} canvas
 * @param {{
 *   inTopP: Set<number>,
 *   sampleCounts: Map<number, number> | null,
 *   selectedTokenIndex: number | null,
 *   sorted: Array<{ adjustedProb: number, idx: number, prob: number, word: string }>
 * }} state
 * @returns {ChartInstance}
 */
export function renderProbabilityChart(chart, canvas, state) {
  const nextChart = chart ?? createProbabilityChart(canvas);
  syncProbabilityChart(nextChart, state);
  return nextChart;
}
