import test from 'node:test';
import assert from 'node:assert/strict';

import { bootstrapGallery } from '../../../js/modules/gallery/bootstrap.js';

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

function bootWithFakes({ initializeError = null, validateError = null } = {}) {
  const runtime = createRuntimeStub();
  const initializeCalls = [];
  const validateCalls = [];
  const windowObj = { sentinel: 'window' };

  const returned = bootstrapGallery({
    createRuntime: () => runtime,
    initializeGalleryApp(args) {
      if (initializeError) {
        throw initializeError;
      }
      initializeCalls.push(args);
    },
    validateGalleryBootstrapData(target) {
      if (validateError) {
        throw validateError;
      }
      validateCalls.push(target);
    },
    windowObj
  });

  return { initializeCalls, returned, runtime, validateCalls, windowObj };
}

test.afterEach(() => {
  delete globalThis.document;
  delete globalThis.window;
});

test('bootstrapGallery validates, initializes, and marks the runtime ready', () => {
  const harness = bootWithFakes();

  assert.equal(harness.returned, harness.runtime);
  assert.equal(harness.runtime.setupGlobalErrorHandlersCalls, 1);
  assert.deepEqual(harness.validateCalls, [harness.windowObj]);
  assert.deepEqual(harness.initializeCalls, [{ runtime: harness.runtime }]);
  assert.equal(harness.runtime.markReadyCalls, 1);
  assert.deepEqual(harness.runtime.reportErrorCalls, []);
});

test('bootstrapGallery reports an initialization error once as fatal without rethrowing', () => {
  const boom = new Error('boom');
  const harness = bootWithFakes({ initializeError: boom });

  assert.equal(harness.runtime.setupGlobalErrorHandlersCalls, 1);
  assert.equal(harness.runtime.markReadyCalls, 0);
  assert.deepEqual(harness.runtime.reportErrorCalls, [
    { error: boom, context: 'gallery initialization', options: { fatal: true } }
  ]);
});

test('bootstrapGallery reports validation errors before initialization', () => {
  const boom = new Error('invalid bootstrap');
  const harness = bootWithFakes({ validateError: boom });

  assert.deepEqual(harness.initializeCalls, []);
  assert.equal(harness.runtime.markReadyCalls, 0);
  assert.deepEqual(harness.runtime.reportErrorCalls, [
    { error: boom, context: 'gallery initialization', options: { fatal: true } }
  ]);
});

test('app boots the real modules on DOMContentLoaded and records a fatal error once', async (t) => {
  const listeners = new Map();
  const windowListeners = new Map();
  globalThis.window = {
    addEventListener(type, handler) {
      windowListeners.set(type, handler);
    }
  };
  globalThis.document = {
    addEventListener(type, handler) {
      listeners.set(type, handler);
    },
    getElementById: () => null,
    documentElement: { dataset: {} }
  };
  const logged = t.mock.method(console, 'error', () => {});

  await import(`../../../js/app.js?test=${Date.now()}`);
  assert.equal(typeof listeners.get('DOMContentLoaded'), 'function');

  // The stub window has no generated globals, so the real validator rejects it.
  listeners.get('DOMContentLoaded')();

  const state = globalThis.window.__ARTIFACTS_RUNTIME__;
  assert.equal(state.ready, false);
  assert.equal(state.lastError.context, 'gallery initialization');
  assert.equal(state.lastError.fatal, true);
  assert.match(state.lastError.message, /ARTIFACTS_CONFIG must be an object/);
  assert.equal(globalThis.document.documentElement.dataset.runtimeStatus, 'error');
  assert.equal(logged.mock.callCount(), 1);
  assert.equal(typeof windowListeners.get('error'), 'function');
});
