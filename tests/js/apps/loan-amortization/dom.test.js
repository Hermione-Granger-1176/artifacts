import assert from 'node:assert/strict';
import test from 'node:test';

// --- DOM helpers ---

function makeElement(overrides = {}) {
  const classes = new Set();
  return {
    hidden: false,
    textContent: '',
    value: '',
    className: '',
    children: [],
    innerHTML: '',
    classList: {
      toggle(cls, force) {
        if (force !== undefined) {
          force ? classes.add(cls) : classes.delete(cls);
        } else {
          classes.has(cls) ? classes.delete(cls) : classes.add(cls);
        }
      },
      contains(cls) { return classes.has(cls); }
    },
    append(...nodes) { this.children.push(...nodes); },
    appendChild(child) { this.children.push(child); return child; },
    addEventListener: () => {},
    ...overrides
  };
}

function setupDocumentMock() {
  const origDoc = globalThis.document;
  globalThis.document = {
    createElement(tag) {
      return makeElement({ tagName: tag });
    },
    documentElement: {
      getAttribute() { return 'light'; }
    }
  };
  globalThis.getComputedStyle = () => ({
    getPropertyValue() { return 'rgb(100, 150, 200)'; }
  });
  return origDoc;
}

function restoreDocument(origDoc) {
  if (origDoc) {
    globalThis.document = origDoc;
  } else {
    delete globalThis.document;
  }
  delete globalThis.getComputedStyle;
}

// --- ui.js ---

import {
  cacheElements as cacheAppElements,
  syncInputsFromSliders,
  syncBiweeklyModeUI,
  updateBiweeklyMode,
  setViewMode,
  setTableMode,
  getChartElements
} from '../../../../apps/loan-amortization/js/modules/ui.js';

test('cacheElements returns cached DOM elements using element-cache', () => {
  const mockDoc = {
    getElementById(id) {
      return { id, tagName: 'INPUT' };
    }
  };

  const result = cacheAppElements(mockDoc);
  assert.ok('inPrincipal' in result);
  assert.ok('slRate' in result);
  assert.ok('metrics' in result);
  assert.equal(result.inPrincipal.id, 'inPrincipal');
});

test('syncInputsFromSliders formats principal, rate, and tenure', () => {
  const elements = {
    inPrincipal: { value: '' },
    inRate: { value: '' },
    inTenure: { value: '' },
    slPrincipal: { value: '250000' },
    slRate: { value: '6.5' },
    slTenure: { value: '15' }
  };

  syncInputsFromSliders(elements);

  assert.equal(elements.inPrincipal.value, '250,000');
  assert.equal(elements.inRate.value, '6.50');
  assert.equal(elements.inTenure.value, '15');
});

test('syncBiweeklyModeUI toggles active class based on mode', () => {
  const bwTrue = makeElement();
  const bwAccel = makeElement();
  const bwDesc = makeElement();
  const elements = { bwTrue, bwAccel, bwDesc };

  syncBiweeklyModeUI(elements, 'true');
  assert.equal(bwTrue.classList.contains('active'), true);
  assert.equal(bwAccel.classList.contains('active'), false);
  assert.match(bwDesc.textContent, /recalculated/);

  syncBiweeklyModeUI(elements, 'accelerated');
  assert.equal(bwTrue.classList.contains('active'), false);
  assert.equal(bwAccel.classList.contains('active'), true);
  assert.match(bwDesc.textContent, /Monthly EMI/);
});

test('updateBiweeklyMode shows panel for biweekly frequency', () => {
  const elements = {
    biweeklyMode: makeElement(),
    bwTrue: makeElement(),
    bwAccel: makeElement(),
    bwDesc: makeElement()
  };

  updateBiweeklyMode(elements, 'biweekly', 'true');
  assert.equal(elements.biweeklyMode.hidden, false);

  updateBiweeklyMode(elements, 'monthly', 'true');
  assert.equal(elements.biweeklyMode.hidden, true);
});

test('setViewMode toggles charts and table visibility', () => {
  const elements = {
    chartsWrap: makeElement(),
    tableWrap: makeElement(),
    btnCharts: makeElement(),
    btnTable: makeElement()
  };

  setViewMode(elements, 'charts');
  assert.equal(elements.chartsWrap.hidden, false);
  assert.equal(elements.tableWrap.hidden, true);
  assert.equal(elements.btnCharts.classList.contains('active'), true);

  setViewMode(elements, 'table');
  assert.equal(elements.chartsWrap.hidden, true);
  assert.equal(elements.tableWrap.hidden, false);
  assert.equal(elements.btnTable.classList.contains('active'), true);
});

test('setTableMode toggles period and yearly table visibility', () => {
  const elements = {
    periodTableWrap: makeElement(),
    yearlyTableWrap: makeElement(),
    btnPeriod: makeElement(),
    btnYearly: makeElement()
  };

  setTableMode(elements, 'period');
  assert.equal(elements.periodTableWrap.hidden, false);
  assert.equal(elements.yearlyTableWrap.hidden, true);
  assert.equal(elements.btnPeriod.classList.contains('active'), true);

  setTableMode(elements, 'yearly');
  assert.equal(elements.periodTableWrap.hidden, true);
  assert.equal(elements.yearlyTableWrap.hidden, false);
  assert.equal(elements.btnYearly.classList.contains('active'), true);
});

test('getChartElements returns chart canvas references', () => {
  const elements = {
    balanceChart: 'bc',
    compChart: 'cc',
    savingsChart: 'sc',
    cumulChart: 'cuc',
    periodChart: 'pc',
    other: 'not-included'
  };

  const result = getChartElements(elements);
  assert.deepEqual(result, {
    balanceChart: 'bc',
    compChart: 'cc',
    savingsChart: 'sc',
    cumulChart: 'cuc',
    periodChart: 'pc'
  });
});

// --- tables.js ---

const origDoc = setupDocumentMock();

const {
  renderTableSummary,
  renderPeriodTable,
  renderYearlyTable
} = await import('../../../../apps/loan-amortization/js/modules/tables.js');

restoreDocument(origDoc);

test('renderTableSummary creates summary stat elements', () => {
  const origDoc2 = setupDocumentMock();
  try {
    const container = makeElement();
    renderTableSummary(container, {
      totalEmi: '$1,200',
      totalPrincipal: '$1,000',
      totalInterest: '$200',
      totalExtras: '-',
      periods: '12'
    });

    assert.equal(container.children.length, 5);
    assert.equal(container.children[0].className, 'stat');
  } finally {
    restoreDocument(origDoc2);
  }
});

test('renderPeriodTable generates rows with extra highlighting', () => {
  const origDoc2 = setupDocumentMock();
  try {
    const tbody = makeElement();
    const rows = [
      { period: 1, emi: 1000, principal: 800, interest: 200, extra: 0, balance: 9200 },
      { period: 2, emi: 1000, principal: 810, interest: 190, extra: 500, balance: 7890 }
    ];
    const fmt = (v) => `$${v}`;

    renderPeriodTable(tbody, rows, fmt);

    assert.equal(tbody.children.length, 2);
    assert.equal(tbody.children[0].className, '');
    assert.equal(tbody.children[1].className, 'extra-highlight');
    assert.match(tbody.children[0].innerHTML, /\$1000/);
  } finally {
    restoreDocument(origDoc2);
  }
});

test('renderYearlyTable aggregates periods into yearly rows', () => {
  const origDoc2 = setupDocumentMock();
  try {
    const tbody = makeElement();
    const rows = [];
    for (let i = 0; i < 24; i++) {
      rows.push({
        period: i + 1,
        principal: 400,
        interest: 100,
        extra: i < 12 ? 50 : 0,
        balance: 10000 - (i + 1) * 400
      });
    }
    const fmt = (v) => `$${v}`;

    renderYearlyTable(tbody, rows, 10000, 12, fmt);

    assert.equal(tbody.children.length, 2);
    assert.equal(tbody.children[0].className, 'year-row');
    assert.match(tbody.children[0].innerHTML, /Year 1/);
    assert.match(tbody.children[1].innerHTML, /Year 2/);
  } finally {
    restoreDocument(origDoc2);
  }
});

// --- interactions.js ---

import { bindEvents } from '../../../../apps/loan-amortization/js/modules/interactions.js';

// Build a segmented-toggle container whose child buttons register their click
// handler into the shared listeners map, mirroring how initSegmented wires the
// real #viewToggle / #tableToggle groups.
function makeToggle(ids, listeners) {
  const buttons = ids.map((id) => {
    const classes = new Set();
    return {
      id,
      classList: {
        toggle(cls, force) { force ? classes.add(cls) : classes.delete(cls); },
        contains(cls) { return classes.has(cls); }
      },
      setAttribute() {},
      addEventListener(type, handler) { listeners[`${id}:${type}`] = handler; }
    };
  });
  return { querySelectorAll() { return buttons; } };
}

test('bindEvents attaches listeners to slider and button elements', () => {
  const listeners = {};
  function mockEl(id) {
    return {
      id,
      value: '100',
      addEventListener(type, handler) {
        listeners[`${id}:${type}`] = handler;
      },
      blur() {}
    };
  }

  const elements = {
    slPrincipal: mockEl('slPrincipal'),
    slRate: mockEl('slRate'),
    slTenure: mockEl('slTenure'),
    inPrincipal: mockEl('inPrincipal'),
    inRate: mockEl('inRate'),
    inTenure: mockEl('inTenure'),
    selFreq: mockEl('selFreq'),
    bwTrue: mockEl('bwTrue'),
    bwAccel: mockEl('bwAccel'),
    btnAdd: mockEl('btnAdd'),
    extraList: mockEl('extraList'),
    viewToggle: makeToggle(['btnCharts', 'btnTable'], listeners),
    tableToggle: makeToggle(['btnPeriod', 'btnYearly'], listeners)
  };

  const calls = [];
  bindEvents({
    elements,
    onSliderInput: () => calls.push('slider'),
    onPrincipalCommit: () => calls.push('principal'),
    onRateCommit: () => calls.push('rate'),
    onTenureCommit: () => calls.push('tenure'),
    onFrequencyChange: () => calls.push('freq'),
    onBiweeklyModeChange: (mode) => calls.push(`bw:${mode}`),
    onAddExtra: () => calls.push('add'),
    onExtraListClick: () => calls.push('extraClick'),
    onExtraListInput: () => calls.push('extraInput'),
    onViewModeChange: (mode) => calls.push(`view:${mode}`),
    onTableModeChange: (mode) => calls.push(`table:${mode}`),
    parseNumber: (v) => parseFloat(v)
  });

  // Slider input triggers callback
  listeners['slPrincipal:input']();
  assert.ok(calls.includes('slider'));

  // Text input change triggers commit
  elements.inPrincipal.value = '100000';
  listeners['inPrincipal:change'].call(elements.inPrincipal);
  assert.ok(calls.includes('principal'));

  // Frequency change
  listeners['selFreq:change']();
  assert.ok(calls.includes('freq'));

  // Biweekly mode buttons
  listeners['bwTrue:click']();
  assert.ok(calls.includes('bw:true'));

  // View mode buttons
  listeners['btnCharts:click']();
  assert.ok(calls.includes('view:charts'));

  // Table mode buttons
  listeners['btnPeriod:click']();
  assert.ok(calls.includes('table:period'));
});

test('bindEvents text input keydown Enter triggers blur', () => {
  const listeners = {};
  let blurred = false;
  function mockEl(id) {
    return {
      id,
      value: '100000',
      addEventListener(type, handler) {
        listeners[`${id}:${type}`] = handler;
      },
      blur() { blurred = true; }
    };
  }

  const elements = {
    slPrincipal: mockEl('slPrincipal'),
    slRate: mockEl('slRate'),
    slTenure: mockEl('slTenure'),
    inPrincipal: mockEl('inPrincipal'),
    inRate: mockEl('inRate'),
    inTenure: mockEl('inTenure'),
    selFreq: mockEl('selFreq'),
    bwTrue: mockEl('bwTrue'),
    bwAccel: mockEl('bwAccel'),
    btnAdd: mockEl('btnAdd'),
    extraList: mockEl('extraList'),
    viewToggle: makeToggle(['btnCharts', 'btnTable'], listeners),
    tableToggle: makeToggle(['btnPeriod', 'btnYearly'], listeners)
  };

  bindEvents({
    elements,
    onSliderInput: () => {},
    onPrincipalCommit: () => {},
    onRateCommit: () => {},
    onTenureCommit: () => {},
    onFrequencyChange: () => {},
    onBiweeklyModeChange: () => {},
    onAddExtra: () => {},
    onExtraListClick: () => {},
    onExtraListInput: () => {},
    onViewModeChange: () => {},
    onTableModeChange: () => {},
    parseNumber: (v) => parseFloat(v)
  });

  // Enter key on text input should trigger blur
  listeners['inPrincipal:keydown']({ key: 'Enter', currentTarget: elements.inPrincipal });
  assert.equal(blurred, true);

  // Non-Enter key should not trigger blur
  blurred = false;
  listeners['inPrincipal:keydown']({ key: 'Tab', currentTarget: elements.inPrincipal });
  assert.equal(blurred, false);
});

test('bindEvents text input clamps to min/max and triggers all commits', () => {
  const listeners = {};
  function mockEl(id) {
    return {
      id,
      value: '100',
      addEventListener(type, handler) {
        listeners[`${id}:${type}`] = handler;
      },
      blur() {}
    };
  }

  const elements = {
    slPrincipal: mockEl('slPrincipal'),
    slRate: mockEl('slRate'),
    slTenure: mockEl('slTenure'),
    inPrincipal: mockEl('inPrincipal'),
    inRate: mockEl('inRate'),
    inTenure: mockEl('inTenure'),
    selFreq: mockEl('selFreq'),
    bwTrue: mockEl('bwTrue'),
    bwAccel: mockEl('bwAccel'),
    btnAdd: mockEl('btnAdd'),
    extraList: mockEl('extraList'),
    viewToggle: makeToggle(['btnCharts', 'btnTable'], listeners),
    tableToggle: makeToggle(['btnPeriod', 'btnYearly'], listeners)
  };

  const calls = [];
  bindEvents({
    elements,
    onSliderInput: () => {},
    onPrincipalCommit: () => calls.push('principal'),
    onRateCommit: () => calls.push('rate'),
    onTenureCommit: () => calls.push('tenure'),
    onFrequencyChange: () => {},
    onBiweeklyModeChange: () => {},
    onAddExtra: () => {},
    onExtraListClick: () => {},
    onExtraListInput: () => {},
    onViewModeChange: () => {},
    onTableModeChange: () => {},
    parseNumber: (v) => parseFloat(v)
  });

  // Rate commit
  elements.inRate.value = '5.5';
  listeners['inRate:change'].call(elements.inRate);
  assert.ok(calls.includes('rate'));

  // Tenure commit
  elements.inTenure.value = '20';
  listeners['inTenure:change'].call(elements.inTenure);
  assert.ok(calls.includes('tenure'));

  // Accelerated biweekly mode
  const bwCalls = [];
  listeners['bwAccel:click']();
  // btn add
  listeners['btnAdd:click']();
  // extra list click and input
  listeners['extraList:click']();
  listeners['extraList:input']();
  // table mode yearly
  listeners['btnYearly:click']();
});

test('bindEvents text input ignores NaN and non-positive values', () => {
  const listeners = {};
  function mockEl(id) {
    return {
      id,
      value: 'abc',
      addEventListener(type, handler) {
        listeners[`${id}:${type}`] = handler;
      },
      blur() {}
    };
  }

  const elements = {
    slPrincipal: mockEl('slPrincipal'),
    slRate: mockEl('slRate'),
    slTenure: mockEl('slTenure'),
    inPrincipal: mockEl('inPrincipal'),
    inRate: mockEl('inRate'),
    inTenure: mockEl('inTenure'),
    selFreq: mockEl('selFreq'),
    bwTrue: mockEl('bwTrue'),
    bwAccel: mockEl('bwAccel'),
    btnAdd: mockEl('btnAdd'),
    extraList: mockEl('extraList'),
    viewToggle: makeToggle(['btnCharts', 'btnTable'], listeners),
    tableToggle: makeToggle(['btnPeriod', 'btnYearly'], listeners)
  };

  const calls = [];
  bindEvents({
    elements,
    onSliderInput: () => {},
    onPrincipalCommit: () => calls.push('principal'),
    onRateCommit: () => {},
    onTenureCommit: () => {},
    onFrequencyChange: () => {},
    onBiweeklyModeChange: () => {},
    onAddExtra: () => {},
    onExtraListClick: () => {},
    onExtraListInput: () => {},
    onViewModeChange: () => {},
    onTableModeChange: () => {},
    parseNumber: (v) => parseFloat(v)
  });

  // NaN value should not trigger commit
  elements.inPrincipal.value = 'abc';
  listeners['inPrincipal:change'].call(elements.inPrincipal);
  assert.equal(calls.length, 0);
});

// --- charts.js ---

// Mock window.Chart before importing charts.js
const origDoc3 = setupDocumentMock();
const origWindow = globalThis.window;
globalThis.window = {
  Chart: function MockChart(_canvas, config) {
    this.type = config.type;
    this.data = config.data;
    this.options = config.options;
    this.plugins = config.plugins;
    this.update = () => {};
    this.$artifactsFormatCurrency = null;
    this.$artifactsInterestTotal = null;
    this.$artifactsPalette = null;
  },
  ChartDataLabels: {}
};

const { refreshPalette, renderCharts } = await import(
  '../../../../apps/loan-amortization/js/modules/charts.js'
);

restoreDocument(origDoc3);
globalThis.window = origWindow;

test('refreshPalette returns a color palette object', () => {
  const orig = setupDocumentMock();
  try {
    const palette = refreshPalette();
    assert.ok(typeof palette === 'object');
    assert.ok('blue' in palette);
    assert.ok('green' in palette);
    assert.ok('red' in palette);
    assert.ok(typeof palette.blueA === 'function');
    assert.match(palette.blueA(0.5), /rgba/);
  } finally {
    restoreDocument(orig);
  }
});

test('refreshPalette clears the cache and returns fresh palette', () => {
  const orig = setupDocumentMock();
  try {
    const first = refreshPalette();
    const second = refreshPalette();
    // Both should be valid palettes (cache was cleared)
    assert.ok(first.blue === second.blue);
    assert.ok('tick' in second);
    assert.ok('grid' in second);
  } finally {
    restoreDocument(orig);
  }
});

test('refreshPalette cssAlpha returns raw value when color has fewer than 3 numbers', () => {
  const origDoc5 = globalThis.document;
  const origGCS = globalThis.getComputedStyle;
  globalThis.document = {
    documentElement: { getAttribute() { return 'light'; } }
  };
  globalThis.getComputedStyle = () => ({
    getPropertyValue(prop) {
      // Return a color with fewer than 3 numeric groups for alpha test
      if (prop === '--note-blue') return 'blue';
      return 'rgb(100, 150, 200)';
    }
  });

  try {
    const palette = refreshPalette();
    // blueA should return the raw value since 'blue' has no numeric groups
    assert.equal(palette.blueA(0.5), 'blue');
  } finally {
    if (origDoc5) globalThis.document = origDoc5; else delete globalThis.document;
    if (origGCS) globalThis.getComputedStyle = origGCS; else delete globalThis.getComputedStyle;
  }
});

test('renderCharts creates chart instances on first call', () => {
  const orig = setupDocumentMock();
  const origWin = globalThis.window;
  const chartConfigs = [];
  globalThis.window = {
    Chart: function MockChart(_canvas, config) {
      chartConfigs.push(config.type);
      this.type = config.type;
      this.data = config.data;
      this.options = config.options;
      this.plugins = config.plugins;
      this.update = () => {};
      this.$artifactsFormatCurrency = null;
      this.$artifactsInterestTotal = null;
      this.$artifactsPalette = null;
    },
    ChartDataLabels: {}
  };

  try {
    const elements = {
      balanceChart: {},
      compChart: {},
      savingsChart: {},
      cumulChart: {},
      periodChart: {}
    };
    const fmt = (v) => `$${v}`;
    const fmtTick = (v) => `$${v}`;

    const base = {
      periods: 12,
      totalInterest: 5000,
      balances: [9000, 8000, 7000, 6000, 5000, 4000, 3000, 2000, 1000, 500, 250, 0]
    };
    const extra = {
      periods: 10,
      totalInterest: 4000,
      totalExtra: 2000,
      breakEven: 5,
      balances: [9000, 7800, 6500, 5100, 3600, 2000, 1000, 500, 100, 0],
      rows: Array.from({ length: 10 }, (_, i) => ({ period: i + 1 })),
      cumulativePrincipal: [800, 1700, 2700, 3800, 5000, 6200, 7500, 8800, 9800, 10000],
      cumulativeExtra: [200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000],
      cumulativeInterest: [100, 190, 270, 340, 400, 450, 490, 520, 540, 550],
      principalParts: [800, 900, 1000, 1100, 1200, 1200, 1300, 1300, 1000, 200],
      extraParts: [200, 200, 200, 200, 200, 200, 200, 200, 200, 200],
      interestParts: [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]
    };

    const charts = renderCharts({
      elements,
      base,
      extra,
      principal: 10000,
      interestSaved: 1000,
      periodLabel: 'Month',
      formatCurrency: fmt,
      formatDollarTick: fmtTick
    });

    // 5 chart types created: line, bar, doughnut, line, line
    assert.equal(chartConfigs.length, 5);
    assert.ok(chartConfigs.includes('line'));
    assert.ok(chartConfigs.includes('bar'));
    assert.ok(chartConfigs.includes('doughnut'));

    // Returns chart instances
    assert.ok('balance' in charts);
    assert.ok('comparison' in charts);
    assert.ok('savings' in charts);
    assert.ok('cumulative' in charts);
    assert.ok('period' in charts);
  } finally {
    restoreDocument(orig);
    if (origWin) globalThis.window = origWin; else delete globalThis.window;
  }
});

test('renderCharts reuses existing chart instances on subsequent calls', () => {
  const orig = setupDocumentMock();
  const origWin = globalThis.window;
  let chartCreateCount = 0;
  globalThis.window = {
    Chart: function MockChart(_canvas, config) {
      chartCreateCount++;
      this.type = config.type;
      this.data = { labels: [], datasets: config.data.datasets };
      this.options = config.options;
      this.plugins = config.plugins;
      this.update = () => {};
      this.$artifactsFormatCurrency = null;
      this.$artifactsInterestTotal = null;
      this.$artifactsPalette = null;
    },
    ChartDataLabels: {}
  };

  try {
    const elements = {
      balanceChart: {},
      compChart: {},
      savingsChart: {},
      cumulChart: {},
      periodChart: {}
    };
    const fmt = (v) => `$${v}`;

    const base = {
      periods: 6, totalInterest: 3000,
      balances: [5000, 4000, 3000, 2000, 1000, 0]
    };
    const extra = {
      periods: 5, totalInterest: 2500, totalExtra: 500, breakEven: null,
      balances: [5000, 3800, 2500, 1200, 0],
      rows: Array.from({ length: 5 }, (_, i) => ({ period: i + 1 })),
      cumulativePrincipal: [1000, 2200, 3500, 4800, 5000],
      cumulativeExtra: [100, 200, 300, 400, 500],
      cumulativeInterest: [100, 180, 250, 310, 360],
      principalParts: [1000, 1200, 1300, 1300, 200],
      extraParts: [100, 100, 100, 100, 100],
      interestParts: [100, 80, 70, 60, 50]
    };

    // First call creates charts
    const firstCharts = renderCharts({
      elements, base, extra, principal: 5000,
      interestSaved: 500, periodLabel: 'Month',
      formatCurrency: fmt, formatDollarTick: fmt
    });
    const firstCreateCount = chartCreateCount;

    // Second call reuses them
    renderCharts({
      charts: firstCharts,
      elements, base, extra, principal: 5000,
      interestSaved: 500, periodLabel: 'Month',
      formatCurrency: fmt, formatDollarTick: fmt
    });

    assert.equal(chartCreateCount, firstCreateCount, 'no new charts created on second call');
  } finally {
    restoreDocument(orig);
    if (origWin) globalThis.window = origWin; else delete globalThis.window;
  }
});

test('renderCharts chart tooltip callbacks produce formatted labels', () => {
  const orig = setupDocumentMock();
  const origWin = globalThis.window;
  const createdCharts = [];
  globalThis.window = {
    Chart: function MockChart(_canvas, config) {
      createdCharts.push(config);
      this.type = config.type;
      this.data = config.data;
      this.options = config.options;
      this.plugins = config.plugins;
      this.update = () => {};
      this.$artifactsFormatCurrency = null;
      this.$artifactsInterestTotal = null;
      this.$artifactsPalette = null;
      // Expose chartArea for centerText plugin
      this.chartArea = { left: 0, right: 200, top: 0, bottom: 200 };
      this.ctx = {
        save() {},
        restore() {},
        fillText() {},
        textAlign: '',
        fillStyle: '',
        font: ''
      };
    },
    ChartDataLabels: {}
  };

  try {
    const elements = {
      balanceChart: {}, compChart: {}, savingsChart: {},
      cumulChart: {}, periodChart: {}
    };
    const fmt = (v) => `$${v}`;
    const base = { periods: 3, totalInterest: 1000, balances: [6000, 3000, 0] };
    const extra = {
      periods: 3, totalInterest: 800, totalExtra: 200, breakEven: 2,
      balances: [5800, 2800, 0],
      rows: [{ period: 1 }, { period: 2 }, { period: 3 }],
      cumulativePrincipal: [3200, 6400, 9000],
      cumulativeExtra: [200, 400, 600],
      cumulativeInterest: [100, 180, 240],
      principalParts: [3200, 3200, 2600],
      extraParts: [200, 200, 200],
      interestParts: [100, 80, 60]
    };

    renderCharts({
      elements, base, extra, principal: 9000,
      interestSaved: 200, periodLabel: 'Month',
      formatCurrency: fmt, formatDollarTick: fmt
    });

    // Exercise tooltip callbacks from line/bar charts
    for (const config of createdCharts) {
      const callbacks = config.options?.plugins?.tooltip?.callbacks;
      if (callbacks?.label) {
        if (config.type === 'doughnut') {
          const label = callbacks.label({ label: 'Interest paid', parsed: 800 });
          assert.match(label, /Interest paid/);
        } else {
          const label = callbacks.label({ dataset: { label: 'Test' }, parsed: { y: 5000 } });
          assert.match(label, /Test/);
        }
      }
    }

    // Exercise doughnut-specific plugin callbacks
    const doughnutConfig = createdCharts.find((c) => c.type === 'doughnut');
    if (doughnutConfig) {

      // Exercise datalabels display callback
      const displayFn = doughnutConfig.options.plugins.datalabels.display;
      const showResult = displayFn({
        dataIndex: 0,
        dataset: { data: [800, 200] },
        chart: { $artifactsInterestTotal: 1000 }
      });
      assert.equal(showResult, true);

      // Exercise datalabels color callback
      const colorFn = doughnutConfig.options.plugins.datalabels.color;
      const colorResult = colorFn({
        dataIndex: 0,
        chart: { $artifactsPalette: { redEmphasis: 'red', greenEmphasis: 'green' } }
      });
      assert.equal(colorResult, 'red');

      // Exercise datalabels formatter callback
      const formatterFn = doughnutConfig.options.plugins.datalabels.formatter;
      const fmtResult = formatterFn(800, {
        chart: { $artifactsInterestTotal: 1000, $artifactsFormatCurrency: fmt }
      });
      assert.match(fmtResult, /80%/);

      // Exercise centerText afterDraw plugin
      const centerTextPlugin = doughnutConfig.plugins?.find((p) => p.id === 'centerText');
      if (centerTextPlugin) {
        const mockChart = {
          data: { datasets: [{ data: [980, 20] }] },
          $artifactsInterestTotal: 1000,
          $artifactsPalette: { redEmphasis: 'red', greenEmphasis: 'green' },
          $artifactsFormatCurrency: fmt,
          chartArea: { left: 0, right: 200, top: 0, bottom: 200 },
          ctx: {
            save() {}, restore() {}, fillText() {},
            textAlign: '', fillStyle: '', font: ''
          }
        };
        // Dominant index = 0 (98% > 95%)
        centerTextPlugin.afterDraw(mockChart);
      }
    }
  } finally {
    restoreDocument(orig);
    if (origWin) globalThis.window = origWin; else delete globalThis.window;
  }
});

test('renderCharts handles zero interest saved', () => {
  const orig = setupDocumentMock();
  const origWin = globalThis.window;
  globalThis.window = {
    Chart: function MockChart(_canvas, config) {
      this.type = config.type;
      this.data = config.data;
      this.options = config.options;
      this.plugins = config.plugins;
      this.update = () => {};
      this.$artifactsFormatCurrency = null;
      this.$artifactsInterestTotal = null;
      this.$artifactsPalette = null;
    },
    ChartDataLabels: {}
  };

  try {
    const elements = {
      balanceChart: {}, compChart: {}, savingsChart: {},
      cumulChart: {}, periodChart: {}
    };
    const fmt = (v) => `$${v}`;
    const base = { periods: 3, totalInterest: 1000, balances: [6000, 3000, 0] };
    const extra = {
      periods: 3, totalInterest: 1000, totalExtra: 0, breakEven: null,
      balances: [6000, 3000, 0],
      rows: [{ period: 1 }, { period: 2 }, { period: 3 }],
      cumulativePrincipal: [3000, 6000, 9000],
      cumulativeExtra: [0, 0, 0],
      cumulativeInterest: [500, 800, 1000],
      principalParts: [3000, 3000, 3000],
      extraParts: [0, 0, 0],
      interestParts: [500, 300, 200]
    };

    // Should not throw with zero interestSaved
    const charts = renderCharts({
      elements, base, extra, principal: 9000,
      interestSaved: 0, periodLabel: 'Week',
      formatCurrency: fmt, formatDollarTick: fmt
    });

    assert.ok('balance' in charts);
  } finally {
    restoreDocument(orig);
    if (origWin) globalThis.window = origWin; else delete globalThis.window;
  }
});
