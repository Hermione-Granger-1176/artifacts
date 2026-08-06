import assert from 'node:assert/strict';
import test from 'node:test';

import { cleanupMocks, setupFullMocks } from '../../common/app-entry-test-support.js';

test('tokenizer explorer app.js loads and initializes without error', async () => {
  const { elementMap } = setupFullMocks();
  const originalSetTimeout = globalThis.setTimeout;
  const originalClearTimeout = globalThis.clearTimeout;
  const scheduled = [];
  globalThis.setTimeout = (callback) => {
    scheduled.push(callback);
    return scheduled.length;
  };
  globalThis.clearTimeout = () => {};
  try {
    await import(`../../../../apps/tokenizer-explorer/js/app.js?t=${Date.now()}-${Math.random()}`);

    assert.ok(
      globalThis.document.documentElement.dataset.runtimeStatus !== undefined,
      'runtime status should be set'
    );

    const tempListeners = elementMap['temp-slider']._listeners;
    if (tempListeners.input) {
      elementMap['temp-slider'].value = '15';
      tempListeners.input[0]();
    }

    const toppListeners = elementMap['topp-slider']._listeners;
    if (toppListeners.input) {
      elementMap['topp-slider'].value = '50';
      toppListeners.input[0]();
    }

    const tabButtons = elementMap.tabs.children;
    if (tabButtons.length > 1) {
      const secondTab = tabButtons[1];
      if (secondTab._listeners && secondTab._listeners.click) {
        secondTab._listeners.click[0]();
      }
    }

    const presetHandler = elementMap['sampling-presets']._listeners.click[0];
    presetHandler({ target: { closest() { return null; } } });
    presetHandler({
      target: {
        closest() {
          return {
            getAttribute(name) {
              return name === 'data-temperature' ? '0.2' : null;
            }
          };
        }
      }
    });
    const preset = {
      getAttribute(name) {
        return name === 'data-temperature' ? '0.7' : '0.9';
      }
    };
    presetHandler({
      target: {
        closest(selector) {
          return selector === '.sampling-preset' ? preset : null;
        }
      }
    });
    assert.equal(elementMap['temp-slider'].value, '7');
    assert.equal(elementMap['topp-slider'].value, '90');

    const setTemperature = (value) => {
      elementMap['temp-slider'].value = value;
      elementMap['temp-slider']._listeners.input[0]();
    };
    setTemperature('0');
    setTemperature('3');
    setTemperature('20');
    setTemperature('10');

    elementMap['pick-token']._listeners.click[0]();
    elementMap['sample-hundred']._listeners.click[0]();
    elementMap['pick-token']._listeners.click[0]();
    elementMap['pick-token']._listeners.click[0]();
    for (const callback of scheduled) {
      callback();
    }
    elementMap['reset-samples']._listeners.click[0]();

    elementMap['whitespace-toggle']._listeners.click[0]();
    elementMap['whitespace-toggle']._listeners.click[0]();
    assert.equal(elementMap['whitespace-toggle'].getAttribute('aria-pressed'), 'false');

    const themeToggle = elementMap['theme-toggle']._listeners.click;
    if (themeToggle) {
      themeToggle[0]();
    }
  } finally {
    globalThis.setTimeout = originalSetTimeout;
    globalThis.clearTimeout = originalClearTimeout;
    cleanupMocks();
  }
});
