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

    assert.equal(
      elementMap.rateValue.classList.contains('is-nudged'),
      true,
      'applying the curve rate should flash the market-rate readout'
    );

    // Trigger the theme-change callback wired through the shell.
    const themeToggle = globalThis.document.getElementById('theme-toggle');
    fire(themeToggle, 'click');
  } finally {
    cleanupMocks();
  }
});

test('bond-price-vs-rate redraws only the charts whose inputs changed', async () => {
  const { elementMap } = setupFullMocks();
  try {
    const updates = [];
    // Queue frames instead of running them inline, the way a browser coalesces input.
    const frames = [];
    globalThis.window.requestAnimationFrame = (callback) => frames.push(callback);
    const input = (element) => {
      fire(element, 'input');
      frames.splice(0).forEach((callback) => callback());
    };
    globalThis.window.Chart = function RecordingChart(canvas, config) {
      this.data = config.data;
      this.options = config.options;
      this.update = (mode) => updates.push({ canvas, mode });
    };
    await import(`../../../../apps/bond-price-vs-rate/js/app.js?t=${Date.now()}-${Math.random()}`);

    const drawn = () => {
      const names = updates.map(({ canvas }) => canvas.id);
      updates.length = 0;
      return names.sort();
    };
    const all = ['priceRateChart', 'sensitivityChart', 'yieldCurveChart'];
    assert.deepEqual(drawn(), all, 'the first render draws every chart');

    // The rate and the coupon move the price curve and the sensitivity bars only.
    elementMap.slRate.value = '7';
    input(elementMap.slRate);
    assert.deepEqual(drawn(), ['priceRateChart', 'sensitivityChart']);
    elementMap.slCoupon.value = '4';
    input(elementMap.slCoupon);
    assert.deepEqual(drawn(), ['priceRateChart', 'sensitivityChart']);

    // The maturity moves all three.
    elementMap.slYears.value = '12';
    input(elementMap.slYears);
    assert.deepEqual(drawn(), all);

    // The curve shape redraws the yield curve alone, and it is the one change that eases.
    fire(elementMap.btnCurveInverted, 'click');
    frames.splice(0).forEach((callback) => callback());
    assert.deepEqual(updates.map(({ canvas, mode }) => [canvas.id, mode]), [['yieldCurveChart', undefined]]);
    drawn();

    // A slider tick that changes nothing redraws nothing.
    input(elementMap.slRate);
    assert.deepEqual(drawn(), []);

    // A theme change repaints every chart, without animation.
    fire(globalThis.document.getElementById('theme-toggle'), 'click');
    assert.deepEqual(updates.map(({ mode }) => mode), ['none', 'none', 'none']);
    assert.deepEqual(drawn(), all);
  } finally {
    cleanupMocks();
  }
});
