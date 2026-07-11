import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const scriptPath = path.resolve('js/boot-guard.js');
const scriptSource = fs.readFileSync(scriptPath, 'utf-8');

function makeBanner(messageEl, { initialClasses = ['hidden'] } = {}) {
  const classes = new Set(initialClasses);
  return {
    classList: {
      remove(name) {
        classes.delete(name);
      },
      contains(name) {
        return classes.has(name);
      },
    },
    querySelector(selector) {
      return selector === 'p' ? messageEl : null;
    },
    _classes: classes,
  };
}

function runBootGuard({ runtimeStatus = 'booting', banner = true } = {}) {
  const timers = [];
  const documentElement = { dataset: { runtimeStatus } };
  const messageEl = { textContent: '' };
  const bannerEl = banner ? makeBanner(messageEl) : null;
  const documentObj = {
    documentElement,
    getElementById(id) {
      return id === 'runtime-error' ? bannerEl : null;
    },
  };
  const context = {
    document: documentObj,
    setTimeout(fn, ms) {
      timers.push({ fn, ms });
      return timers.length;
    },
  };
  context.window = context;
  context.globalThis = context;
  vm.runInNewContext(scriptSource, context);

  return { context, timers, bannerEl, messageEl, documentElement };
}

test('boot guard exposes its factory on the global object', () => {
  const { context } = runBootGuard();
  const guard = context.__ARTIFACTS_BOOT_GUARD__;
  assert.equal(typeof guard.checkBoot, 'function');
  assert.equal(typeof guard.isBooted, 'function');
  assert.equal(typeof guard.revealStartupError, 'function');
  assert.equal(typeof guard.scheduleGuard, 'function');
  assert.equal(guard.defaultTimeoutMs, 8000);
});

test('boot guard schedules a timeout on load', () => {
  const { timers } = runBootGuard();
  assert.equal(timers.length, 1);
  assert.equal(timers[0].ms, 8000);
});

test('scheduled guard reveals the error banner when the app never booted', () => {
  const { timers, bannerEl, messageEl, documentElement } = runBootGuard({ runtimeStatus: 'booting' });

  timers[0].fn();

  assert.equal(bannerEl._classes.has('hidden'), false);
  assert.equal(bannerEl._classes.has('visually-hidden'), false);
  assert.match(messageEl.textContent, /failed to start/);
  assert.equal(documentElement.dataset.runtimeStatus, 'error');
});

test('scheduled guard stands down when the app reported ready', () => {
  const { timers, bannerEl, messageEl } = runBootGuard({ runtimeStatus: 'ready' });

  const revealed = timers[0].fn();

  assert.equal(revealed, false);
  assert.equal(bannerEl._classes.has('hidden'), true);
  assert.equal(messageEl.textContent, '');
});

test('isBooted treats ready and error as booted, booting as not', () => {
  const { context } = runBootGuard();
  const { isBooted } = context.__ARTIFACTS_BOOT_GUARD__;
  assert.equal(isBooted({ documentElement: { dataset: { runtimeStatus: 'ready' } } }), true);
  assert.equal(isBooted({ documentElement: { dataset: { runtimeStatus: 'error' } } }), true);
  assert.equal(isBooted({ documentElement: { dataset: { runtimeStatus: 'booting' } } }), false);
  assert.equal(isBooted({}), false);
  assert.equal(isBooted(null), false);
});

test('readRuntimeStatus returns an empty string without a document element', () => {
  const { context } = runBootGuard();
  const { readRuntimeStatus } = context.__ARTIFACTS_BOOT_GUARD__;
  assert.equal(readRuntimeStatus(null), '');
  assert.equal(readRuntimeStatus({}), '');
});

test('checkBoot does nothing once the app is booted', () => {
  const { context } = runBootGuard({ runtimeStatus: 'ready' });
  const { checkBoot } = context.__ARTIFACTS_BOOT_GUARD__;
  const messageEl = { textContent: '' };
  const bannerEl = makeBanner(messageEl);
  const documentObj = {
    documentElement: { dataset: { runtimeStatus: 'ready' } },
    getElementById: () => bannerEl,
  };
  assert.equal(checkBoot(documentObj), false);
  assert.equal(bannerEl._classes.has('hidden'), true);
});

test('revealStartupError returns false when the banner is missing', () => {
  const { context } = runBootGuard({ banner: false });
  const { revealStartupError } = context.__ARTIFACTS_BOOT_GUARD__;
  const documentObj = {
    documentElement: { dataset: {} },
    getElementById: () => null,
  };
  assert.equal(revealStartupError(documentObj), false);
});

test('revealStartupError returns false without a usable document', () => {
  const { context } = runBootGuard();
  const { revealStartupError } = context.__ARTIFACTS_BOOT_GUARD__;
  assert.equal(revealStartupError(null), false);
  assert.equal(revealStartupError({}), false);
});

test('scheduleGuard returns null without a setTimeout capable target', () => {
  const { context } = runBootGuard();
  const { scheduleGuard } = context.__ARTIFACTS_BOOT_GUARD__;
  assert.equal(scheduleGuard(null), null);
  assert.equal(scheduleGuard({}), null);
});
