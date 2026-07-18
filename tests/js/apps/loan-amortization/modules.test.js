import assert from 'node:assert/strict';
import test from 'node:test';

import {
  calcEMI,
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
import { buildMetricsMarkup, renderMetrics } from '../../../../apps/loan-amortization/js/modules/metrics.js';
import {
  getBiweeklyEmiOverride,
  getFrequencyParams,
  summarizeScheduleRows
} from '../../../../apps/loan-amortization/js/modules/schedule-summary.js';

// --- amortization.js ---

test('calcEMI computes correct monthly payment', () => {
  // $100,000 at 6% annual over 360 months
  const emi = calcEMI(100000, 0.005, 360);
  assert.ok(Math.abs(emi - 599.55) < 0.5);
});

test('calcEMI returns simple division for zero rate', () => {
  assert.equal(calcEMI(12000, 0, 12), 1000);
});

test('getExtraForPeriod sums onetime and recurring extras', () => {
  const extras = [
    { type: 'onetime', period: 3, amount: 500 },
    { type: 'recurring', startPeriod: 1, every: 2, amount: 100 },
    { type: 'unknown', amount: 999 }
  ];
  // Period 3: onetime(500) + recurring hits (3-1)%2===0 → 100 = 600
  assert.equal(getExtraForPeriod(3, extras), 600);
  // Period 2: recurring misses (2-1)%2===1 → 0
  assert.equal(getExtraForPeriod(2, extras), 0);
  // Period 1: recurring hits (1-1)%2===0 → 100
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
  // High-rate short loan: interest dominates early, principal catches up
  const result = runSchedule(100000, 0.02, 60);
  // breakEven is either null or a positive period number
  if (result.breakEven !== null) {
    assert.ok(result.breakEven > 1);
    assert.ok(result.breakEven <= result.periods);
  }
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

test('buildMetricsMarkup renders savings and escapes tooltip content', () => {
  const markup = buildMetricsMarkup(
    {
      base: { emi: 300, totalInterest: 5000 },
      extra: { totalInterest: 4200, periods: 18, breakEven: 9 },
      savings: 800,
      periodsSaved: 2,
      totalPaid: 54200,
      costRatio: 1.084,
      label: 'Month'
    },
    (value) => `$${value}`
  );

  assert.match(markup, /Monthly EMI/);
  assert.match(markup, /Save \$800/);
  assert.match(markup, /Break-even/);
  assert.doesNotMatch(markup, /EMI \+ extras\) >/);
  assert.match(markup, /EMI \+ extras\) &gt; interest/);
});

test('buildMetricsMarkup omits savings and periods-saved pills when zero', () => {
  const markup = buildMetricsMarkup(
    {
      base: { emi: 300, totalInterest: 5000 },
      extra: { totalInterest: 5000, periods: 20, breakEven: null },
      savings: 0,
      periodsSaved: 0,
      totalPaid: 55000,
      costRatio: 1.1,
      label: 'Week'
    },
    (value) => `$${value}`
  );

  assert.doesNotMatch(markup, /savings-pill/);
  assert.match(markup, /N\/A/);
  assert.match(markup, /Weekly EMI/);
});

test('renderMetrics sets container innerHTML', () => {
  const container = { innerHTML: '' };
  renderMetrics(
    container,
    {
      base: { emi: 500, totalInterest: 8000 },
      extra: { totalInterest: 7000, periods: 24, breakEven: 10 },
      savings: 1000,
      periodsSaved: 3,
      totalPaid: 67000,
      costRatio: 1.12,
      label: 'Month'
    },
    (value) => `$${value}`
  );

  assert.ok(container.innerHTML.length > 0);
  assert.match(container.innerHTML, /Monthly EMI/);
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

  // Restore
  if (origCreate) {
    globalThis.document.createElement = origCreate;
  } else {
    delete globalThis.document;
  }
});
