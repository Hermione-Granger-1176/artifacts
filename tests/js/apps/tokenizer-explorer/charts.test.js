import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildProbabilityChartData,
  refreshPalette,
  renderProbabilityChart
} from '../../../../apps/tokenizer-explorer/js/modules/charts.js';

function chartState(overrides = {}) {
  return {
    inTopP: new Set([0, 1]),
    sampleCounts: null,
    selectedTokenIndex: null,
    sorted: [
      { adjustedProb: 0.7, idx: 0, prob: 0.63, word: 'mat' },
      { adjustedProb: 0.3, idx: 1, prob: 0.27, word: 'floor' },
      { adjustedProb: 0, idx: 2, prob: 0.1, word: 'roof' }
    ],
    ...overrides
  };
}

function setupChartMocks() {
  const originalDocument = globalThis.document;
  const originalWindow = globalThis.window;
  const originalGetComputedStyle = globalThis.getComputedStyle;
  globalThis.document = {
    body: {},
    documentElement: { getAttribute() { return 'light'; } }
  };
  globalThis.getComputedStyle = () => ({
    getPropertyValue() { return 'rgb(100, 150, 200)'; }
  });
  globalThis.window = {
    Chart: function MockChart(_canvas, config) {
      this.data = config.data;
      this.options = config.options;
      this.type = config.type;
      this.updateCalls = 0;
      this.update = () => { this.updateCalls += 1; };
    }
  };
  return { originalDocument, originalWindow, originalGetComputedStyle };
}

function restoreChartMocks({ originalDocument, originalWindow, originalGetComputedStyle }) {
  if (originalDocument) globalThis.document = originalDocument; else delete globalThis.document;
  if (originalWindow) globalThis.window = originalWindow; else delete globalThis.window;
  if (originalGetComputedStyle) globalThis.getComputedStyle = originalGetComputedStyle;
  else delete globalThis.getComputedStyle;
}

test('buildProbabilityChartData keeps temperature-shaped bars and labels exclusions', () => {
  const data = buildProbabilityChartData(chartState({ sampleCounts: new Map([[0, 6], [1, 3], [2, 1]]) }));
  assert.deepEqual(data.labels, ['mat', 'floor', 'roof (off)']);
  assert.deepEqual(data.shapedPercentages, [63, 27, 10]);
  assert.deepEqual(data.adjustedPercentages, [70, 30, 0]);
  assert.deepEqual(data.empiricalCounts, [6, 3, 1]);
  assert.deepEqual(data.empiricalPercentages, [60, 30, 10]);
});

test('renderProbabilityChart creates once and then updates the same chart instance', () => {
  const mocks = setupChartMocks();
  try {
    const chart = renderProbabilityChart(null, {}, chartState({ selectedTokenIndex: 1 }));
    assert.equal(chart.type, 'bar');
    assert.equal(chart.options.indexAxis, 'y');
    assert.equal(chart.options.scales.x.max, 100);
    assert.equal(chart.data.labels[2], 'roof (off)');
    assert.equal(chart.data.datasets[0].data[1], 27);
    assert.equal(chart.data.datasets[0].data[2], 10);
    assert.equal(chart.data.datasets[1].hidden, true);
    assert.equal(chart.updateCalls, 1);

    const next = renderProbabilityChart(
      chart,
      {},
      chartState({ sampleCounts: new Map([[0, 71], [1, 29], [2, 0]]) })
    );
    assert.equal(next, chart);
    assert.equal(chart.data.datasets[1].hidden, false);
    assert.equal(chart.data.datasets[1].data[0], 71);
    assert.equal(chart.options.plugins.legend.display, true);
    assert.equal(chart.updateCalls, 2);

    const disabledTooltip = chart.options.plugins.tooltip.callbacks.label({
      dataIndex: 2,
      dataset: chart.data.datasets[0],
      datasetIndex: 0,
      parsed: { x: 10 }
    });
    const survivorTooltip = chart.options.plugins.tooltip.callbacks.label({
      dataIndex: 0,
      dataset: chart.data.datasets[0],
      datasetIndex: 0,
      parsed: { x: 63 }
    });
    const observedTooltip = chart.options.plugins.tooltip.callbacks.label({
      dataIndex: 0,
      dataset: chart.data.datasets[1],
      datasetIndex: 1,
      parsed: { x: 71 }
    });
    assert.match(disabledTooltip, /disabled by Top P/);
    assert.match(survivorTooltip, /renormalized to 70.00% in the pool/);
    assert.match(observedTooltip, /71 of 100 draws/);
    refreshPalette();
  } finally {
    restoreChartMocks(mocks);
  }
});
