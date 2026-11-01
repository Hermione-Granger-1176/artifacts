import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import {
  calcEmi,
  getExtraForPeriod,
  runSchedule
} from '../../../../apps/loan-amortization/js/modules/amortization.js';
import {
  createExtra,
  removeExtraById,
  setExtraType,
  updateExtraField,
  summarizeExtra,
  renderExtras
} from '../../../../apps/loan-amortization/js/modules/extras.js';
import {
  formatCurrency,
  formatDollarTick,
  parseNumber
} from '../../../../js/modules/formatting.js';
import { escapeAttribute } from '../../../../js/modules/html-escape.js';
import {
  buildMetricsView,
  formatPeriodsAsDuration,
  renderMetrics
} from '../../../../apps/loan-amortization/js/modules/metrics.js';
import { FakeNode, installFakeDom } from './fake-dom.js';
import {
  getBiweeklyEmiOverride,
  getFrequencyParams,
  summarizeScheduleRows
} from '../../../../apps/loan-amortization/js/modules/schedule-summary.js';

// --- amortization.js ---

test('calcEmi computes correct monthly payment', () => {
  // $100,000 at 6% annual over 360 months
  const emi = calcEmi(100000, 0.005, 360);
  assert.ok(Math.abs(emi - 599.55) < 0.5);
});

test('calcEmi returns simple division for zero rate', () => {
  assert.equal(calcEmi(12000, 0, 12), 1000);
});

test('getExtraForPeriod sums onetime and recurring extras', () => {
  const extras = [
    { type: 'onetime', period: 3, amount: 500 },
    { type: 'recurring', startPeriod: 1, every: 2, amount: 100 },
    { type: 'unknown', amount: 999 }
  ];
  // Period 3: onetime 500 plus a recurring hit ((3-1)%2===0) of 100 is 600
  assert.equal(getExtraForPeriod(3, extras), 600);
  // Period 2: recurring misses ((2-1)%2===1), so 0
  assert.equal(getExtraForPeriod(2, extras), 0);
  // Period 1: recurring hits ((1-1)%2===0), so 100
  assert.equal(getExtraForPeriod(1, extras), 100);
});

test('runSchedule produces a complete amortization without extras', () => {
  const result = runSchedule(10000, 0.01, 12);
  assert.equal(result.periods, 12);
  assert.ok(result.emi > 0);
  assert.equal(result.rows.length, 12);
  assert.ok(result.totalInterest > 0);
  assert.equal(result.totalExtra, 0);
  // Final balance should be zero
  assert.equal(result.rows[11].balance, 0);
});

test('runSchedule with extras shortens the schedule', () => {
  const base = runSchedule(10000, 0.01, 12);
  const withExtras = runSchedule(10000, 0.01, 12, {
    withExtras: true,
    extras: [{ type: 'recurring', startPeriod: 1, every: 1, amount: 200 }]
  });
  assert.ok(withExtras.periods < base.periods);
  assert.ok(withExtras.totalExtra > 0);
});

test('runSchedule respects emiOverride', () => {
  const result = runSchedule(10000, 0.01, 12, { emiOverride: 1000 });
  assert.equal(result.emi, 1000);
  assert.ok(result.periods < 12);
});

test('runSchedule reports breakEven when cumulative principal overtakes interest', () => {
  // At 2% per period, interest dominates early and principal catches up later
  const result = runSchedule(100000, 0.02, 60);
  assert.ok(result.breakEven !== null);
  assert.ok(result.breakEven > 1);
  assert.ok(result.breakEven <= result.periods);
});

test('runSchedule reports period one when principal immediately exceeds interest', () => {
  const result = runSchedule(12000, 0, 12);
  assert.equal(result.breakEven, 1);
});

test('runSchedule caps extra at remaining balance', () => {
  // Large extra that exceeds balance
  const result = runSchedule(1000, 0.01, 12, {
    withExtras: true,
    extras: [{ type: 'onetime', period: 1, amount: 50000 }]
  });
  assert.equal(result.periods, 1);
  assert.equal(result.rows[0].balance, 0);
});

// --- formatting.js ---

test('formatCurrency formats with dollar sign and commas', () => {
  assert.equal(formatCurrency(1234567), '$1,234,567');
  assert.equal(formatCurrency(99.7), '$100');
});

test('formatDollarTick handles millions, thousands, and small values', () => {
  assert.equal(formatDollarTick(2500000), '$2.5M');
  assert.equal(formatDollarTick(50000), '$50k');
  assert.equal(formatDollarTick(1500), '$1.5k');
  assert.equal(formatDollarTick(500), '$500');
  assert.equal(formatDollarTick(-50000), '-$50k');
  assert.equal(formatDollarTick(0), '$0');
});

test('parseNumber strips non-numeric characters', () => {
  assert.equal(parseNumber('$1,234.56'), 1234.56);
  assert.equal(parseNumber('abc'), 0);
});

test('escapeAttribute escapes HTML-sensitive characters', () => {
  assert.equal(escapeAttribute('<a href="x">&'), '&lt;a href=&quot;x&quot;&gt;&amp;');
});

// --- schedule-summary.js ---

test('getFrequencyParams returns cadence metadata for weekly payments', () => {
  assert.deepEqual(getFrequencyParams('weekly'), {
    periodsPerYear: 52,
    label: 'Week'
  });
});

test('getBiweeklyEmiOverride only applies to accelerated biweekly mode', () => {
  assert.equal(
    getBiweeklyEmiOverride({
      principal: 50000,
      annualRate: 5,
      years: 7,
      frequency: 'monthly',
      bwMode: 'accelerated'
    }),
    null
  );

  const accelerated = getBiweeklyEmiOverride({
    principal: 50000,
    annualRate: 5,
    years: 7,
    frequency: 'biweekly',
    bwMode: 'accelerated'
  });
  assert.ok(accelerated !== null);
  assert.ok(accelerated > 0);
});

test('summarizeScheduleRows totals EMI, principal, interest, and extras', () => {
  const totals = summarizeScheduleRows([
    { emi: 100, principal: 70, interest: 30, extra: 0 },
    { emi: 120, principal: 90, interest: 20, extra: 40 }
  ]);

  assert.deepEqual(totals, {
    totalEmi: 220,
    totalPrincipal: 160,
    totalInterest: 50,
    totalExtras: 40
  });
});

const fmt = (value) => `$${value}`;

test('buildMetricsView promotes the EMI to the hero and keeps the other metrics', () => {
  const view = buildMetricsView(
    {
      base: { emi: 300, totalInterest: 5000 },
      extra: { totalInterest: 4200, totalExtra: 6000, periods: 18, breakEven: 9 },
      savings: 800,
      periodsSaved: 2,
      totalPaid: 54200,
      costRatio: 1.084,
      label: 'Month',
      periodsPerYear: 12
    },
    fmt
  );

  assert.equal(view.heroLabel, 'Monthly EMI');
  assert.equal(view.heroValue, '$300');
  assert.equal(view.heroSub, 'Plus $6000 in extra payments over the loan');
  assert.equal(view.chip, 'Saves $800 \u00b7 2m sooner');
  assert.equal(view.interestValue, '$4200');
  assert.equal(view.interestSub, 'Without extras: $5000');
  assert.equal(view.payoffValue, '18 months');
  assert.equal(view.payoffSub, '2 earlier than without extras');
  assert.equal(view.paidValue, '$54200');
  assert.equal(view.paidSub, 'Interest is 8.4% of loan');
  assert.equal(view.breakValue, 'Month 9');
  assert.match(view.heroTip, /each month/);
  assert.match(view.payoffTip, /Number of months/);
  assert.match(view.breakTip, /first month/);
});

test('buildMetricsView leaves the chip and extras sub-line empty when there are no extras', () => {
  const view = buildMetricsView(
    {
      base: { emi: 300, totalInterest: 5000 },
      extra: { totalInterest: 5000, totalExtra: 0, periods: 20, breakEven: null },
      savings: 0,
      periodsSaved: 0,
      totalPaid: 55000,
      costRatio: 1.1,
      label: 'Week',
      periodsPerYear: 52
    },
    fmt
  );

  assert.equal(view.chip, '');
  assert.equal(view.heroSub, 'Fixed payment, no extras');
  assert.equal(view.payoffSub, 'Until the loan is repaid');
  assert.equal(view.breakValue, 'N/A');
  assert.equal(view.heroLabel, 'Weekly EMI');
});

test('buildMetricsView chip shows only the part that applies', () => {
  const base = {
    base: { emi: 300, totalInterest: 5000 },
    extra: { totalInterest: 4990, totalExtra: 100, periods: 20, breakEven: 3 },
    totalPaid: 55000,
    costRatio: 1.1,
    label: 'Month',
    periodsPerYear: 12
  };

  assert.equal(buildMetricsView({ ...base, savings: 0.5, periodsSaved: 14 }, fmt).chip, '1y 2m sooner');
  assert.equal(buildMetricsView({ ...base, savings: 10, periodsSaved: 0 }, fmt).chip, 'Saves $10');
});

test('formatPeriodsAsDuration converts periods to years and months', () => {
  assert.equal(formatPeriodsAsDuration(30, 12), '2y 6m');
  assert.equal(formatPeriodsAsDuration(24, 12), '2y');
  assert.equal(formatPeriodsAsDuration(5, 12), '5m');
  assert.equal(formatPeriodsAsDuration(26, 26), '1y');
  assert.equal(formatPeriodsAsDuration(1, 52), 'under 1m');
});

// The metrics block ships in index.html; the test builds one slot per
// data-metric name found there, so the page and the module cannot drift apart.
const pageMarkup = readFileSync(
  new URL('../../../../apps/loan-amortization/index.html', import.meta.url),
  'utf8'
);
const pageSlotNames = [...pageMarkup.matchAll(/data-metric="(\w+)"/g)].map((match) => match[1]);

function makeMetricsContainer() {
  const restore = installFakeDom();
  const container = new FakeNode('div');
  const slots = {};
  for (const name of pageSlotNames) {
    const slot = new FakeNode(name.endsWith('Tip') ? 'button' : 'div');
    slot.setAttribute('data-metric', name);
    slots[name] = slot;
    container.append(slot);
  }
  return { container, slots, restore };
}

const sampleMetrics = {
  base: { emi: 500, totalInterest: 8000 },
  extra: { totalInterest: 7000, totalExtra: 900, periods: 24, breakEven: 10 },
  savings: 1000,
  periodsSaved: 3,
  totalPaid: 67000,
  costRatio: 1.12,
  label: 'Month',
  periodsPerYear: 12
};

test('page markup ships a slot for every metric the module writes', () => {
  const view = buildMetricsView(sampleMetrics, fmt);
  assert.deepEqual([...pageSlotNames].sort(), Object.keys(view).sort());
});

test('renderMetrics writes text, tips, and the chip into the shipped slots', () => {
  const { container, slots, restore } = makeMetricsContainer();
  try {
    renderMetrics(container, sampleMetrics, fmt);

    assert.equal(slots.heroValue.textContent, '$500');
    assert.equal(slots.payoffValue.textContent, '24 months');
    assert.equal(slots.heroTip.getAttribute('data-tip'), 'Fixed payment amount each month, excluding extra payments');
    assert.equal(slots.heroTip.getAttribute('aria-label'), slots.heroTip.getAttribute('data-tip'));
    assert.equal(slots.chip.textContent, 'Saves $1000 \u00b7 3m sooner');
    assert.equal(slots.chip.classList.contains('is-empty'), false);
    assert.equal(slots.chip.getAttribute('aria-hidden'), 'false');
  } finally {
    restore();
  }
});

test('renderMetrics keeps nodes and the chip text when values change or the chip hides', () => {
  const { container, slots, restore } = makeMetricsContainer();
  try {
    renderMetrics(container, sampleMetrics, fmt);
    const heroValue = slots.heroValue;
    const chipText = slots.chip.textContent;

    renderMetrics(
      container,
      { ...sampleMetrics, base: { emi: 650, totalInterest: 8000 }, savings: 0, periodsSaved: 0 },
      fmt
    );

    assert.equal(slots.heroValue, heroValue);
    assert.equal(slots.heroValue.textContent, '$650');
    // The chip keeps its last text so it holds its width while it fades out.
    assert.equal(slots.chip.textContent, chipText);
    assert.equal(slots.chip.classList.contains('is-empty'), true);
    assert.equal(slots.chip.getAttribute('aria-hidden'), 'true');
  } finally {
    restore();
  }
});

test('renderMetrics skips slots the markup does not provide', () => {
  const restore = installFakeDom();
  try {
    const container = new FakeNode('div');
    assert.doesNotThrow(() => renderMetrics(container, sampleMetrics, fmt));
  } finally {
    restore();
  }
});

// --- extras.js ---

test('updateExtraField rejects fields not in the allowlist', () => {
  const extras = [createExtra(1)];
  updateExtraField(extras, 1, '__proto__', '999');
  assert.equal(extras[0].amount, 500); // unchanged
  updateExtraField(extras, 1, 'constructor', '1');
  assert.equal(extras[0].amount, 500);
});

test('updateExtraField accepts allowed fields with valid values', () => {
  const extras = [createExtra(1)];
  updateExtraField(extras, 1, 'amount', '1000');
  assert.equal(extras[0].amount, 1000);
  updateExtraField(extras, 1, 'every', '3');
  assert.equal(extras[0].every, 3);
});

test('updateExtraField rejects NaN and negative values', () => {
  const extras = [createExtra(1)];
  updateExtraField(extras, 1, 'amount', 'abc');
  assert.equal(extras[0].amount, 500); // unchanged, NaN rejected
  updateExtraField(extras, 1, 'amount', '-10');
  assert.equal(extras[0].amount, 500); // unchanged, negative rejected
});

test('updateExtraField rejects zero for period fields', () => {
  const extras = [createExtra(1)];
  updateExtraField(extras, 1, 'every', '0');
  assert.equal(extras[0].every, 1); // unchanged, zero rejected for period field
  updateExtraField(extras, 1, 'startPeriod', '0');
  assert.equal(extras[0].startPeriod, 1);
});

test('removeExtraById filters by id', () => {
  const extras = [createExtra(1), createExtra(2), createExtra(3)];
  const result = removeExtraById(extras, 2);
  assert.equal(result.length, 2);
  assert.deepEqual(result.map((e) => e.id), [1, 3]);
});

test('setExtraType changes the type of a matching extra', () => {
  const extras = [createExtra(1)];
  assert.equal(extras[0].type, 'recurring');
  setExtraType(extras, 1, 'onetime');
  assert.equal(extras[0].type, 'onetime');
});

test('setExtraType is a no-op for non-matching id', () => {
  const extras = [createExtra(1)];
  setExtraType(extras, 999, 'onetime');
  assert.equal(extras[0].type, 'recurring');
});

test('summarizeExtra describes a recurring payment', () => {
  const extra = { type: 'recurring', amount: 500, every: 1, startPeriod: 1 };
  const summary = summarizeExtra(extra, 'Month');
  assert.match(summary, /Pays \$500/);
  assert.match(summary, /every Month/);
  assert.match(summary, /starting from Month 1/);
});

test('summarizeExtra describes recurring with multi-period interval', () => {
  const extra = { type: 'recurring', amount: 1000, every: 3, startPeriod: 6 };
  const summary = summarizeExtra(extra, 'Month');
  assert.match(summary, /every 3 Months/);
  assert.match(summary, /starting from Month 6/);
});

test('summarizeExtra describes a one-time payment', () => {
  const extra = { type: 'onetime', amount: 2000, period: 12 };
  const summary = summarizeExtra(extra, 'Month');
  assert.match(summary, /One-time payment of \$2,000/);
  assert.match(summary, /at Month 12/);
});

function extraRows(container) {
  return container.children;
}

test('renderExtras builds recurring and one-time DOM elements', () => {
  const children = [];
  const container = {
    innerHTML: '',
    appendChild(child) { children.push(child); }
  };
  // Stub document.createElement for Node.js
  const origCreate = globalThis.document?.createElement;
  globalThis.document = {
    createElement(tag) {
      const attrs = {};
      return {
        tagName: tag,
        className: '',
        dataset: {},
        innerHTML: '',
        setAttribute(k, v) { attrs[k] = v; },
        getAttribute(k) { return attrs[k] ?? null; }
      };
    }
  };

  const extras = [
    { id: 1, type: 'recurring', amount: 500, every: 1, startPeriod: 1 },
    { id: 2, type: 'onetime', amount: 2000, period: 6 }
  ];

  renderExtras({ container, extras, periodLabel: 'Month' });

  assert.equal(children.length, 2);
  assert.equal(children[0].className, 'extra-item');
  assert.match(children[0].innerHTML, /Recurring/);
  assert.match(children[0].innerHTML, /data-field="amount"/);
  assert.match(children[1].innerHTML, /One-time/);
  assert.match(children[1].innerHTML, /data-field="period"/);
  assert.match(children[0].innerHTML, /class="btn-remove"/);
  assert.match(children[0].innerHTML, /class="extra-summary">Pays \$500 every Month starting from Month 1</);
  assert.match(children[0].innerHTML, /data-field="every"/);
  assert.match(children[0].innerHTML, /data-field="startPeriod"/);
  assert.match(children[1].innerHTML, /extra-fields is-onetime/);
  assert.match(children[1].innerHTML, /One-time payment of \$2,000 at Month 6/);
  assert.doesNotMatch(children[1].innerHTML, /info-tip/);
  assert.equal(children[0].innerHTML.match(/<svg class="loan-icon"/g)?.length, 2);
  assert.match(children[0].innerHTML, /<\/svg>Recurring/);
  assert.match(children[1].innerHTML, /<\/svg>One-time/);

  // Restore
  if (origCreate) {
    globalThis.document.createElement = origCreate;
  } else {
    delete globalThis.document;
  }
});


test('renderExtras puts focus back on the control that was pressed', () => {
  const saved = globalThis.document;
  const focused = [];
  const pressed = { dataset: { action: 'set-type', type: 'onetime' }, closest: () => ({ dataset: { extraId: '7' } }) };
  const rebuilt = { focus() { focused.push(this); } };
  const queries = [];
  const container = {
    innerHTML: '',
    contains: (node) => node === pressed,
    appendChild() {},
    querySelector(selector) { queries.push(selector); return rebuilt; }
  };
  globalThis.document = {
    activeElement: pressed,
    createElement: () => ({ dataset: {}, innerHTML: '', setAttribute() {} })
  };
  try {
    renderExtras({ container, extras: [{ id: 7, type: 'onetime', amount: 100, period: 2 }], periodLabel: 'Month' });
    assert.deepEqual(queries, ['[data-extra-id="7"] [data-action="set-type"][data-type="onetime"]']);
    assert.deepEqual(focused, [rebuilt]);

    // A field keeps focus by its data-field; a control outside the rows is left alone.
    pressed.dataset = { field: 'amount' };
    queries.length = 0;
    renderExtras({ container, extras: [], periodLabel: 'Month' });
    assert.deepEqual(queries, ['[data-extra-id="7"] [data-field="amount"]']);
    container.contains = () => false;
    queries.length = 0;
    renderExtras({ container, extras: [], periodLabel: 'Month' });
    assert.deepEqual(queries, []);
  } finally {
    globalThis.document = saved;
  }
});
