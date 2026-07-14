import assert from 'node:assert/strict';
import test from 'node:test';

import {
  chartGlobal,
  createPaletteCache,
  cssAlpha,
  cssValue,
  isDark
} from '../../../js/modules/chart-theme.js';

function withDom({ theme = 'light', properties = {} } = {}, run) {
  const origDoc = globalThis.document;
  const origGcs = globalThis.getComputedStyle;
  globalThis.document = {
    body: {},
    documentElement: {
      getAttribute() { return theme; }
    }
  };
  globalThis.getComputedStyle = () => ({
    getPropertyValue(name) { return properties[name] ?? ' rgb(10, 20, 30) '; }
  });
  try {
    return run();
  } finally {
    if (origDoc) globalThis.document = origDoc; else delete globalThis.document;
    if (origGcs) globalThis.getComputedStyle = origGcs; else delete globalThis.getComputedStyle;
  }
}

test('chartGlobal returns the window object', () => {
  const origWin = globalThis.window;
  globalThis.window = { Chart: 'sentinel' };
  try {
    assert.equal(chartGlobal().Chart, 'sentinel');
  } finally {
    if (origWin) globalThis.window = origWin; else delete globalThis.window;
  }
});

test('cssValue trims the computed custom property', () => {
  withDom({}, () => {
    assert.equal(cssValue('--color-blue'), 'rgb(10, 20, 30)');
  });
});

test('cssAlpha rebuilds an rgb property at the requested alpha', () => {
  withDom({}, () => {
    assert.equal(cssAlpha('--note-blue', 0.5), 'rgba(10, 20, 30, 0.5)');
  });
});

test('cssAlpha falls back to the raw value without three numeric channels', () => {
  withDom({ properties: { '--note-blue': 'blue' } }, () => {
    assert.equal(cssAlpha('--note-blue', 0.5), 'blue');
  });
});

test('isDark reflects the documentElement theme attribute', () => {
  withDom({ theme: 'dark' }, () => assert.equal(isDark(), true));
  withDom({ theme: 'light' }, () => assert.equal(isDark(), false));
});

test('createPaletteCache builds once per theme and rebuilds on theme change', () => {
  let builds = 0;
  const { colors } = createPaletteCache(({ css }) => {
    builds += 1;
    return { blue: css('--color-blue') };
  });

  withDom({}, () => {
    assert.deepEqual(colors(), { blue: 'rgb(10, 20, 30)' });
    colors();
    assert.equal(builds, 1, 'same theme reuses the cached palette');
  });

  withDom({ theme: 'dark' }, () => {
    colors();
    assert.equal(builds, 2, 'theme change rebuilds the palette');
  });
});

test('refreshPalette drops the cache and rebuilds immediately', () => {
  let builds = 0;
  const { colors, refreshPalette } = createPaletteCache(({ cssAlpha: alpha }) => {
    builds += 1;
    return { blueA: alpha('--note-blue', 0.2) };
  });

  withDom({}, () => {
    colors();
    const palette = refreshPalette();
    assert.equal(builds, 2, 'refresh rebuilds even when the theme is unchanged');
    assert.equal(palette.blueA, 'rgba(10, 20, 30, 0.2)');
  });
});
