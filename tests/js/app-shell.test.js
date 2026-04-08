import test from 'node:test';
import assert from 'node:assert/strict';

import { renderAppShell, initAppShell } from '../../js/modules/app-shell.js';

function createSlot() {
  return {
    childElementCount: 0,
    innerHTML: ''
  };
}

function createMockEnv(overrides = {}) {
  const attrs = { 'data-theme': 'light' };
  const listeners = {};
  const elements = {};

  const html = {
    getAttribute(name) { return attrs[name] ?? null; },
    setAttribute(name, value) { attrs[name] = value; }
  };

  function makeElement(id) {
    const el = {
      id,
      _attrs: {},
      classList: {
        _classes: new Set(),
        toggle(cls, force) { force ? this._classes.add(cls) : this._classes.delete(cls); },
        contains(cls) { return this._classes.has(cls); }
      },
      tabIndex: -1,
      setAttribute(name, value) { this._attrs[name] = value; },
      getAttribute(name) { return this._attrs[name] ?? null; },
      addEventListener(event, handler) {
        listeners[`${id}:${event}`] = handler;
      }
    };
    return el;
  }

  elements['back-button'] = makeElement('back-button');
  elements['theme-toggle'] = makeElement('theme-toggle');
  elements['scroll-top'] = makeElement('scroll-top');

  const themeColorMeta = {
    _attrs: {},
    setAttribute(name, value) { this._attrs[name] = value; },
    getAttribute(name) { return this._attrs[name] ?? null; }
  };

  const shellSlots = {
    '[data-app-shell="header"]': createSlot(),
    '[data-app-shell="runtime-error"]': createSlot(),
    '[data-app-shell="scroll-top"]': createSlot()
  };

  const mockDocument = {
    documentElement: html,
    getElementById(id) { return elements[id] ?? null; },
    querySelector(sel) {
      if (sel === 'meta[name="theme-color"]') return themeColorMeta;
      return shellSlots[sel] ?? null;
    },
    referrer: ''
  };

  const mockWindow = {
    __ARTIFACTS_APP_THEME_BOOTSTRAP__: {
      normalizeTheme(t) { return t === 'dark' ? 'dark' : 'light'; }
    },
    matchMedia() { return { matches: false }; },
    scrollY: 0,
    scrollTo() {},
    history: { length: 2, back() {} },
    location: { origin: 'https://example.com', href: '' },
    addEventListener(event, handler, opts) {
      listeners[`window:${event}`] = handler;
    }
  };

  // Inject globals so initAppShell can use them
  globalThis.document = mockDocument;
  globalThis.window = mockWindow;
  globalThis.HTMLElement = globalThis.HTMLElement ?? class {};

  return { html, attrs, elements, listeners, themeColorMeta, mockDocument, mockWindow, ...overrides };
}

function cleanupGlobals() {
  delete globalThis.document;
  delete globalThis.window;
}

test('renderAppShell fills shared shell placeholders', () => {
  const slots = {
    '[data-app-shell="header"]': createSlot(),
    '[data-app-shell="runtime-error"]': createSlot(),
    '[data-app-shell="scroll-top"]': createSlot()
  };

  renderAppShell({
    documentObj: {
      querySelector(selector) {
        return slots[selector] ?? null;
      }
    },
    homePath: '../'
  });

  assert.match(slots['[data-app-shell="header"]'].innerHTML, /id="theme-toggle"/);
  assert.match(slots['[data-app-shell="header"]'].innerHTML, /href="\.\.\/"/);
  assert.match(slots['[data-app-shell="runtime-error"]'].innerHTML, /id="runtime-error"/);
  assert.match(slots['[data-app-shell="runtime-error"]'].innerHTML, /id="runtime-error-details"/);
  assert.match(slots['[data-app-shell="runtime-error"]'].innerHTML, /id="runtime-error-copy"/);
  assert.match(slots['[data-app-shell="scroll-top"]'].innerHTML, /id="scroll-top"/);
});

test('renderAppShell leaves populated placeholders unchanged', () => {
  const slot = {
    childElementCount: 1,
    innerHTML: '<p>Keep existing content</p>'
  };

  renderAppShell({
    documentObj: {
      querySelector(selector) {
        return selector === '[data-app-shell="header"]' ? slot : null;
      }
    }
  });

  assert.equal(slot.innerHTML, '<p>Keep existing content</p>');
});

test('initAppShell sets up theme toggle and syncs theme state', () => {
  const env = createMockEnv();
  try {
    const shell = initAppShell({ homePath: '../' });

    // Theme toggle click changes theme
    env.listeners['theme-toggle:click']();
    assert.equal(env.attrs['data-theme'], 'dark');
    assert.equal(env.elements['theme-toggle'].getAttribute('aria-pressed'), 'true');

    // Toggle again to switch back
    env.listeners['theme-toggle:click']();
    assert.equal(env.attrs['data-theme'], 'light');
    assert.equal(env.elements['theme-toggle'].getAttribute('aria-pressed'), 'false');
  } finally {
    cleanupGlobals();
  }
});

test('initAppShell applyTheme normalizes and persists', () => {
  const env = createMockEnv();
  try {
    const themeChanges = [];
    const shell = initAppShell({
      homePath: '../',
      onThemeChange: (t) => themeChanges.push(t)
    });

    shell.applyTheme('dark');
    assert.equal(env.attrs['data-theme'], 'dark');
    assert.equal(env.themeColorMeta.getAttribute('content'), 'rgb(20, 20, 20)');
    assert.deepEqual(themeChanges, ['dark']);

    shell.applyTheme('invalid');
    assert.equal(env.attrs['data-theme'], 'light');
    assert.equal(env.themeColorMeta.getAttribute('content'), 'rgb(248, 248, 246)');
  } finally {
    cleanupGlobals();
  }
});

test('initAppShell back button navigates home when no referrer', () => {
  const env = createMockEnv();
  try {
    initAppShell({ homePath: '../' });
    env.listeners['back-button:click']();
    assert.equal(globalThis.window.location.href, '../');
  } finally {
    cleanupGlobals();
  }
});

test('initAppShell back button uses history.back for same-origin referrer', () => {
  const env = createMockEnv();
  try {
    let backedUp = false;
    globalThis.document.referrer = 'https://example.com/page';
    globalThis.window.history.back = () => { backedUp = true; };
    initAppShell({ homePath: '../' });
    env.listeners['back-button:click']();
    assert.equal(backedUp, true);
  } finally {
    cleanupGlobals();
  }
});

test('initAppShell back button navigates home for cross-origin referrer', () => {
  const env = createMockEnv();
  try {
    globalThis.document.referrer = 'https://other-site.com/page';
    initAppShell({ homePath: '../' });
    env.listeners['back-button:click']();
    assert.equal(globalThis.window.location.href, '../');
  } finally {
    cleanupGlobals();
  }
});

test('initAppShell scroll-top toggles visibility based on scroll position', () => {
  const env = createMockEnv();
  try {
    const shell = initAppShell({ homePath: '../' });

    globalThis.window.scrollY = 300;
    shell.updateScrollTopVisibility();
    assert.equal(env.elements['scroll-top'].classList.contains('is-visible'), true);
    assert.equal(env.elements['scroll-top'].getAttribute('aria-hidden'), 'false');

    globalThis.window.scrollY = 100;
    shell.updateScrollTopVisibility();
    assert.equal(env.elements['scroll-top'].classList.contains('is-visible'), false);
    assert.equal(env.elements['scroll-top'].getAttribute('aria-hidden'), 'true');
  } finally {
    cleanupGlobals();
  }
});

test('initAppShell scroll-top click scrolls to top', () => {
  const env = createMockEnv();
  try {
    let scrollArgs = null;
    globalThis.window.scrollTo = (args) => { scrollArgs = args; };
    initAppShell({ homePath: '../' });
    env.listeners['scroll-top:click']();
    assert.deepEqual(scrollArgs, { top: 0, behavior: 'smooth' });
  } finally {
    cleanupGlobals();
  }
});

test('initAppShell handles missing theme-color meta gracefully', () => {
  const env = createMockEnv();
  try {
    const origQuerySelector = globalThis.document.querySelector.bind(globalThis.document);
    globalThis.document.querySelector = (sel) => {
      if (sel === 'meta[name="theme-color"]') return null;
      return origQuerySelector(sel);
    };
    // Should not throw
    const shell = initAppShell({ homePath: '../' });
    shell.applyTheme('dark');
    assert.equal(env.attrs['data-theme'], 'dark');
  } finally {
    cleanupGlobals();
  }
});
