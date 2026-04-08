import assert from 'node:assert/strict';
import test from 'node:test';

import { cleanupMocks, setupFullMocks } from '../../common/app-entry-test-support.js';

test('loan amortization app.js loads and initializes without error', async () => {
  const { elementMap } = setupFullMocks();
  try {
    await import(`../../../../apps/loan-amortization/js/app.js?t=${Date.now()}-${Math.random()}`);

    assert.ok(
      globalThis.document.documentElement.dataset.runtimeStatus !== undefined,
      'runtime status should be set'
    );
    assert.ok(elementMap.inPrincipal.value !== '', 'principal input should be formatted');

    const sliderListeners = elementMap.slPrincipal._listeners;
    if (sliderListeners.input) {
      elementMap.slPrincipal.value = '150000';
      sliderListeners.input[0]();
    }

    const freqListeners = elementMap.selFreq._listeners;
    if (freqListeners.change) {
      elementMap.selFreq.value = 'biweekly';
      freqListeners.change[0]();
    }

    const btnTableListeners = elementMap.btnTable._listeners;
    if (btnTableListeners.click) {
      btnTableListeners.click[0]();
    }

    const btnAddListeners = elementMap.btnAdd._listeners;
    if (btnAddListeners.click) {
      btnAddListeners.click[0]();
    }

    const bwTrueListeners = elementMap.bwTrue._listeners;
    if (bwTrueListeners.click) {
      bwTrueListeners.click[0]();
    }

    const bwAccelListeners = elementMap.bwAccel._listeners;
    if (bwAccelListeners.click) {
      bwAccelListeners.click[0]();
    }

    const btnPeriodListeners = elementMap.btnPeriod._listeners;
    if (btnPeriodListeners.click) {
      btnPeriodListeners.click[0]();
    }
    const btnYearlyListeners = elementMap.btnYearly._listeners;
    if (btnYearlyListeners.click) {
      btnYearlyListeners.click[0]();
    }

    const btnChartsListeners = elementMap.btnCharts._listeners;
    if (btnChartsListeners.click) {
      btnChartsListeners.click[0]();
    }

    const extraListClickListeners = elementMap.extraList._listeners;
    if (extraListClickListeners.click) {
      extraListClickListeners.click[0]({
        target: { closest() { return null; } }
      });

      extraListClickListeners.click[0]({
        target: {
          closest(sel) {
            if (sel === 'button[data-action]') {
              return {
                dataset: { action: 'set-type', type: 'onetime' },
                closest(s) {
                  if (s === '[data-extra-id]') return { dataset: { extraId: '0' } };
                  return null;
                }
              };
            }
            return null;
          }
        }
      });

      extraListClickListeners.click[0]({
        target: {
          closest(sel) {
            if (sel === 'button[data-action]') {
              return {
                dataset: { action: 'remove-extra' },
                closest(s) {
                  if (s === '[data-extra-id]') return { dataset: { extraId: '0' } };
                  return null;
                }
              };
            }
            return null;
          }
        }
      });
    }

    const extraListInputListeners = elementMap.extraList._listeners;
    if (extraListInputListeners.input) {
      extraListInputListeners.input[0]({
        target: { closest() { return null; } }
      });
    }

    const inPrincipalListeners = elementMap.inPrincipal._listeners;
    if (inPrincipalListeners.change) {
      elementMap.inPrincipal.value = '200000';
      inPrincipalListeners.change[0].call(elementMap.inPrincipal);
    }

    const inRateListeners = elementMap.inRate._listeners;
    if (inRateListeners.change) {
      elementMap.inRate.value = '5.5';
      inRateListeners.change[0].call(elementMap.inRate);
    }

    const inTenureListeners = elementMap.inTenure._listeners;
    if (inTenureListeners.change) {
      elementMap.inTenure.value = '20';
      inTenureListeners.change[0].call(elementMap.inTenure);
    }
  } finally {
    cleanupMocks();
  }
});
