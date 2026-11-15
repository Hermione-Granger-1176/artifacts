import test from 'node:test';
import assert from 'node:assert/strict';

import { initializeMatureApp } from '../../../js/modules/app-runtime.js';

function createHarness() {
  const windowListeners = new Map();
  const windowObj = {
    __ARTIFACT_READY__: undefined,
    addEventListener(type, handler) {
      windowListeners.set(type, handler);
    },
    localStorage: {
      getItem() {
        return null;
      },
      setItem() {}
    }
  };
  const consoleMessages = [];
  const runtimeErrorBanner = {
    className: 'runtime-error hidden',
    classList: {
      remove(name) {
        if (name === 'hidden') {
          runtimeErrorBanner.className = 'runtime-error';
        }
      }
    }
  };
  const documentObj = {
    documentElement: { dataset: {} },
    addEventListener() {},
    getElementById(id) {
      return id === 'runtime-error' ? runtimeErrorBanner : null;
    }
  };

  return {
    documentObj,
    consoleMessages,
    windowListeners,
    runtimeErrorBanner,
    windowObj
  };
}

test('initializeMatureApp runs the app at once and marks ready after successful startup', () => {
  const harness = createHarness();
  let runCalls = 0;

  const runtime = initializeMatureApp({
    runtimeOptions: {
      consoleObj: { error(message) { harness.consoleMessages.push(message); } }
    },
    documentObj: harness.documentObj,
    run() {
      runCalls += 1;
    },
    windowObj: harness.windowObj
  });

  assert.equal(runCalls, 1);
  assert.equal(harness.windowObj.__ARTIFACT_READY__, true);
  assert.equal(runtime.state.ready, true);
  assert.equal(harness.documentObj.documentElement.dataset.runtimeStatus, 'ready');
});

test('initializeMatureApp reports a fatal startup failure once without rethrowing', () => {
  const harness = createHarness();
  const boom = new Error('startup failed');

  const runtime = initializeMatureApp({
    documentObj: harness.documentObj,
    onErrorContext: 'tokenizer explorer initialization',
    runtimeOptions: {
      consoleObj: { error(message) { harness.consoleMessages.push(message); } }
    },
    run() {
      throw boom;
    },
    windowObj: harness.windowObj
  });

  assert.equal(harness.windowObj.__ARTIFACT_READY__, false);
  assert.equal(runtime.state.ready, false);
  assert.equal(runtime.state.lastError?.context, 'tokenizer explorer initialization');
  assert.equal(runtime.state.lastError?.fatal, true);
  assert.equal(harness.documentObj.documentElement.dataset.runtimeStatus, 'error');
  assert.equal(harness.runtimeErrorBanner.className, 'runtime-error');
  assert.equal(harness.consoleMessages.length, 1);
  assert.match(harness.consoleMessages[0], /tokenizer explorer initialization/);
  assert.equal(typeof harness.windowListeners.get('error'), 'function');
});
