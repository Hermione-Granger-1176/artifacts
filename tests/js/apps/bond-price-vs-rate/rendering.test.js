import assert from 'node:assert/strict';
import test from 'node:test';

import {
  formatCurrency,
  formatDollarTick,
  formatPercent
} from '../../../../js/modules/formatting.js';
import {
  analystExplainText,
  curveExplainText,
  heroExplainText,
  mathExplainText,
  mechanismExplainText,
  regimePresentation,
  renderAnalytics,
  renderCouponCompare,
  renderMathLegend,
  renderNarrative,
  renderPriceSplit,
  renderScheduleTable,
  rippleExplainText,
  sensitivityExplainText
} from '../../../../apps/bond-price-vs-rate/js/modules/narrative.js';
import { bindEvents } from '../../../../apps/bond-price-vs-rate/js/modules/interactions.js';
import {
  CURVE_BUTTON_IDS,
  cacheElements,
  getChartElements,
  syncSliderLabels
} from '../../../../apps/bond-price-vs-rate/js/modules/ui.js';
import { refreshPalette, renderCharts } from '../../../../apps/bond-price-vs-rate/js/modules/charts.js';

// --- DOM helpers ---

function makeElement(overrides = {}) {
  const classes = new Set();
  const attrs = {};
  return {
    hidden: false,
    textContent: '',
    value: '',
    className: '',
    children: [],
    innerHTML: '',
    style: {},
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
    setAttribute(key, val) { attrs[key] = val; },
    getAttribute(key) { return attrs[key] ?? null; },
    append(...nodes) { this.children.push(...nodes); },
    appendChild(child) { this.children.push(child); return child; },
    addEventListener: () => {},
    ...overrides
  };
}

function setupDocumentMock({ theme = 'light' } = {}) {
  const origDoc = globalThis.document;
  const origGcs = globalThis.getComputedStyle;
  globalThis.document = {
    body: {},
    createElement(tag) {
      return makeElement({ tagName: tag });
    },
    documentElement: {
      getAttribute() { return theme; }
    }
  };
  globalThis.getComputedStyle = () => ({
    getPropertyValue() { return 'rgb(100, 150, 200)'; }
  });
  return { origDoc, origGcs };
}

function restoreDocument({ origDoc, origGcs }) {
  if (origDoc) globalThis.document = origDoc; else delete globalThis.document;
  if (origGcs) globalThis.getComputedStyle = origGcs; else delete globalThis.getComputedStyle;
}

// --- formatting.js ---

test('formatCurrency formats with a dollar sign and the requested decimals', () => {
  assert.equal(formatCurrency(1170.6, 2), '$1,170.60');
  assert.equal(formatCurrency(926.4, 0), '$926');
  assert.equal(formatCurrency(1000, 0), '$1,000');
});

test('formatPercent defaults to one decimal and honors the digits argument', () => {
  assert.equal(formatPercent(5), '5.0%');
  assert.equal(formatPercent(4.2713, 2), '4.27%');
});

test('formatDollarTick is re-exported from the shared module', () => {
  assert.equal(formatDollarTick(50000), '$50k');
  assert.equal(formatDollarTick(-1500), '-$1.5k');
});

// --- narrative.js ---

const FORMATTERS = { formatCurrency, formatPercent };

// Discounted cash-flow schedule matching the narrative fixture (annual coupons).
function buildSchedule(couponRatePct, years, annualYieldPct, faceValue = 1000) {
  const coupon = (faceValue * couponRatePct) / 100;
  const rows = [];
  for (let period = 1; period <= years; period += 1) {
    const amount = coupon + (period === years ? faceValue : 0);
    const discountFactor = 1 / (1 + annualYieldPct / 100) ** period;
    rows.push({ period, timeYears: period, amount, discountFactor, presentValue: amount * discountFactor });
  }
  return rows;
}

function narrativeState(overrides = {}) {
  return {
    bond: { faceValue: 1000, couponRatePct: 5, years: 10, annualYieldPct: 6 },
    price: 926.4,
    regime: 'discount',
    schedule: buildSchedule(5, 10, 6),
    sensitivity: { currentPct: -7.36, shortPct: -1.83, longPct: -13.76 },
    analytics: {
      price: 926.4,
      pvCoupons: 368,
      pvFace: 558.39,
      currentYieldPct: 5.3972,
      macaulayYears: 8.0225,
      modifiedYears: 7.5684,
      convexity: 72.5693,
      dv01: 0.7011
    },
    curve: { key: 'normal', label: 'Normal', atMaturityPct: 4.7837 },
    ...overrides
  };
}

test('regimePresentation maps each regime to a badge and arrow directions', () => {
  assert.deepEqual(regimePresentation('discount'), {
    label: 'Discount', badgeClass: 'is-red', rateArrow: 'is-up', priceArrow: 'is-down'
  });
  assert.deepEqual(regimePresentation('premium'), {
    label: 'Premium', badgeClass: 'is-green', rateArrow: 'is-down', priceArrow: 'is-up'
  });
  assert.deepEqual(regimePresentation('par'), {
    label: 'At par', badgeClass: 'is-blue', rateArrow: 'is-flat', priceArrow: 'is-flat'
  });
});

test('heroExplainText adapts to each regime', () => {
  assert.match(heroExplainText(narrativeState(), FORMATTERS), /discount to its \$1,000 face value/);
  assert.match(
    heroExplainText(narrativeState({ regime: 'premium', price: 1081.11 }), FORMATTERS),
    /premium over the \$1,000 face value/
  );
  assert.match(
    heroExplainText(narrativeState({ regime: 'par', price: 1000 }), FORMATTERS),
    /matches this bond's 5.0% coupon/
  );
});

test('mechanismExplainText adapts to each regime', () => {
  assert.match(mechanismExplainText(narrativeState(), FORMATTERS), /sits below the market/);
  assert.match(mechanismExplainText(narrativeState({ regime: 'premium' }), FORMATTERS), /sits above the market/);
  assert.match(mechanismExplainText(narrativeState({ regime: 'par' }), FORMATTERS), /equals the market/);
});

test('mathExplainText walks discounting from the coupons to the price', () => {
  const text = mathExplainText(narrativeState(), FORMATTERS);
  assert.match(text, /At a 6.0% market rate/);
  assert.match(text, /each of the 10 \$50 coupon payments/);
  assert.match(text, /\$1,000 face repayment in year 10 is worth \$558.39 today/);
  assert.match(text, /gives the \$926.40 price/);
  assert.match(text, /higher rate drags the price down/);
});

test('renderMathLegend writes the live coupon, rate, years, and face values', () => {
  const elements = {
    mathLegendCoupon: makeElement(),
    mathLegendRate: makeElement(),
    mathLegendYears: makeElement(),
    mathLegendFace: makeElement()
  };
  renderMathLegend(elements, narrativeState(), FORMATTERS);
  assert.equal(elements.mathLegendCoupon.textContent, '$50');
  assert.equal(elements.mathLegendRate.textContent, '6.0%');
  assert.equal(elements.mathLegendYears.textContent, '10');
  assert.equal(elements.mathLegendFace.textContent, '$1,000');
});

test('renderScheduleTable renders a row per period plus a total matching the price', () => {
  const orig = setupDocumentMock();
  try {
    const tbody = makeElement();
    renderScheduleTable(tbody, narrativeState(), FORMATTERS);
    // Ten coupon periods plus the total row.
    assert.equal(tbody.children.length, 11);

    const first = tbody.children[0];
    assert.equal(first.children[0].textContent, '1');
    assert.equal(first.children[1].textContent, '$50.00');
    assert.equal(first.children[2].textContent, (1 / 1.06).toFixed(4));

    // The final period merges the face into the payment and flags it.
    const final = tbody.children[9];
    assert.equal(final.children[1].children[0].textContent, '$1,050.00');
    assert.match(final.children[1].children[1].textContent, /\$1,000 face/);

    const total = tbody.children[10];
    assert.equal(total.children[1].textContent, '$926.40');
  } finally {
    restoreDocument(orig);
  }
});

test('sensitivityExplainText reports magnitudes for the current, short, and long bonds', () => {
  const text = sensitivityExplainText(narrativeState(), FORMATTERS);
  assert.match(text, /shave about 7.4% off your 10-year bond/);
  assert.match(text, /roughly 1.8% for a 2-year/);
  assert.match(text, /13.8% for a 30-year/);
});

test('rippleExplainText adapts to each regime', () => {
  assert.match(rippleExplainText(narrativeState()), /loses value/);
  assert.match(rippleExplainText(narrativeState({ regime: 'premium' })), /gain value/);
  assert.match(rippleExplainText(narrativeState({ regime: 'par' })), /hold their value/);
});

test('renderCouponCompare builds a bar row per rate and scales the fill width', () => {
  const orig = setupDocumentMock();
  try {
    const container = makeElement();
    renderCouponCompare(container, narrativeState(), FORMATTERS);
    assert.equal(container.children.length, 2);
    const [couponRow, marketRow] = container.children;
    assert.equal(couponRow.children[2].textContent, '5.0%');
    assert.equal(marketRow.children[2].textContent, '6.0%');
    // Coupon 5 of a 12 max => 41.67% width.
    assert.ok(couponRow.children[1].children[0].style.width.startsWith('41.6'));
  } finally {
    restoreDocument(orig);
  }
});

function narrativeElements() {
  return {
    priceValue: makeElement(),
    priceCaption: makeElement(),
    regimeBadge: makeElement(),
    rateArrow: makeElement(),
    priceArrow: makeElement(),
    heroExplain: makeElement(),
    mechanismExplain: makeElement(),
    mathExplain: makeElement(),
    mathLegendCoupon: makeElement(),
    mathLegendRate: makeElement(),
    mathLegendYears: makeElement(),
    mathLegendFace: makeElement(),
    mathSchedule: makeElement(),
    sensitivityExplain: makeElement(),
    analystExplain: makeElement(),
    rippleExplain: makeElement(),
    couponCompare: makeElement(),
    pvSplit: makeElement(),
    statCurrentYield: makeElement(),
    statMacaulay: makeElement(),
    statModified: makeElement(),
    statConvexity: makeElement(),
    curveExplain: makeElement(),
    btnApplyCurve: makeElement()
  };
}

test('analystExplainText quotes duration, convexity, DV01, and current yield', () => {
  const text = analystExplainText(narrativeState(), FORMATTERS);
  assert.match(text, /one-point rate rise should cost about 7.6%/);
  assert.match(text, /the exact reprice is 7.4%/);
  assert.match(text, /convexity \(72.6\)/);
  assert.match(text, /\$0.70 of price move per basis point/);
  assert.match(text, /5.40% current yield on the 5.0% coupon/);
});

test('renderPriceSplit sizes each bar by its share of the price', () => {
  const orig = setupDocumentMock();
  try {
    const container = makeElement();
    renderPriceSplit(container, narrativeState(), FORMATTERS);
    assert.equal(container.children.length, 2);
    const [couponsRow, faceRow] = container.children;
    assert.equal(couponsRow.children[0].textContent, 'Coupons');
    assert.equal(couponsRow.children[2].textContent, '$368');
    assert.equal(faceRow.children[2].textContent, '$558');
    // Coupons carry 368 of the 926.40 price => 39.7% of the bar.
    assert.ok(couponsRow.children[1].children[0].style.width.startsWith('39.7'));
    assert.ok(faceRow.children[1].children[0].style.width.startsWith('60.2'));
  } finally {
    restoreDocument(orig);
  }
});

test('renderAnalytics fills the four stat tiles', () => {
  const elements = narrativeElements();
  renderAnalytics(elements, narrativeState(), FORMATTERS);
  assert.equal(elements.statCurrentYield.textContent, '5.40%');
  assert.equal(elements.statMacaulay.textContent, '8.0 yrs');
  assert.equal(elements.statModified.textContent, '7.6');
  assert.equal(elements.statConvexity.textContent, '72.6');
});

test('curveExplainText tells each shape story and quotes the rate at maturity', () => {
  const normal = curveExplainText(narrativeState(), FORMATTERS);
  assert.match(normal, /A normal curve slopes up/);
  assert.match(normal, /At your 10-year maturity this normal curve offers about 4.8%/);
  assert.match(normal, /versus the 6.0% market rate set at the top/);

  const flat = curveExplainText(
    narrativeState({ curve: { key: 'flat', label: 'Flat', atMaturityPct: 4.5 } }),
    FORMATTERS
  );
  assert.match(flat, /A flat curve pays nothing extra for waiting/);

  const inverted = curveExplainText(
    narrativeState({ curve: { key: 'inverted', label: 'Inverted', atMaturityPct: 4.07 } }),
    FORMATTERS
  );
  assert.match(inverted, /most famous recession warning/);
});

test('renderNarrative writes the discount readouts and up/down arrows', () => {
  const orig = setupDocumentMock();
  try {
    const elements = narrativeElements();
    renderNarrative(elements, narrativeState(), FORMATTERS);
    assert.equal(elements.priceValue.textContent, '$926.40');
    assert.equal(elements.priceCaption.textContent, 'This 10-year, 5% bond is now worth');
    assert.equal(elements.regimeBadge.textContent, 'Discount');
    assert.equal(elements.regimeBadge.className, 'chip is-red');
    assert.equal(elements.rateArrow.textContent, '▲');
    assert.equal(elements.rateArrow.className, 'br-arrow is-up');
    assert.equal(elements.priceArrow.textContent, '▼');
    assert.equal(elements.couponCompare.children.length, 2);
    assert.equal(elements.pvSplit.children.length, 2);
    assert.equal(elements.mathLegendCoupon.textContent, '$50');
    assert.equal(elements.mathSchedule.children.length, 11);
    assert.match(elements.mathExplain.textContent, /market rate/);
    assert.equal(elements.statModified.textContent, '7.6');
    assert.match(elements.analystExplain.textContent, /Modified duration/);
    assert.match(elements.curveExplain.textContent, /normal curve/);
    assert.equal(elements.btnApplyCurve.textContent, 'Set the market rate to 4.8%');
  } finally {
    restoreDocument(orig);
  }
});

test('renderNarrative renders a premium bond with a fractional coupon caption', () => {
  const orig = setupDocumentMock();
  try {
    const elements = narrativeElements();
    renderNarrative(
      elements,
      narrativeState({ regime: 'premium', price: 1081.11, bond: { faceValue: 1000, couponRatePct: 5.5, years: 1, annualYieldPct: 4 } }),
      FORMATTERS
    );
    assert.equal(elements.priceValue.textContent, '$1,081.11');
    assert.equal(elements.priceCaption.textContent, 'This 1-year, 5.5% bond is now worth');
    assert.equal(elements.regimeBadge.className, 'chip is-green');
    assert.equal(elements.priceArrow.textContent, '▲');
  } finally {
    restoreDocument(orig);
  }
});

test('renderNarrative renders a par bond with flat arrows', () => {
  const orig = setupDocumentMock();
  try {
    const elements = narrativeElements();
    renderNarrative(elements, narrativeState({ regime: 'par', price: 1000 }), FORMATTERS);
    assert.equal(elements.regimeBadge.className, 'chip is-blue');
    assert.equal(elements.rateArrow.textContent, '-');
    assert.equal(elements.rateArrow.className, 'br-arrow is-flat');
    assert.equal(elements.priceArrow.textContent, '-');
  } finally {
    restoreDocument(orig);
  }
});

// --- ui.js ---

test('cacheElements resolves the explainer control ids', () => {
  const mockDoc = {
    getElementById(id) { return { id, tagName: 'INPUT' }; }
  };
  const result = cacheElements(mockDoc);
  assert.ok('slRate' in result);
  assert.ok('slCoupon' in result);
  assert.ok('priceValue' in result);
  assert.ok('sensitivityChart' in result);
  assert.equal(result.slRate.id, 'slRate');
});

test('syncSliderLabels formats the rate, coupon, and years labels', () => {
  const elements = {
    slRate: { value: '6' }, slCoupon: { value: '5' }, slYears: { value: '10' },
    rateValue: makeElement(), couponValue: makeElement(), yearsValue: makeElement()
  };
  syncSliderLabels(elements);
  assert.equal(elements.rateValue.textContent, '6.0%');
  assert.equal(elements.couponValue.textContent, '5.0%');
  assert.equal(elements.yearsValue.textContent, '10 years');
});

test('syncSliderLabels uses the singular for a one-year bond', () => {
  const elements = {
    slRate: { value: '5' }, slCoupon: { value: '5' }, slYears: { value: '1' },
    rateValue: makeElement(), couponValue: makeElement(), yearsValue: makeElement()
  };
  syncSliderLabels(elements);
  assert.equal(elements.yearsValue.textContent, '1 year');
});

test('getChartElements returns only the three chart canvases', () => {
  const elements = {
    priceRateChart: 'pr', sensitivityChart: 'se', yieldCurveChart: 'yc', other: 'no'
  };
  assert.deepEqual(getChartElements(elements), {
    priceRateChart: 'pr', sensitivityChart: 'se', yieldCurveChart: 'yc'
  });
});

// --- interactions.js ---

// Build a segmented-toggle container whose child buttons register their click
// handler into the shared listeners map, mirroring how initSegmented wires the
// real #curveToggle group.
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

test('bindEvents wires the sliders, curve presets, and apply button', () => {
  const listeners = {};
  function el(id) {
    return {
      id,
      addEventListener(type, handler) { listeners[`${id}:${type}`] = handler; }
    };
  }
  const elements = {
    slRate: el('slRate'), slCoupon: el('slCoupon'), slYears: el('slYears'),
    btnApplyCurve: el('btnApplyCurve'),
    curveToggle: makeToggle(Object.values(CURVE_BUTTON_IDS), listeners)
  };
  const calls = [];
  bindEvents({
    elements,
    onSliderInput: () => calls.push('slider'),
    onCurveSelect: (key) => calls.push(`curve:${key}`),
    onApplyCurveRate: () => calls.push('apply')
  });

  listeners['slRate:input']();
  listeners['slCoupon:input']();
  listeners['slYears:input']();
  listeners['btnCurveNormal:click']();
  listeners['btnCurveFlat:click']();
  listeners['btnCurveInverted:click']();
  listeners['btnApplyCurve:click']();
  assert.deepEqual(calls, [
    'slider', 'slider', 'slider',
    'curve:normal', 'curve:flat', 'curve:inverted', 'apply'
  ]);
});

// --- charts.js ---

function chartWindow(createdConfigs) {
  return {
    Chart: function MockChart(_canvas, config) {
      if (createdConfigs) {
        createdConfigs.push(config);
      }
      this.type = config.type;
      this.data = config.data;
      this.options = config.options;
      this.update = () => {};
    }
  };
}

function chartData() {
  return {
    elements: { priceRateChart: {}, sensitivityChart: {}, yieldCurveChart: {} },
    priceRate: {
      curve: [{ x: 1, y: 1300 }, { x: 5, y: 1000 }, { x: 12, y: 650 }],
      current: { x: 5, y: 1000 }
    },
    sensitivity: { labels: ['2', '10', '30'], values: [-1.8, -7.4, -13.8], currentIndex: 1 },
    yieldCurve: {
      curve: [{ x: 1, y: 3.3 }, { x: 10, y: 4.8 }, { x: 30, y: 5.4 }],
      current: { x: 10, y: 4.8 }
    },
    formatDollarTick: (value) => `$${value}`
  };
}

test('refreshPalette returns a palette derived from CSS variables', () => {
  const orig = setupDocumentMock();
  try {
    const palette = refreshPalette();
    assert.ok('blue' in palette);
    assert.ok('red' in palette);
    assert.equal(typeof palette.blueA, 'function');
    assert.match(palette.blueA(0.5), /rgba/);
  } finally {
    restoreDocument(orig);
  }
});

test('cssAlpha falls back to the raw value when a color has fewer than three numbers', () => {
  const origDoc = globalThis.document;
  const origGcs = globalThis.getComputedStyle;
  globalThis.document = { body: {}, documentElement: { getAttribute() { return 'dark'; } } };
  globalThis.getComputedStyle = () => ({
    getPropertyValue(prop) {
      return prop === '--note-blue' ? 'blue' : 'rgb(1, 2, 3)';
    }
  });
  try {
    const palette = refreshPalette();
    assert.equal(palette.blueA(0.5), 'blue');
  } finally {
    if (origDoc) globalThis.document = origDoc; else delete globalThis.document;
    if (origGcs) globalThis.getComputedStyle = origGcs; else delete globalThis.getComputedStyle;
  }
});

test('renderCharts creates the three charts on first call and reuses them after', () => {
  const orig = setupDocumentMock();
  const origWin = globalThis.window;
  const configs = [];
  globalThis.window = chartWindow(configs);
  try {
    refreshPalette();
    const first = renderCharts(chartData());
    assert.equal(configs.length, 3);
    assert.ok('priceRate' in first);
    assert.ok('sensitivity' in first);
    assert.ok('yieldCurve' in first);
    assert.deepEqual(first.yieldCurve.data.datasets[1].data, [{ x: 10, y: 4.8 }]);

    const createdBefore = configs.length;
    renderCharts({ charts: first, ...chartData() });
    assert.equal(configs.length, createdBefore, 'no new charts created on reuse');
  } finally {
    restoreDocument(orig);
    if (origWin) globalThis.window = origWin; else delete globalThis.window;
  }
});

test('chart tooltip callbacks produce formatted output', () => {
  const orig = setupDocumentMock();
  const origWin = globalThis.window;
  const configs = [];
  globalThis.window = chartWindow(configs);
  try {
    refreshPalette();
    renderCharts(chartData());

    const [priceLine, curveLine] = configs.filter((c) => c.type === 'line');
    const lineLabel = priceLine.options.plugins.tooltip.callbacks.label({
      dataset: { label: 'Price' },
      parsed: { y: 1000 }
    });
    assert.match(lineLabel, /Price/);

    const curveLabel = curveLine.options.plugins.tooltip.callbacks.label({
      dataset: { label: 'Curve yield' },
      parsed: { y: 4.7837 }
    });
    assert.equal(curveLabel, 'Curve yield: 4.78%');

    const bar = configs.find((c) => c.type === 'bar');
    const barLabel = bar.options.plugins.tooltip.callbacks.label({ parsed: { y: -7.36 } });
    assert.equal(barLabel, '-7.4%');

    // Percent axis ticks always show two decimals and never leak float noise.
    const yieldTick = curveLine.options.scales.y.ticks.callback;
    assert.equal(yieldTick(4.800000000000001), '4.80%');
    assert.equal(yieldTick(3.6000000000000005), '3.60%');
    assert.equal(yieldTick(5), '5.00%');
    const barTick = bar.options.scales.y.ticks.callback;
    assert.equal(barTick(-13.799999999999999), '-13.80%');
  } finally {
    restoreDocument(orig);
    if (origWin) globalThis.window = origWin; else delete globalThis.window;
  }
});
