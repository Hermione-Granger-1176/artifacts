import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
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
  sensitivityExplainText,
  sizingCopy
} from '../../../../apps/bond-price-vs-rate/js/modules/narrative.js';
import {
  YIELD_CURVES,
  bondAnalytics,
  bondPrice,
  bondSchedule,
  curveYieldPct,
  priceRegime
} from '../../../../apps/bond-price-vs-rate/js/modules/bond-math.js';
import { bindEvents } from '../../../../apps/bond-price-vs-rate/js/modules/interactions.js';
import {
  CURVE_BUTTON_IDS,
  cacheElements,
  getChartElements,
  nudgeRateValue,
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
    dataset: {},
    parentNode: null,
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
    append(...nodes) {
      for (const node of nodes) {
        node.remove?.();
        node.parentNode = this;
        this.children.push(node);
      }
    },
    appendChild(child) { this.append(child); return child; },
    remove() {
      if (this.parentNode) {
        this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
        this.parentNode = null;
      }
    },
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
    curve: {
      key: 'normal',
      label: 'Normal',
      atMaturityPct: 4.7837,
      shapes: {
        normal: { label: 'Normal', atMaturityPct: 4.7837 },
        flat: { label: 'Flat', atMaturityPct: 4.5 },
        inverted: { label: 'Inverted', atMaturityPct: 4.07 }
      }
    },
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
    assert.equal(first.children[1].children[0].textContent, '$50.00');
    assert.equal(first.children[1].children[1].textContent, '', 'only the final period carries the face note');
    assert.equal(first.children[2].textContent, (1 / 1.06).toFixed(4));

    // The final period merges the face into the payment and flags it.
    const final = tbody.children[9];
    assert.equal(final.children[1].children[0].textContent, '$1,050.00');
    assert.match(final.children[1].children[1].textContent, /\$1,000 face/);

    const total = tbody.children[10];
    assert.equal(total.className, 'br-schedule-total');
    assert.equal(total.children[1].textContent, '$926.40');
  } finally {
    restoreDocument(orig);
  }
});

test('renderScheduleTable updates the cells in place and only changes rows when the years change', () => {
  const orig = setupDocumentMock();
  try {
    const tbody = makeElement();
    renderScheduleTable(tbody, narrativeState(), FORMATTERS);
    const rows = [...tbody.children];
    const total = rows[10];

    // A new rate keeps every row and cell node, and rewrites their text.
    renderScheduleTable(
      tbody,
      narrativeState({
        bond: { faceValue: 1000, couponRatePct: 5, years: 10, annualYieldPct: 8 },
        price: 798.7,
        schedule: buildSchedule(5, 10, 8)
      }),
      FORMATTERS
    );
    assert.deepEqual([...tbody.children], rows, 'the same row nodes stay in place');
    assert.equal(rows[0].children[2].textContent, (1 / 1.08).toFixed(4));
    assert.equal(total.children[1].textContent, '$798.70');

    // Fewer years remove the trailing rows; the old final row stops carrying the face note.
    renderScheduleTable(
      tbody,
      narrativeState({
        bond: { faceValue: 1000, couponRatePct: 5, years: 3, annualYieldPct: 6 },
        schedule: buildSchedule(5, 3, 6)
      }),
      FORMATTERS
    );
    assert.equal(tbody.children.length, 4);
    assert.equal(tbody.children[3], total, 'the total row stays last');
    assert.equal(tbody.children[2].children[1].children[0].textContent, '$1,050.00');
    assert.match(tbody.children[2].children[1].children[1].textContent, /face/);

    // More years add rows before the total, and the face note moves to the new final row.
    renderScheduleTable(
      tbody,
      narrativeState({
        bond: { faceValue: 1000, couponRatePct: 5, years: 12, annualYieldPct: 6 },
        schedule: buildSchedule(5, 12, 6)
      }),
      FORMATTERS
    );
    assert.equal(tbody.children.length, 13);
    assert.equal(tbody.children[12], total);
    assert.equal(tbody.children[2].children[1].children[1].textContent, '');
    assert.match(tbody.children[11].children[1].children[1].textContent, /face/);
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
    assert.ok(couponRow.children[1].children[0].style.scale.startsWith('0.416'));

    // A later render reuses the rows, so the meter's width transition runs.
    const rows = [...container.children];
    const fill = couponRow.children[1].children[0];
    renderCouponCompare(
      container,
      narrativeState({ bond: { faceValue: 1000, couponRatePct: 12, years: 10, annualYieldPct: 6 } }),
      FORMATTERS
    );
    assert.deepEqual([...container.children], rows);
    assert.equal(couponRow.children[1].children[0], fill);
    assert.equal(fill.style.scale, '1 1');
    assert.equal(couponRow.children[2].textContent, '12.0%');
  } finally {
    restoreDocument(orig);
  }
});

test('renderCouponCompare adopts rows that are already in the markup', () => {
  const orig = setupDocumentMock();
  try {
    const container = makeElement();
    const rows = ['This bond', 'Market'].map((label) => {
      const row = makeElement();
      const name = makeElement({ textContent: label });
      const track = makeElement();
      const fill = makeElement();
      track.append(fill);
      row.append(name, track, makeElement({ textContent: '5.0%' }));
      return row;
    });
    container.append(...rows);
    renderCouponCompare(container, narrativeState(), FORMATTERS);
    assert.deepEqual([...container.children], rows, 'the markup rows are kept, not rebuilt');
    assert.equal(rows[1].children[2].textContent, '6.0%');
    assert.equal(rows[1].children[1].children[0].style.scale, '0.5 1');
  } finally {
    restoreDocument(orig);
  }
});

// The stacked callouts keep one child per variant; the active one is what a reader sees.
function activeVariant(element) {
  const active = element.children.filter((child) => child.classList.contains('is-active'));
  assert.equal(active.length, 1, 'exactly one variant is active');
  return active[0];
}

function activeText(element) {
  return activeVariant(element).textContent;
}

function variantNodes(element) {
  return element.children.filter((child) => child.getAttribute('data-variant'));
}

function ghostNodes(element) {
  return element.children.filter((child) => child.getAttribute('data-ghost'));
}

function variantKeys(element) {
  return variantNodes(element).map((child) => child.getAttribute('data-variant'));
}

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
    btnApplyCurve: makeElement(),
    btnApplyCurveLabel: makeElement()
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
    assert.ok(couponsRow.children[1].children[0].style.scale.startsWith('0.397'));
    assert.ok(faceRow.children[1].children[0].style.scale.startsWith('0.602'));
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
  assert.match(normal, /versus the 6.0% market rate set on the left/);

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
    assert.deepEqual(variantKeys(elements.regimeBadge), ['premium', 'par', 'discount']);
    assert.equal(activeText(elements.regimeBadge), 'Discount');
    assert.equal(elements.regimeBadge.className, 'chip reserve is-red');
    assert.equal(elements.rateArrow.textContent, '▲');
    assert.equal(elements.rateArrow.className, 'br-arrow is-up');
    assert.equal(elements.priceArrow.textContent, '▼');
    assert.equal(elements.couponCompare.children.length, 2);
    assert.equal(elements.pvSplit.children.length, 2);
    assert.equal(elements.mathLegendCoupon.textContent, '$50');
    assert.equal(elements.mathSchedule.children.length, 11);
    assert.match(activeText(elements.mathExplain), /market rate/);
    assert.match(activeText(elements.heroExplain), /discount to its \$1,000 face value/);
    assert.match(activeText(elements.mechanismExplain), /sits below the market/);
    assert.match(activeText(elements.rippleExplain), /loses value/);
    assert.equal(elements.statModified.textContent, '7.6');
    assert.match(activeText(elements.analystExplain), /Modified duration/);
    assert.deepEqual(variantKeys(elements.curveExplain), ['normal', 'flat', 'inverted']);
    assert.match(activeText(elements.curveExplain), /normal curve/);
    assert.equal(elements.btnApplyCurveLabel.textContent, 'Set the market rate to 4.8%');
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
    assert.equal(elements.regimeBadge.className, 'chip reserve is-green');
    assert.equal(activeText(elements.regimeBadge), 'Premium');
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
    assert.equal(elements.regimeBadge.className, 'chip reserve is-blue');
    assert.equal(activeText(elements.regimeBadge), 'At par');
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

test('nudgeRateValue restarts the readout highlight on every call', () => {
  const classes = new Set();
  const log = [];
  const readout = {
    get offsetWidth() { log.push('reflow'); return 0; },
    classList: {
      add(cls) { classes.add(cls); log.push(`add:${cls}`); },
      remove(cls) { classes.delete(cls); log.push(`remove:${cls}`); }
    }
  };

  nudgeRateValue({ rateValue: readout });
  nudgeRateValue({ rateValue: readout });

  assert.equal(classes.has('is-nudged'), true);
  assert.deepEqual(log, [
    'remove:is-nudged', 'reflow', 'add:is-nudged',
    'remove:is-nudged', 'reflow', 'add:is-nudged'
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

test('renderNarrative stacks every variant so swapping regimes keeps the same copy slots', () => {
  const orig = setupDocumentMock();
  try {
    const elements = narrativeElements();
    renderNarrative(elements, narrativeState(), FORMATTERS);
    const heroNodes = [...elements.heroExplain.children];
    assert.equal(variantNodes(elements.heroExplain).length, 3);
    assert.equal(ghostNodes(elements.heroExplain).length, 3);
    assert.equal(variantNodes(elements.heroExplain).filter((node) => node.classList.contains('is-active')).length, 1);

    renderNarrative(elements, narrativeState({ regime: 'premium', price: 1081.11 }), FORMATTERS);
    assert.deepEqual([...elements.heroExplain.children], heroNodes, 'the variant nodes are reused');
    assert.match(activeText(elements.heroExplain), /premium over the \$1,000 face value/);
    assert.match(activeText(elements.rippleExplain), /gain value/);

    // Only the active variant carries real copy; the sizing copy reserves the space.
    assert.deepEqual(
      variantNodes(elements.heroExplain).map((node) => node.textContent === ''),
      [false, true, true]
    );
    const ghosts = ghostNodes(elements.heroExplain);
    assert.ok(ghosts.some((node) => /matches this bond's 12.0% coupon/.test(node.textContent)));
    assert.ok(ghosts.some((node) => /Rates rose to 12.0%/.test(node.textContent)));
    assert.ok(ghosts.every((node) => node.getAttribute('aria-hidden') === 'true'));

    // Switching the curve swaps the active curve story and quotes that curve's own rate.
    renderNarrative(
      elements,
      narrativeState({
        curve: {
          key: 'inverted',
          label: 'Inverted',
          atMaturityPct: 4.07,
          shapes: {
            normal: { label: 'Normal', atMaturityPct: 4.7837 },
            flat: { label: 'Flat', atMaturityPct: 4.5 },
            inverted: { label: 'Inverted', atMaturityPct: 4.07 }
          }
        }
      }),
      FORMATTERS
    );
    assert.match(activeText(elements.curveExplain), /inverted curve offers about 4.1%/);
    const flat = variantNodes(elements.curveExplain).find((node) => node.getAttribute('data-variant') === 'flat');
    assert.equal(flat.textContent, '', 'an inactive curve story is empty');
  } finally {
    restoreDocument(orig);
  }
});

test('renderNarrative falls back to the selected curve when the state has no shape table', () => {
  const orig = setupDocumentMock();
  try {
    const elements = narrativeElements();
    renderNarrative(
      elements,
      narrativeState({ curve: { key: 'flat', label: 'Flat', atMaturityPct: 4.5 } }),
      FORMATTERS
    );
    assert.deepEqual(variantKeys(elements.curveExplain), ['flat']);
    assert.match(activeText(elements.curveExplain), /A flat curve pays nothing extra/);
  } finally {
    restoreDocument(orig);
  }
});

test('renderNarrative adopts variant markup that is already on the page', () => {
  const orig = setupDocumentMock();
  try {
    const elements = narrativeElements();
    const authored = ['premium', 'par', 'discount'].map((key) => {
      const node = makeElement();
      node.setAttribute('data-variant', key);
      return node;
    });
    elements.regimeBadge.append(...authored);
    const authoredGhost = makeElement();
    authoredGhost.setAttribute('data-ghost', 'text');
    elements.mathExplain.append(authoredGhost);
    renderNarrative(elements, narrativeState(), FORMATTERS);
    assert.equal(ghostNodes(elements.mathExplain).length, 1, 'an authored sizing node is adopted');
    assert.ok(authoredGhost.textContent.includes('12.0% market rate'));
    assert.deepEqual([...elements.regimeBadge.children], authored, 'authored variants are kept, none added');
    assert.equal(authored[2].textContent, 'Discount');
    assert.equal(authored[2].classList.contains('is-active'), true);
    assert.equal(authored[1].classList.contains('is-active'), false);
  } finally {
    restoreDocument(orig);
  }
});

test('the static first-paint copy in index.html matches the default render', () => {
  const html = readFileSync(
    new URL('../../../../apps/bond-price-vs-rate/index.html', import.meta.url),
    'utf8'
  );
  const bond = { faceValue: 1000, couponRatePct: 5, years: 10, annualYieldPct: 5, frequency: 1 };
  const price = bondPrice(bond);
  const regime = priceRegime(5, 5);
  const shapes = Object.fromEntries(
    Object.entries(YIELD_CURVES).map(([key, shape]) => [
      key,
      { label: shape.label, atMaturityPct: curveYieldPct(shape, 10) }
    ])
  );
  const shock = (years) =>
    (bondPrice({ ...bond, years, annualYieldPct: bond.annualYieldPct + 1 }) / bondPrice({ ...bond, years }) - 1) * 100;
  const state = narrativeState({
    bond,
    price,
    regime,
    schedule: bondSchedule(bond),
    analytics: bondAnalytics(bond),
    sensitivity: { currentPct: shock(10), shortPct: shock(2), longPct: shock(30) },
    curve: { key: 'normal', ...shapes.normal, shapes }
  });

  const sizing = sizingCopy(FORMATTERS);
  const expectCopy = (id, texts, active) => {
    const reals = Object.entries(texts)
      .map(([key, text]) => `<span class="br-variant${key === active ? ' is-active' : ''}" data-variant="${key}">${key === active ? text : ''}</span>`)
      .join('');
    const ghosts = Object.entries(sizing[id])
      .map(([key, text]) => `<span class="reserve-ghost" data-ghost="${key}" aria-hidden="true">${text}</span>`)
      .join('');
    assert.ok(
      html.includes(`<p class="app-callout-body reserve" id="${id}">${reals}${ghosts}</p>`),
      `${id} first-paint copy matches the default render`
    );
  };
  const byRegime = (build) =>
    Object.fromEntries(['premium', 'par', 'discount'].map((key) => [key, build({ ...state, regime: key }, FORMATTERS)]));

  expectCopy('heroExplain', byRegime(heroExplainText), regime);
  expectCopy('mechanismExplain', byRegime(mechanismExplainText), regime);
  expectCopy('rippleExplain', byRegime(rippleExplainText), regime);
  expectCopy(
    'curveExplain',
    Object.fromEntries(
      Object.entries(shapes).map(([key, shape]) => [key, curveExplainText({ ...state, curve: { ...shape, key } }, FORMATTERS)])
    ),
    'normal'
  );
  expectCopy('mathExplain', { text: mathExplainText(state, FORMATTERS) }, 'text');
  expectCopy('sensitivityExplain', { text: sensitivityExplainText(state, FORMATTERS) }, 'text');
  expectCopy('analystExplain', { text: analystExplainText(state, FORMATTERS) }, 'text');

  // The comparison rows ship with the default labels and values.
  for (const label of ['This bond', 'Market', 'Coupons', 'Face value']) {
    assert.ok(html.includes(`<span class="br-compare-label">${label}</span>`), `${label} row is in the markup`);
  }
  assert.ok(html.includes(`<span class="br-compare-num">${formatPercent(5)}</span>`));
  const { pvCoupons, pvFace } = state.analytics;
  assert.ok(html.includes(`<span class="br-compare-num">${formatCurrency(pvCoupons, 0)}</span>`));
  assert.ok(html.includes(`<span class="br-compare-num">${formatCurrency(pvFace, 0)}</span>`));
});

// --- charts.js: which charts redraw, how, and when ---

function recordingWindow(updates, { reducedMotion = false } = {}) {
  return {
    matchMedia: () => ({ matches: reducedMotion }),
    Chart: function RecordingChart(canvas, config) {
      this.type = config.type;
      this.data = config.data;
      this.options = config.options;
      this.canvas = canvas;
      this.update = (mode) => updates.push({ chart: this, mode });
    }
  };
}

function drawsOf(updates, chart) {
  return updates.filter((entry) => entry.chart === chart).map((entry) => entry.mode);
}

test('renderCharts animates only the first draw, then redraws input changes without animation', () => {
  const orig = setupDocumentMock();
  const origWin = globalThis.window;
  const updates = [];
  globalThis.window = recordingWindow(updates);
  try {
    refreshPalette();
    const charts = renderCharts(chartData());
    assert.deepEqual(updates.map((entry) => entry.mode), [undefined, undefined, undefined], 'first draw eases in');

    updates.length = 0;
    renderCharts({ charts, ...chartData() });
    assert.deepEqual(updates.map((entry) => entry.mode), ['none', 'none', 'none'], 'slider ticks redraw at once');
  } finally {
    restoreDocument(orig);
    if (origWin) globalThis.window = origWin; else delete globalThis.window;
  }
});

test('renderCharts redraws only the charts it is given data for', () => {
  const orig = setupDocumentMock();
  const origWin = globalThis.window;
  const updates = [];
  globalThis.window = recordingWindow(updates);
  try {
    refreshPalette();
    const charts = renderCharts(chartData());
    updates.length = 0;

    const { priceRate, sensitivity, elements, formatDollarTick } = chartData();
    renderCharts({ charts, elements, priceRate, sensitivity, formatDollarTick });
    assert.equal(drawsOf(updates, charts.yieldCurve).length, 0, 'the yield curve is left alone');
    assert.equal(drawsOf(updates, charts.priceRate).length, 1);
    assert.equal(drawsOf(updates, charts.sensitivity).length, 1);
  } finally {
    restoreDocument(orig);
    if (origWin) globalThis.window = origWin; else delete globalThis.window;
  }
});

test('renderCharts eases a requested change unless the reader prefers reduced motion', () => {
  for (const reducedMotion of [false, true]) {
    const orig = setupDocumentMock();
    const origWin = globalThis.window;
    const updates = [];
    globalThis.window = recordingWindow(updates, { reducedMotion });
    try {
      refreshPalette();
      const charts = renderCharts(chartData());
      updates.length = 0;
      const { yieldCurve, elements, formatDollarTick } = chartData();
      renderCharts({ charts, elements, yieldCurve, formatDollarTick, animate: { yieldCurve: true } });
      assert.deepEqual(drawsOf(updates, charts.yieldCurve), [reducedMotion ? 'none' : undefined]);
    } finally {
      restoreDocument(orig);
      if (origWin) globalThis.window = origWin; else delete globalThis.window;
    }
  }
});

test('renderCharts tolerates a browser without matchMedia', () => {
  const orig = setupDocumentMock();
  const origWin = globalThis.window;
  const updates = [];
  const win = recordingWindow(updates);
  delete win.matchMedia;
  globalThis.window = win;
  try {
    refreshPalette();
    const charts = renderCharts(chartData());
    updates.length = 0;
    const { yieldCurve, elements, formatDollarTick } = chartData();
    renderCharts({ charts, elements, yieldCurve, formatDollarTick, animate: { yieldCurve: true } });
    assert.deepEqual(drawsOf(updates, charts.yieldCurve), [undefined]);
  } finally {
    restoreDocument(orig);
    if (origWin) globalThis.window = origWin; else delete globalThis.window;
  }
});

test('renderCharts keeps an off-screen chart pending and draws it once it scrolls into view', () => {
  const orig = setupDocumentMock();
  const origWin = globalThis.window;
  const origObserver = globalThis.IntersectionObserver;
  const updates = [];
  let notify = null;
  const observed = [];
  globalThis.IntersectionObserver = class {
    constructor(callback, options) {
      notify = callback;
      this.options = options;
    }
    observe(target) { observed.push(target); }
  };
  globalThis.window = recordingWindow(updates);
  try {
    refreshPalette();
    const data = chartData();
    const charts = renderCharts(data);
    assert.equal(observed.length, 3, 'each canvas is watched');
    updates.length = 0;

    // The sensitivity chart scrolls out of range; the others stay in view.
    notify([{ target: data.elements.sensitivityChart, isIntersecting: false }]);
    renderCharts({ charts, ...chartData() });
    assert.equal(drawsOf(updates, charts.sensitivity).length, 0, 'an off-screen chart is not redrawn');
    assert.equal(drawsOf(updates, charts.priceRate).length, 1);

    // The redraw on entering view uses the newest data.
    const latest = chartData();
    latest.sensitivity = { labels: ['2'], values: [-2], currentIndex: 0 };
    renderCharts({ charts, ...latest });
    updates.length = 0;
    notify([
      { target: {}, isIntersecting: true },
      { target: data.elements.sensitivityChart, isIntersecting: true }
    ]);
    assert.deepEqual(drawsOf(updates, charts.sensitivity), ['none']);
    assert.deepEqual(charts.sensitivity.data.labels, ['2'], 'the latest data is the one drawn');
  } finally {
    restoreDocument(orig);
    if (origWin) globalThis.window = origWin; else delete globalThis.window;
    if (origObserver) globalThis.IntersectionObserver = origObserver; else delete globalThis.IntersectionObserver;
  }
});

test('the sizing copy is at least as long as any copy a slider setting can print', () => {
  const sizing = sizingCopy(FORMATTERS);
  const shapesFor = (years) =>
    Object.fromEntries(
      Object.entries(YIELD_CURVES).map(([key, shape]) => [key, { label: shape.label, atMaturityPct: curveYieldPct(shape, years) }])
    );
  const builders = {
    heroExplain: (state, key) => heroExplainText({ ...state, regime: key }, FORMATTERS),
    mechanismExplain: (state, key) => mechanismExplainText({ ...state, regime: key }, FORMATTERS),
    rippleExplain: (state, key) => rippleExplainText({ ...state, regime: key }),
    curveExplain: (state, key) => curveExplainText({ ...state, curve: { ...state.curve.shapes[key], key } }, FORMATTERS),
    mathExplain: (state) => mathExplainText(state, FORMATTERS),
    sensitivityExplain: (state) => sensitivityExplainText(state, FORMATTERS),
    analystExplain: (state) => analystExplainText(state, FORMATTERS)
  };
  const longest = Object.fromEntries(Object.keys(builders).map((id) => [id, {}]));

  for (let coupon = 1; coupon <= 12; coupon += 0.5) {
    for (let rate = 1; rate <= 12; rate += 0.5) {
      for (let years = 1; years <= 30; years += 1) {
        const bond = { faceValue: 1000, couponRatePct: coupon, years, annualYieldPct: rate, frequency: 1 };
        const shock = (maturity) =>
          (bondPrice({ ...bond, years: maturity, annualYieldPct: rate + 1 }) / bondPrice({ ...bond, years: maturity }) - 1) * 100;
        const shapes = shapesFor(years);
        const state = {
          bond,
          price: bondPrice(bond),
          regime: priceRegime(coupon, rate),
          schedule: bondSchedule(bond),
          analytics: bondAnalytics(bond),
          sensitivity: { currentPct: shock(years), shortPct: shock(2), longPct: shock(30) },
          curve: { key: 'normal', ...shapes.normal, shapes }
        };
        for (const [id, build] of Object.entries(builders)) {
          for (const key of Object.keys(sizing[id])) {
            longest[id][key] = Math.max(longest[id][key] ?? 0, build(state, key).length);
          }
        }
      }
    }
  }

  for (const [id, keys] of Object.entries(longest)) {
    for (const [key, length] of Object.entries(keys)) {
      assert.ok(
        sizing[id][key].length >= length,
        `${id}/${key} sizing copy (${sizing[id][key].length}) covers the longest real copy (${length})`
      );
    }
  }
});
