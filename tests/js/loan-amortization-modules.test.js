import assert from 'node:assert/strict';
import test from 'node:test';

import {
  calcEMI,
  getExtraForPeriod,
  runSchedule
} from '../../apps/loan-amortization/js/modules/amortization.js';
import {
  formatCurrency,
  formatDollarTick,
  parseNumber,
  escapeAttribute
} from '../../apps/loan-amortization/js/modules/formatting.js';
import { buildMetricsMarkup } from '../../apps/loan-amortization/js/modules/metrics.js';
import {
  getBiweeklyEmiOverride,
  getFrequencyParams,
  summarizeScheduleRows
} from '../../apps/loan-amortization/js/modules/schedule-summary.js';

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
