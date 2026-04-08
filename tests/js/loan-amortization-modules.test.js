import assert from 'node:assert/strict';
import test from 'node:test';

import { buildMetricsMarkup } from '../../apps/loan-amortization/js/modules/metrics.js';
import {
  getBiweeklyEmiOverride,
  getFrequencyParams,
  summarizeScheduleRows
} from '../../apps/loan-amortization/js/modules/schedule-summary.js';

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
