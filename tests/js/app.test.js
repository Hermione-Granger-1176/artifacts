import test from 'node:test';
import assert from 'node:assert/strict';

function createRuntimeStub() {
  return {
    markReadyCalls: 0,
    reportErrorCalls: [],
    setupGlobalErrorHandlersCalls: 0,
    markReady() {
      this.markReadyCalls += 1;
    },
    reportError(error, context, options) {
      this.reportErrorCalls.push({ error, context, options });
    },
    setupGlobalErrorHandlers() {
      this.setupGlobalErrorHandlersCalls += 1;
    }
  };
}

function createBootstrapHarness({ initializeError = null, validateError = null } = {}) {
  const listeners = new Map();
  const runtime = createRuntimeStub();
  const initializeCalls = [];
  const validateCalls = [];

  globalThis.window = { sentinel: 'window' };
  globalThis.document = {
    addEventListener(type, handler) {
      listeners.set(type, handler);
    }
  };
  globalThis.__APP_TEST_HOOKS__ = {
    createRuntime: () => runtime,
    initializeGalleryApp(args) {
      if (initializeError) {
        throw initializeError;
      }
      initializeCalls.push(args);
    },
    validateGalleryBootstrapData(windowObj) {
      if (validateError) {
        throw validateError;
      }
      validateCalls.push(windowObj);
    }
  };

  return {
    getHandler() {
      return listeners.get('DOMContentLoaded');
    },
    initializeCalls,
    runtime,
    validateCalls
  };
}

async function importAppModule() {
  return import(`../../js/app.js?test=${Date.now()}-${Math.random()}`);
}

test.afterEach(() => {
  delete globalThis.__APP_TEST_HOOKS__;
  delete globalThis.document;
  delete globalThis.window;
});

test('app registers a DOMContentLoaded bootstrap handler on import', async () => {
  const harness = createBootstrapHarness();

  await importAppModule();

  assert.equal(typeof harness.getHandler(), 'function');
});

test('app bootstraps gallery successfully on DOMContentLoaded', async () => {
  const harness = createBootstrapHarness();

  await importAppModule();
  harness.getHandler()();

  assert.equal(harness.runtime.setupGlobalErrorHandlersCalls, 1);
  assert.deepEqual(harness.validateCalls, [globalThis.window]);
  assert.deepEqual(harness.initializeCalls, [{ runtime: harness.runtime }]);
  assert.equal(harness.runtime.markReadyCalls, 1);
  assert.deepEqual(harness.runtime.reportErrorCalls, []);
});

test('app reports fatal bootstrap errors and rethrows them', async () => {
  const boom = new Error('boom');
  const harness = createBootstrapHarness({ initializeError: boom });

  await importAppModule();

  assert.throws(() => harness.getHandler()(), /boom/);
  assert.equal(harness.runtime.setupGlobalErrorHandlersCalls, 1);
  assert.equal(harness.runtime.markReadyCalls, 0);
  assert.equal(harness.runtime.reportErrorCalls.length, 1);
  assert.deepEqual(harness.runtime.reportErrorCalls[0], {
    error: boom,
    context: 'gallery initialization',
    options: { fatal: true }
  });
});

test('app reports validation errors before initialization', async () => {
  const boom = new Error('invalid bootstrap');
  const harness = createBootstrapHarness({ validateError: boom });

  await importAppModule();

  assert.throws(() => harness.getHandler()(), /invalid bootstrap/);
  assert.deepEqual(harness.initializeCalls, []);
  assert.equal(harness.runtime.markReadyCalls, 0);
  assert.equal(harness.runtime.reportErrorCalls.length, 1);
  assert.deepEqual(harness.runtime.reportErrorCalls[0], {
    error: boom,
    context: 'gallery initialization',
    options: { fatal: true }
  });
});
