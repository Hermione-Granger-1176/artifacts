import test from 'node:test';
import assert from 'node:assert/strict';

import { createRuntime, readStorage, writeStorage } from '../../js/modules/runtime.js';

function createWindowStub() {
  const listeners = new Map();
  const storage = new Map();

  return {
    __ARTIFACTS_ERROR_HANDLERS_BOUND__: false,
    addEventListener(type, handler) {
      listeners.set(type, handler);
    },
    dispatch(type, payload) {
      listeners.get(type)?.(payload);
    },
    localStorage: {
      getItem(key) {
        return storage.has(key) ? storage.get(key) : null;
      },
      setItem(key, value) {
        storage.set(key, value);
      }
    }
  };
}

function createDocumentStub() {
  const runtimeErrorBanner = {
    className: 'runtime-error hidden',
    classList: {
      removed: false,
      remove(name) {
        this.removed = true;
        if (name === 'hidden' || name === 'visually-hidden') {
          runtimeErrorBanner.className = 'runtime-error';
        }
      }
    }
  };

  return {
    documentElement: {
      dataset: {}
    },
    getElementById(id) {
      return id === 'runtime-error' ? runtimeErrorBanner : null;
    },
    runtimeErrorBanner
  };
}

test('runtime reads and writes storage and tracks readiness', () => {
  const consoleObj = { error() {} };
  const runtime = createRuntime({
    consoleObj,
    documentObj: createDocumentStub(),
    windowObj: createWindowStub()
  });

  assert.equal(runtime.readStorage('theme', 'dark'), 'dark');
  assert.equal(runtime.writeStorage('theme', 'light'), true);
  assert.equal(runtime.readStorage('theme', 'dark'), 'light');
  runtime.markReady();
  assert.equal(runtime.state.ready, true);
});

test('runtime reports global errors', () => {
  const documentObj = createDocumentStub();
  const windowObj = createWindowStub();
  const runtime = createRuntime({ consoleObj: { error() {} }, documentObj, windowObj });

  runtime.setupGlobalErrorHandlers();
  windowObj.dispatch('error', { error: new Error('boom') });

  assert.equal(runtime.state.lastError.message, 'boom');
  assert.equal(documentObj.documentElement.dataset.runtimeStatus, 'error');
});

test('runtime reveals the error banner for fatal errors', () => {
  const documentObj = createDocumentStub();
  const windowObj = createWindowStub();
  const runtime = createRuntime({ consoleObj: { error() {} }, documentObj, windowObj });

  runtime.reportError(new Error('fatal boom'), 'gallery initialization', { fatal: true });

  assert.equal(documentObj.documentElement.dataset.runtimeStatus, 'error');
  assert.equal(documentObj.runtimeErrorBanner.classList.removed, true);
});

test('runtime falls back when storage access throws', () => {
  const errors = [];
  const windowObj = createWindowStub();
  windowObj.localStorage = {
    getItem() {
      throw new Error('read blocked');
    },
    setItem() {
      throw new Error('write blocked');
    }
  };
  const runtime = createRuntime({
    consoleObj: { error(message) { errors.push(message); } },
    documentObj: createDocumentStub(),
    windowObj
  });

  assert.equal(runtime.readStorage('theme', 'light'), 'light');
  assert.equal(runtime.writeStorage('theme', 'dark'), false);
  assert.equal(runtime.state.lastError.message, 'write blocked');
  assert.match(errors[0], /localStorage read/);
  assert.match(errors[1], /localStorage write/);
});

test('runtime setupGlobalErrorHandlers is idempotent and handles rejections', () => {
  const documentObj = createDocumentStub();
  const windowObj = createWindowStub();
  const runtime = createRuntime({ consoleObj: { error() {} }, documentObj, windowObj });

  runtime.setupGlobalErrorHandlers();
  runtime.setupGlobalErrorHandlers();
  windowObj.dispatch('unhandledrejection', { reason: { message: 'async boom' } });

  assert.equal(windowObj.__ARTIFACTS_ERROR_HANDLERS_BOUND__, true);
  assert.equal(runtime.state.lastError.message, 'async boom');
  assert.equal(documentObj.documentElement.dataset.runtimeStatus, 'error');
});

test('runtime treats post-ready global failures as non-fatal', () => {
  const documentObj = createDocumentStub();
  const windowObj = createWindowStub();
  const runtime = createRuntime({ consoleObj: { error() {} }, documentObj, windowObj });

  runtime.markReady();
  runtime.setupGlobalErrorHandlers();
  windowObj.dispatch('error', { error: new Error('after ready') });

  assert.equal(runtime.state.lastError.message, 'after ready');
  assert.equal(runtime.state.lastError.fatal, false);
  assert.equal(documentObj.documentElement.dataset.runtimeStatus, 'ready');
});

test('runtime suppresses expected bootstrap validation console noise', () => {
  const errors = [];
  const runtime = createRuntime({
    consoleObj: { error(message) { errors.push(message); } },
    documentObj: createDocumentStub(),
    windowObj: createWindowStub()
  });

  runtime.reportError(
    new Error('window.ARTIFACTS_DATA must be an array'),
    'gallery initialization',
    { fatal: true }
  );

  assert.deepEqual(errors, []);
});

test('standalone readStorage reads from window.localStorage', () => {
  const storage = new Map([['color', 'blue']]);
  const original = globalThis.window;
  globalThis.window = {
    localStorage: {
      getItem(key) { return storage.get(key) ?? null; }
    }
  };

  assert.equal(readStorage('color'), 'blue');
  assert.equal(readStorage('missing'), null);
  assert.equal(readStorage('missing', 'default'), 'default');

  globalThis.window = original;
});

test('standalone readStorage returns fallback when localStorage throws', () => {
  const original = globalThis.window;
  globalThis.window = {
    localStorage: {
      getItem() { throw new Error('blocked'); }
    }
  };

  assert.equal(readStorage('any', 'safe'), 'safe');

  globalThis.window = original;
});

test('standalone writeStorage writes to window.localStorage', () => {
  const storage = new Map();
  const original = globalThis.window;
  globalThis.window = {
    localStorage: {
      setItem(key, value) { storage.set(key, value); }
    }
  };

  assert.equal(writeStorage('color', 'red'), true);
  assert.equal(storage.get('color'), 'red');

  globalThis.window = original;
});

test('standalone writeStorage returns false when localStorage throws', () => {
  const original = globalThis.window;
  globalThis.window = {
    localStorage: {
      setItem() { throw new Error('quota exceeded'); }
    }
  };

  assert.equal(writeStorage('color', 'red'), false);

  globalThis.window = original;
});
