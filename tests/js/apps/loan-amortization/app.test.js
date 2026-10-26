import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import { cleanupMocks, setupFullMocks } from '../../common/app-entry-test-support.js';
import { FakeNode, installFakeDom } from './fake-dom.js';

const pageMarkup = readFileSync(
  new URL('../../../../apps/loan-amortization/index.html', import.meta.url),
  'utf8'
);
const metricSlotNames = [...pageMarkup.matchAll(/data-metric="(\w+)"/g)].map((match) => match[1]);

/**
 * Mount the shared app mocks, then swap in tree-aware nodes for the elements
 * the app updates in place, and queue animation frames so a test decides when
 * scheduled work runs.
 */
function setupLoanApp() {
  const { elementMap } = setupFullMocks();
  const restoreDom = installFakeDom();

  for (const id of ['tbody', 'ybody', 'tableSummary', 'extraList']) {
    elementMap[id] = new FakeNode('div');
  }
  const metrics = new FakeNode('div');
  const slots = {};
  for (const name of metricSlotNames) {
    slots[name] = new FakeNode('div');
    slots[name].setAttribute('data-metric', name);
    metrics.append(slots[name]);
  }
  elementMap.metrics = metrics;

  // The page ships with the schedule view and the yearly table hidden.
  elementMap.tableWrap.hidden = true;
  elementMap.yearlyTableWrap.hidden = true;

  const frames = [];
  globalThis.window.requestAnimationFrame = (callback) => {
    frames.push(callback);
    return frames.length;
  };
  const flushFrames = () => {
    for (const callback of frames.splice(0)) callback();
  };

  return {
    elementMap,
    slots,
    frames,
    flushFrames,
    restore() {
      restoreDom();
      cleanupMocks();
    }
  };
}

async function importLoanApp() {
  await import(`../../../../apps/loan-amortization/js/app.js?t=${Date.now()}-${Math.random()}`);
}

function extraInputEvent(summaryNode, field, value) {
  const row = { dataset: { extraId: '0' } };
  const input = {
    dataset: { field },
    value,
    closest(selector) {
      if (selector === '[data-extra-id]') return row;
      if (selector === '.extra-item') return { querySelector: () => summaryNode };
      return null;
    }
  };
  return {
    target: { closest: (selector) => (selector === 'input[data-field]' ? input : null) }
  };
}

test('loan amortization app.js loads and initializes without error', async () => {
  const { elementMap, restore } = setupLoanApp();
  try {
    await importLoanApp();

    assert.ok(
      globalThis.document.documentElement.dataset.runtimeStatus !== undefined,
      'runtime status should be set'
    );
    assert.ok(elementMap.inPrincipal.value !== '', 'principal input should be formatted');

    const sliderListeners = elementMap.slPrincipal._listeners;
    elementMap.slPrincipal.value = '150000';
    sliderListeners.input[0]();

    elementMap.selFreq.value = 'biweekly';
    elementMap.selFreq._listeners.change[0]();
    assert.equal(elementMap.bwTrue.disabled, false, 'bi-weekly enables its method toggle');

    elementMap.btnTable._listeners.click[0]();
    elementMap.btnAdd._listeners.click[0]();
    elementMap.bwTrue._listeners.click[0]();
    elementMap.bwAccel._listeners.click[0]();
    elementMap.btnPeriod._listeners.click[0]();
    elementMap.btnYearly._listeners.click[0]();
    elementMap.btnCharts._listeners.click[0]();

    const extraListListeners = elementMap.extraList._listeners;
    extraListListeners.click[0]({ target: { closest: () => null } });

    for (const [action, data] of [
      ['set-type', { type: 'onetime' }],
      ['remove-extra', {}],
      ['unknown-action', {}]
    ]) {
      extraListListeners.click[0]({
        target: {
          closest(selector) {
            if (selector !== 'button[data-action]') return null;
            return {
              dataset: { action, ...data },
              closest: (inner) => (inner === '[data-extra-id]' ? { dataset: { extraId: '0' } } : null)
            };
          }
        }
      });
    }
    // A button outside any extra row is ignored.
    extraListListeners.click[0]({
      target: {
        closest: () => ({ dataset: { action: 'remove-extra' }, closest: () => null })
      }
    });

    extraListListeners.input[0]({ target: { closest: () => null } });
    extraListListeners.input[0]({
      target: { closest: () => ({ dataset: { field: 'amount' }, closest: () => null }) }
    });

    elementMap.inPrincipal.value = '200000';
    elementMap.inPrincipal._listeners.change[0].call(elementMap.inPrincipal);
    elementMap.inRate.value = '5.5';
    elementMap.inRate._listeners.change[0].call(elementMap.inRate);
    elementMap.inTenure.value = '20';
    elementMap.inTenure._listeners.change[0].call(elementMap.inTenure);
  } finally {
    restore();
  }
});

test('loan app draws only the visible table and redraws a hidden one when it is shown', async () => {
  const { elementMap, flushFrames, restore } = setupLoanApp();
  try {
    await importLoanApp();
    // Charts view is open: no table work yet.
    assert.equal(elementMap.tbody.children.length, 0);
    assert.equal(elementMap.ybody.children.length, 0);

    elementMap.btnTable._listeners.click[0]();
    assert.equal(elementMap.tableSummary.children.length, 5);
    assert.equal(elementMap.tbody.children.length, 180, '15 years of monthly rows');
    assert.equal(elementMap.ybody.children.length, 0, 'the yearly table stays undrawn while hidden');

    elementMap.btnYearly._listeners.click[0]();
    assert.equal(elementMap.ybody.children.length, 15);

    // A tick while the yearly table is showing leaves the hidden period table alone.
    const periodRows = [...elementMap.tbody.children];
    elementMap.slTenure.value = '10';
    elementMap.slTenure._listeners.input[0]();
    flushFrames();
    assert.equal(elementMap.ybody.children.length, 10);
    assert.deepEqual(elementMap.tbody.children, periodRows, 'hidden table not rebuilt');

    // Showing it again brings it up to date.
    elementMap.btnPeriod._listeners.click[0]();
    assert.equal(elementMap.tbody.children.length, 120);
    assert.equal(elementMap.tbody.children[0], periodRows[0], 'rows are reused');
  } finally {
    restore();
  }
});

test('loan app schedules extra-field typing and keeps the EMI', async () => {
  const { elementMap, slots, frames, flushFrames, restore } = setupLoanApp();
  try {
    await importLoanApp();
    const emi = slots.heroValue.textContent;
    assert.match(emi, /^\$/);
    assert.equal(slots.chip.classList.contains('is-empty'), true, 'no extras, no savings chip');

    elementMap.btnAdd._listeners.click[0]();
    flushFrames();
    assert.equal(elementMap.extraList.children.length, 1);
    assert.equal(slots.chip.classList.contains('is-empty'), false, 'an extra payment saves interest');
    const chipText = slots.chip.textContent;

    const summaryNode = new FakeNode('div');
    const inputs = elementMap.extraList._listeners.input[0];
    inputs(extraInputEvent(summaryNode, 'amount', '1500'));
    inputs(extraInputEvent(summaryNode, 'amount', '2500'));
    inputs(extraInputEvent(summaryNode, 'amount', '3500'));

    // The summary line follows the keystroke; the calculation waits for one frame.
    assert.match(summaryNode.textContent, /\$3,500/);
    assert.equal(slots.chip.textContent, chipText);
    assert.equal(frames.length, 1, 'a burst of keystrokes schedules one recalculation');

    flushFrames();
    assert.notEqual(slots.chip.textContent, chipText);
    assert.equal(slots.heroValue.textContent, emi, 'extras never change the EMI');

    // Changing the loan terms drops the cached base schedule.
    elementMap.slPrincipal.value = '300000';
    elementMap.slPrincipal._listeners.input[0]();
    flushFrames();
    assert.notEqual(slots.heroValue.textContent, emi);
  } finally {
    restore();
  }
});
