import assert from 'node:assert/strict';
import test from 'node:test';

import { cleanupMocks, setupFullMocks } from '../../common/app-entry-test-support.js';

test('tokenizer explorer app.js loads and initializes without error', async () => {
  const { elementMap } = setupFullMocks();
  const originalSetTimeout = globalThis.setTimeout;
  const originalClearTimeout = globalThis.clearTimeout;
  let timeoutCallback = null;
  let clearedTimeouts = 0;
  globalThis.setTimeout = (callback) => {
    timeoutCallback = callback;
    return 1;
  };
  globalThis.clearTimeout = () => {
    clearedTimeouts += 1;
  };
  try {
    await import(`../../../../apps/tokenizer-explorer/js/app.js?t=${Date.now()}-${Math.random()}`);

    assert.ok(
      globalThis.document.documentElement.dataset.runtimeStatus !== undefined,
      'runtime status should be set'
    );

    const tempInput = elementMap['temp-slider']._listeners.input[0];
    for (const value of ['0', '2', '15', '20']) {
      elementMap['temp-slider'].value = value;
      tempInput();
    }

    elementMap['topp-slider'].value = '50';
    elementMap['topp-slider']._listeners.input[0]();

    const presetClick = elementMap['sampling-presets']._listeners.click[0];
    presetClick({ target: { closest: () => null } });
    presetClick({
      target: {
        closest: () => ({ getAttribute: () => null })
      }
    });
    presetClick({
      target: {
        closest: () => ({
          getAttribute: (name) => name === 'data-temperature' ? '0.3' : '0.5'
        })
      }
    });

    const tabButtons = elementMap.tabs.children;
    tabButtons[1]._listeners.click[0]();

    const pickToken = elementMap['pick-token']._listeners.click[0];
    pickToken();
    pickToken();
    assert.equal(clearedTimeouts, 1);
    timeoutCallback();

    pickToken();
    elementMap['sample-hundred']._listeners.click[0]();
    assert.equal(clearedTimeouts, 2);
    elementMap['reset-samples']._listeners.click[0]();

    const whitespaceClick = elementMap['whitespace-toggle']._listeners.click[0];
    whitespaceClick();
    assert.equal(elementMap['whitespace-toggle'].textContent, 'Hide whitespace');
    whitespaceClick();
    assert.equal(elementMap['whitespace-toggle'].textContent, 'Show whitespace');

    elementMap['theme-toggle']._listeners.click[0]();
  } finally {
    globalThis.setTimeout = originalSetTimeout;
    globalThis.clearTimeout = originalClearTimeout;
    cleanupMocks();
  }
});
