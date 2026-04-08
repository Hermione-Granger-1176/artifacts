import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const scriptPath = path.resolve('js/app-theme.js');
const scriptSource = fs.readFileSync(scriptPath, 'utf-8');

function runThemeBootstrap({ getItem = () => null, documentElement = { dataset: {} } } = {}) {
  const context = {
    document: { documentElement },
    localStorage: { getItem },
  };
  context.globalThis = context;
  vm.runInNewContext(scriptSource, context);
  return context;
}

test('app theme bootstrap applies a stored dark theme', () => {
  const context = runThemeBootstrap({ getItem: () => 'dark' });

  assert.equal(context.document.documentElement.dataset.theme, 'dark');
  assert.equal(context.__ARTIFACTS_APP_THEME_BOOTSTRAP__.storageKey, 'theme');
});

test('app theme bootstrap falls back to light for invalid values', () => {
  const context = runThemeBootstrap({ getItem: () => 'sepia' });

  assert.equal(context.document.documentElement.dataset.theme, 'light');
});

test('app theme bootstrap falls back to light when storage access fails', () => {
  const context = runThemeBootstrap({
    getItem() {
      throw new Error('denied');
    },
  });

  assert.equal(context.document.documentElement.dataset.theme, 'light');
});

test('normalizeTheme is exposed on the bootstrap object', () => {
  const context = runThemeBootstrap();
  assert.equal(typeof context.__ARTIFACTS_APP_THEME_BOOTSTRAP__.normalizeTheme, 'function');
});

test('normalizeTheme returns "dark" for "dark"', () => {
  const { __ARTIFACTS_APP_THEME_BOOTSTRAP__: bootstrap } = runThemeBootstrap();
  assert.equal(bootstrap.normalizeTheme('dark'), 'dark');
});

test('normalizeTheme returns "light" for "light"', () => {
  const { __ARTIFACTS_APP_THEME_BOOTSTRAP__: bootstrap } = runThemeBootstrap();
  assert.equal(bootstrap.normalizeTheme('light'), 'light');
});

test('normalizeTheme returns "light" for null', () => {
  const { __ARTIFACTS_APP_THEME_BOOTSTRAP__: bootstrap } = runThemeBootstrap();
  assert.equal(bootstrap.normalizeTheme(null), 'light');
});

test('normalizeTheme returns "light" for undefined', () => {
  const { __ARTIFACTS_APP_THEME_BOOTSTRAP__: bootstrap } = runThemeBootstrap();
  assert.equal(bootstrap.normalizeTheme(undefined), 'light');
});

test('normalizeTheme returns "light" for empty string', () => {
  const { __ARTIFACTS_APP_THEME_BOOTSTRAP__: bootstrap } = runThemeBootstrap();
  assert.equal(bootstrap.normalizeTheme(''), 'light');
});

test('normalizeTheme returns "light" for "DARK" (case-sensitive)', () => {
  const { __ARTIFACTS_APP_THEME_BOOTSTRAP__: bootstrap } = runThemeBootstrap();
  assert.equal(bootstrap.normalizeTheme('DARK'), 'light');
});

test('normalizeTheme returns "light" for "invalid"', () => {
  const { __ARTIFACTS_APP_THEME_BOOTSTRAP__: bootstrap } = runThemeBootstrap();
  assert.equal(bootstrap.normalizeTheme('invalid'), 'light');
});
