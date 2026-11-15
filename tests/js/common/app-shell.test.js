import test from 'node:test';
import assert from 'node:assert/strict';

import { renderAppShell, initAppShell } from '../../../js/modules/app-shell.js';

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

  // Records whether the transition-suspending class was on when the theme
  // attribute changed, and queues animation frames for the tests to flush.
  const themeSwaps = [];
  const htmlClasses = new Set();
  const frames = new Map();
  let nextFrame = 1;

  const html = {
    getAttribute(name) { return attrs[name] ?? null; },
    setAttribute(name, value) {
      if (name === 'data-theme') themeSwaps.push(htmlClasses.has('theme-switching'));
      attrs[name] = value;
    },
    classList: {
      add(cls) { htmlClasses.add(cls); },
      remove(cls) { htmlClasses.delete(cls); },
      contains(cls) { return htmlClasses.has(cls); }
    }
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

  const mockDocument = {
    documentElement: html,
    getElementById(id) { return elements[id] ?? null; },
    querySelector(sel) {
      return sel === 'meta[name="theme-color"]' ? themeColorMeta : null;
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
    requestAnimationFrame(callback) {
      const id = nextFrame++;
      frames.set(id, callback);
      return id;
    },
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

  // Run the frame callbacks queued so far, as one animation frame would.
  const flushFrame = () => {
    const pending = [...frames.values()];
    frames.clear();
    pending.forEach((callback) => callback());
  };

  return {
    html, attrs, elements, listeners, themeColorMeta, mockDocument, mockWindow,
    htmlClasses, themeSwaps, flushFrame, ...overrides
  };
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
    }
  });

  assert.match(slots['[data-app-shell="header"]'].innerHTML, /id="theme-toggle"/);
  assert.match(slots['[data-app-shell="header"]'].innerHTML, /href="\.\.\/\.\.\/" class="brand-link"/);
  assert.match(slots['[data-app-shell="runtime-error"]'].innerHTML, /id="runtime-error"/);
  assert.match(slots['[data-app-shell="runtime-error"]'].innerHTML, /id="runtime-error-details"/);
  assert.match(slots['[data-app-shell="runtime-error"]'].innerHTML, /id="runtime-error-copy"/);
  // display:none keeps the idle failure text out of the accessibility tree;
  // visually-hidden would let a screen reader read it on a healthy page.
  assert.match(slots['[data-app-shell="runtime-error"]'].innerHTML, /class="runtime-error hidden"/);
  assert.match(slots['[data-app-shell="scroll-top"]'].innerHTML, /id="scroll-top"/);
});

test('initAppShell sets up theme toggle and syncs theme state', () => {
  const env = createMockEnv();
  try {
    const shell = initAppShell();

    env.listeners['theme-toggle:click']();
    assert.equal(env.attrs['data-theme'], 'dark');
    assert.equal(env.elements['theme-toggle'].getAttribute('aria-pressed'), 'true');

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
    initAppShell();
    env.listeners['back-button:click']();
    assert.equal(globalThis.window.location.href, '../../');
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
    initAppShell();
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
    initAppShell();
    env.listeners['back-button:click']();
    assert.equal(globalThis.window.location.href, '../../');
  } finally {
    cleanupGlobals();
  }
});

test('initAppShell scroll-top toggles visibility based on scroll position', () => {
  const env = createMockEnv();
  try {
    const shell = initAppShell();

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
    initAppShell();
    env.listeners['scroll-top:click']();
    assert.deepEqual(scrollArgs, { top: 0, behavior: 'smooth' });
  } finally {
    cleanupGlobals();
  }
});

test('initAppShell applyTheme suspends transitions around the theme change for two frames', () => {
  const env = createMockEnv();
  try {
    const shell = initAppShell();

    shell.applyTheme('dark');
    assert.deepEqual(env.themeSwaps, [true]);
    assert.equal(env.htmlClasses.has('theme-switching'), true);

    env.flushFrame();
    assert.equal(env.htmlClasses.has('theme-switching'), true);
    env.flushFrame();
    assert.equal(env.htmlClasses.has('theme-switching'), false);
    assert.equal(env.attrs['data-theme'], 'dark');
  } finally {
    cleanupGlobals();
  }
});

test('initAppShell applyTheme restarts the two-frame window on a rapid second toggle', () => {
  const env = createMockEnv();
  try {
    const shell = initAppShell();

    shell.applyTheme('dark');
    env.flushFrame();
    shell.applyTheme('light');
    env.flushFrame();
    assert.equal(env.htmlClasses.has('theme-switching'), true);
    env.flushFrame();
    assert.equal(env.htmlClasses.has('theme-switching'), false);
    assert.deepEqual(env.themeSwaps, [true, true]);
  } finally {
    cleanupGlobals();
  }
});

test('initAppShell scroll-top coalesces scroll events per frame and writes only on a change', () => {
  const env = createMockEnv();
  try {
    initAppShell();
    const button = env.elements['scroll-top'];
    let writes = 0;
    const setAttribute = button.setAttribute.bind(button);
    button.setAttribute = (name, value) => { writes += 1; setAttribute(name, value); };

    const onScroll = env.listeners['window:scroll'];
    globalThis.window.scrollY = 400;
    onScroll();
    onScroll();
    onScroll();
    assert.equal(button.classList.contains('is-visible'), false);
    env.flushFrame();
    assert.equal(button.classList.contains('is-visible'), true);
    assert.equal(writes, 1);

    globalThis.window.scrollY = 900;
    onScroll();
    env.flushFrame();
    assert.equal(writes, 1);

    globalThis.window.scrollY = 10;
    onScroll();
    env.flushFrame();
    assert.equal(button.classList.contains('is-visible'), false);
    assert.equal(writes, 2);
  } finally {
    cleanupGlobals();
  }
});
