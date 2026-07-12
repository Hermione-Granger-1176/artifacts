// Chart.js and its datalabels plugin are loaded as vendor globals on window.
// They ship no local type definitions, so read them through an any-typed view
// of window resolved at call time (never a cached reference) rather than adding
// a runtime dependency.
/** @returns {any} The window object typed loosely for vendor chart globals. */
function chartGlobal() {
  return /** @type {any} */ (window);
}

function css(propertyName) {
  return getComputedStyle(document.body).getPropertyValue(propertyName).trim();
}

function cssAlpha(propertyName, alpha) {
  const raw = css(propertyName);
  const matches = raw.match(/\d+/g);
  if (!matches || matches.length < 3) {
    return raw;
  }
  return `rgba(${matches[0]}, ${matches[1]}, ${matches[2]}, ${alpha})`;
}

function isDark() {
  return document.documentElement.getAttribute("data-theme") === "dark";
}

let cachedPalette = /** @type {any} */ (null);
let cachedTheme = /** @type {string | null} */ (null);

function colors() {
  const theme = isDark() ? "dark" : "light";
  if (cachedPalette && cachedTheme === theme) {
    return cachedPalette;
  }

  cachedTheme = theme;
  cachedPalette = {
    blue: css("--color-blue"),
    green: css("--color-green"),
    red: css("--color-red"),
    noteBlue: css("--note-blue"),
    noteGreen: css("--note-green"),
    noteRed: css("--note-red"),
    blueA(alpha) {
      return cssAlpha("--note-blue", alpha);
    },
    greenA(alpha) {
      return cssAlpha("--note-green", alpha);
    },
    redA(alpha) {
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
  };

  return cachedPalette;
}

/** @returns {object} Fresh chart color palette read from CSS custom properties. */
export function refreshPalette() {
  cachedTheme = null;
  cachedPalette = null;
  return colors();
}

function pad(values, length) {
  if (values.length >= length) {
    return [...values];
  }
  return [...values, ...new Array(length - values.length).fill(0)];
}

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

function applyAxes(scales, palette, periodLabel, formatDollarTick, options = {}) {
  const xScale = scales.x;
  const yScale = scales.y;
  const {
    stackedY = false,
    showXGrid = true,
    xTitle = periodLabel,
    yTitle = null
  } = options;

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

function createBalanceChart(canvas) {
  return new (chartGlobal().Chart)(canvas, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Without extras",
          data: [],
          fill: true,
          pointRadius: 0,
          borderWidth: 2,
          tension: 0.3,
          borderDash: [6, 3]
        },
        {
          label: "With extras",
          data: [],
          fill: true,
          pointRadius: 0,
          borderWidth: 2.5,
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
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
        x: { title: {}, ticks: {}, grid: {} },
        y: { title: {}, ticks: {}, grid: {} }
      }
    }
  });
}

function syncBalanceChart(chart, state, formatDollarTick) {
  const { base, extra, maxPeriods, lineLabels, palette, periodLabel } = state;
  chart.data.labels = lineLabels;
  chart.data.datasets[0].data = pad(base.balances, maxPeriods);
  chart.data.datasets[0].borderColor = palette.blue;
  chart.data.datasets[0].backgroundColor = palette.blueA(0.08);
  chart.data.datasets[1].data = pad(extra.balances, maxPeriods);
  chart.data.datasets[1].borderColor = palette.green;
  chart.data.datasets[1].backgroundColor = palette.greenA(0.08);
  applyAxes(chart.options.scales, palette, periodLabel, formatDollarTick, {
    yTitle: "Balance"
  });
  chart.update();
}

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
    options: {
      responsive: true,
      maintainAspectRatio: false,
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
        x: { ticks: {}, grid: {} },
        y: { ticks: {}, grid: {} }
      }
    }
  });
}

function syncComparisonChart(chart, state, formatDollarTick) {
  const { base, extra, palette, principal } = state;
  chart.data.datasets[0].data = [principal, Math.max(0, Math.round(principal - extra.totalExtra))];
  chart.data.datasets[0].backgroundColor = palette.blue;
  chart.data.datasets[1].data = [Math.round(base.totalInterest), Math.round(extra.totalInterest)];
  chart.data.datasets[1].backgroundColor = palette.noteRed;
  chart.data.datasets[2].data = [0, Math.round(extra.totalExtra)];
  chart.data.datasets[2].backgroundColor = palette.noteGreen;
  applyAxes(chart.options.scales, palette, state.periodLabel, formatDollarTick, {
    showXGrid: false,
    stackedY: true,
    xTitle: "Comparison"
  });
  chart.options.scales.x.stacked = true;
  chart.update();
}

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
            label(context) {
              return `${context.label}: $${context.parsed.toLocaleString()}`;
            }
          }
        },
        datalabels: {
          display(context) {
            const value = context.dataset.data[context.dataIndex];
            const total = context.chart.$artifactsInterestTotal || 1;
            return value > 0 && value / total <= 0.95;
          },
          anchor: "end",
          align: "end",
          offset: 8,
          color(context) {
            const palette = context.chart.$artifactsPalette;
            if (!palette) {
              return "currentColor";
            }
            return context.dataIndex === 0 ? palette.redEmphasis : palette.greenEmphasis;
          },
          font: { weight: "500", size: 12 },
          textAlign: "center",
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
      afterDraw(chart) {
        const dataset = chart.data.datasets[0].data;
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

function syncSavingsChart(chart, state, formatCurrency) {
  const { interestPaid, interestSaved, interestTotal, palette } = state;
  chart.$artifactsFormatCurrency = formatCurrency;
  chart.$artifactsInterestTotal = interestTotal;
  chart.$artifactsPalette = palette;
  chart.data.datasets[0].data = [interestPaid, interestSaved];
  chart.data.datasets[0].backgroundColor = [palette.noteRed, palette.noteGreen];
  chart.data.datasets[0].borderColor = palette.surface;
  chart.update();
}

function createCumulativeChart(canvas) {
  return new (chartGlobal().Chart)(canvas, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Cumulative principal",
          data: [],
          fill: true,
          pointRadius: 0,
          borderWidth: 2,
          tension: 0.3
        },
        {
          label: "Cumulative extras",
          data: [],
          fill: true,
          pointRadius: 0,
          borderWidth: 2,
          tension: 0.3
        },
        {
          label: "Cumulative interest",
          data: [],
          fill: true,
          pointRadius: 0,
          borderWidth: 2,
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        annotation: { annotations: {} },
        tooltip: {
          callbacks: {
            label(context) {
              return `${context.dataset.label}: $${context.parsed.y.toLocaleString()}`;
            }
          }
        }
      },
      scales: {
        x: { title: {}, ticks: {}, grid: {} },
        y: { ticks: {}, grid: {} }
      }
    }
  });
}

function syncCumulativeChart(chart, state, formatDollarTick) {
  const { extra, palette, periodLabel } = state;
  chart.data.labels = extra.rows.map((row) => row.period);
  chart.data.datasets[0].data = extra.cumulativePrincipal;
  chart.data.datasets[0].borderColor = palette.blue;
  chart.data.datasets[0].backgroundColor = palette.blueA(0.1);
  chart.data.datasets[1].data = extra.cumulativeExtra;
  chart.data.datasets[1].borderColor = palette.green;
  chart.data.datasets[1].backgroundColor = palette.greenA(0.1);
  chart.data.datasets[2].data = extra.cumulativeInterest;
  chart.data.datasets[2].borderColor = palette.red;
  chart.data.datasets[2].backgroundColor = palette.redA(0.1);
  chart.options.plugins.annotation = state.annotation;
  applyAxes(chart.options.scales, palette, periodLabel, formatDollarTick);
  chart.update();
}

function createPeriodChart(canvas) {
  return new (chartGlobal().Chart)(canvas, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Principal",
          data: [],
          fill: true,
          pointRadius: 0,
          borderWidth: 1.5,
          tension: 0.3,
          order: 3
        },
        {
          label: "Extra payment",
          data: [],
          fill: true,
          pointRadius: 0,
          borderWidth: 1.5,
          tension: 0.3,
          order: 2
        },
        {
          label: "Interest",
          data: [],
          fill: true,
          pointRadius: 0,
          borderWidth: 1.5,
          tension: 0.3,
          order: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
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
        x: { title: {}, ticks: {}, grid: {} },
        y: { ticks: {}, grid: {} }
      }
    }
  });
}

function syncPeriodChart(chart, state, formatDollarTick) {
  const { extra, palette, periodLabel } = state;
  chart.data.labels = extra.rows.map((row) => row.period);
  chart.data.datasets[0].data = extra.principalParts;
  chart.data.datasets[0].borderColor = palette.blue;
  chart.data.datasets[0].backgroundColor = palette.blueA(0.4);
  chart.data.datasets[1].data = extra.extraParts;
  chart.data.datasets[1].borderColor = palette.green;
  chart.data.datasets[1].backgroundColor = palette.greenA(0.4);
  chart.data.datasets[2].data = extra.interestParts;
  chart.data.datasets[2].borderColor = palette.red;
  chart.data.datasets[2].backgroundColor = palette.redA(0.45);
  applyAxes(chart.options.scales, palette, periodLabel, formatDollarTick, {
    stackedY: true
  });
  chart.update();
}

function createCharts(elements) {
  return {
    balance: createBalanceChart(elements.balanceChart),
    comparison: createComparisonChart(elements.compChart),
    savings: createSavingsChart(elements.savingsChart),
    cumulative: createCumulativeChart(elements.cumulChart),
    period: createPeriodChart(elements.periodChart)
  };
}

function syncCharts(charts, state, formatCurrency, formatDollarTick) {
  syncBalanceChart(charts.balance, state, formatDollarTick);
  syncComparisonChart(charts.comparison, state, formatDollarTick);
  syncSavingsChart(charts.savings, state, formatCurrency);
  syncCumulativeChart(charts.cumulative, state, formatDollarTick);
  syncPeriodChart(charts.period, state, formatDollarTick);
}

/**
 * @typedef {{
 *   charts?: Record<string, any>,
 *   elements: Record<string, any>,
 *   base: import('./amortization.js').ScheduleResult,
 *   extra: import('./amortization.js').ScheduleResult,
 *   principal: number,
 *   interestSaved: number,
 *   periodLabel: string,
 *   formatCurrency: (value: number) => string,
 *   formatDollarTick: (value: number) => string
 * }} ChartRenderOptions
 */

/**
 * Create or update all loan amortization chart instances.
 * @param {ChartRenderOptions} options - Chart data and formatting callbacks.
 * @returns {Record<string, any>} Chart instances keyed by name.
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
  formatDollarTick
}) {
  const nextCharts = charts.balance ? charts : createCharts(elements);
  const state = buildChartState({
    base,
    extra,
    principal,
    interestSaved,
    periodLabel
  });

  syncCharts(nextCharts, state, formatCurrency, formatDollarTick);
  return nextCharts;
}
