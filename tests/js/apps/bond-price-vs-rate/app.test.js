import assert from 'node:assert/strict';
import test from 'node:test';

import { cleanupMocks, setupFullMocks } from '../../common/app-entry-test-support.js';

function fire(element, type, event) {
  const handlers = element._listeners[type];
  if (handlers) {
    for (const handler of handlers) {
      handler.call(element, event);
    }
  }
}

test('bond-price-vs-rate app.js boots the shared runtime without error', async () => {
  const { elementMap } = setupFullMocks();
  try {
    // Cache-bust the import so repeat runs re-evaluate the module.
    await import(`../../../../apps/bond-price-vs-rate/js/app.js?t=${Date.now()}-${Math.random()}`);

    assert.equal(
      globalThis.window.__ARTIFACT_READY__,
      true,
      'the Bond Price Vs Rate bootstrap should finish without a fatal error'
    );
    assert.equal(
      globalThis.document.documentElement.dataset.runtimeStatus,
      'ready',
      'the shared runtime should reach the ready state'
    );

    // Drive each slider through every price regime so the narrative and chart
    // paths all run: rate below the coupon (premium), rate at the coupon (par),
    // and rate above the coupon (discount).
    elementMap.slRate.value = '4';
    fire(elementMap.slRate, 'input');

    elementMap.slCoupon.value = '4';
    fire(elementMap.slCoupon, 'input');

    elementMap.slRate.value = '8';
    fire(elementMap.slRate, 'input');

    elementMap.slYears.value = '20';
    fire(elementMap.slYears, 'input');

    // Walk the yield-curve presets, then push the curve rate into the slider.
    fire(elementMap.btnCurveInverted, 'click');
    fire(elementMap.btnCurveFlat, 'click');
    fire(elementMap.btnCurveNormal, 'click');
    fire(elementMap.btnApplyCurve, 'click');
    assert.equal(
      elementMap.slRate.value,
      '5.3',
      'applying the normal curve at 20 years should round its ~5.29% rate to 5.3'
    );

    // Trigger the theme-change callback wired through the shell.
    const themeToggle = globalThis.document.getElementById('theme-toggle');
    fire(themeToggle, 'click');
  } finally {
    cleanupMocks();
  }
});
