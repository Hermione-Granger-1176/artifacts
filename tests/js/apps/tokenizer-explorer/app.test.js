import assert from 'node:assert/strict';
import test from 'node:test';

import { cleanupMocks, setupFullMocks } from '../../common/app-entry-test-support.js';

test('tokenizer explorer app.js loads and initializes without error', async () => {
  const { elementMap } = setupFullMocks();
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
  } finally {
    cleanupMocks();
  }
});
