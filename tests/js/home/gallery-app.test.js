import test from 'node:test';
import assert from 'node:assert/strict';

// CSS.escape is a browser API not available in Node.js
globalThis.CSS = globalThis.CSS || {};
globalThis.CSS.escape = globalThis.CSS.escape || ((v) => String(v).replace(/([^\w-])/g, '\\$1'));

import { initializeGalleryApp } from '../../../js/modules/gallery/gallery-app.js';
import {
  buildGalleryUrl,
  readGalleryStateFromSearch
} from '../../../js/modules/gallery/gallery-url.js';

class FakeClassList {
  constructor(initial = []) {
    this.values = new Set(initial);
  }

  add(...names) {
    names.forEach((name) => this.values.add(name));
  }

  remove(...names) {
    names.forEach((name) => this.values.delete(name));
  }

  toggle(name, force) {
    if (force === undefined) {
      if (this.values.has(name)) {
        this.values.delete(name);
        return false;
      }
      this.values.add(name);
      return true;
    }

    if (force) {
      this.values.add(name);
    } else {
      this.values.delete(name);
    }
    return force;
  }

  contains(name) {
    return this.values.has(name);
  }
}

class FakeElement {
  constructor({ id = '', tagName = 'DIV', classes = [] } = {}) {
    this.id = id;
    this.tagName = tagName;
    this.classList = new FakeClassList(classes);
    this.dataset = {};
    this.attributes = {};
    this.listeners = new Map();
    this.parentElement = null;
    this.ownerDocument = null;
    this.value = '';
    this.textContent = '';
    this.disabled = false;
    this.isContentEditable = false;
    this.inert = false;
    this.style = {
      properties: {},
      getPropertyValue(name) {
        return this.properties[name] || '';
      },
      removeProperty(name) {
        delete this.properties[name];
      },
      setProperty(name, value) {
        this.properties[name] = value;
      }
    };
    this._innerHTML = '';
  }

  set innerHTML(value) {
    this._innerHTML = value;
  }

  get innerHTML() {
    return this._innerHTML;
  }

  addEventListener(type, handler) {
    const handlers = this.listeners.get(type) || [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  dispatch(type, overrides = {}) {
    const event = {
      currentTarget: this,
      defaultPrevented: false,
      propagationStopped: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      stopPropagation() {
        this.propagationStopped = true;
      },
      target: this,
      ...overrides
    };

    for (const handler of this.listeners.get(type) || []) {
      handler(event);
    }

    return event;
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  getAttribute(name) {
    return Object.hasOwn(this.attributes, name) ? this.attributes[name] : null;
  }

  removeAttribute(name) {
    delete this.attributes[name];
  }

  hasAttribute(name) {
    return Object.hasOwn(this.attributes, name);
  }

  focus() {
    if (this.ownerDocument) {
      this.ownerDocument.activeElement = this;
    }
  }

  contains(target) {
    for (let node = target; node; node = node.parentElement) {
      if (node === this) {
        return true;
      }
    }

    return false;
  }

  matches(selector) {
    switch (selector) {
      case '[data-close-detail]':
        return this.hasAttribute('data-close-detail');
      case '[data-page]':
        return Object.hasOwn(this.dataset, 'page');
      default:
        if (selector.startsWith('#')) {
          return this.id === selector.slice(1);
        }

        if (selector.startsWith('.')) {
          return this.classList.contains(selector.slice(1));
        }

        return false;
    }
  }

  closest(selector) {
    for (let node = this; node; node = node.parentElement) {
      if (node.matches(selector)) {
        return node;
      }
    }

    return null;
  }

  querySelector() {
    return null;
  }

  querySelectorAll() {
    return [];
  }

  getBoundingClientRect() {
    return { left: 100, top: 100, width: 320, height: 180 };
  }
}

class FakeCard extends FakeElement {
  constructor(id, classes, expanded) {
    super({ tagName: 'BUTTON', classes });
    this.dataset.id = id;
    this.setAttribute('aria-expanded', String(expanded));
    this.setAttribute('type', 'button');
  }

  matches(selector) {
    switch (selector) {
      case '.artifact-card':
        return true;
      default:
        if (selector.startsWith('.artifact-card[data-id=')) {
          const match = selector.match(/data-id="([^"]+)"/);
          return this.dataset.id === match?.[1];
        }

        return super.matches(selector);
    }
  }

  getBoundingClientRect() {
    const numericId = Number.parseInt(this.dataset.id.split('-').at(-1), 10) || 1;
    return { left: 40 + numericId, top: 80 + numericId, width: 260, height: 180 };
  }
}

class FakeGrid extends FakeElement {
  constructor() {
    super({ id: 'artifacts-grid' });
    this.cards = [];
  }

  get innerHTML() {
    return this._innerHTML;
  }

  set innerHTML(value) {
    this._innerHTML = value;
    this.cards = [...value.matchAll(/<button class="([^"]*artifact-card[^"]*)" data-id="([^"]+)"[^>]*aria-expanded="([^"]+)"/g)].map(([, classNames, id, expanded]) => {
      const classes = classNames.trim().split(/\s+/).filter(Boolean);
      const card = new FakeCard(id, classes, expanded === 'true');
      card.parentElement = this;
      card.ownerDocument = this.ownerDocument;
      return card;
    });
  }

  querySelector(selector) {
    if (selector.startsWith('.artifact-card[data-id=')) {
      const match = selector.match(/data-id="([^"]+)"/);
      return this.cards.find((card) => card.dataset.id === match?.[1]) || null;
    }
    return this.slices?.[selector] || null;
  }

  querySelectorAll(selector) {
    if (selector === '.artifact-card') {
      return this.cards;
    }
    return [];
  }
}

async function settleMicrotasks() {
  for (let index = 0; index < 12; index += 1) {
    await Promise.resolve();
  }
}

/** Element with just enough tree behaviour for the book scene's leaf and ghost. */
class FakeBookElement extends FakeElement {
  constructor(options = {}) {
    super(options);
    this.children = [];
    this.slices = {};
  }

  appendChild(child) {
    child.parentElement = this;
    this.children.push(child);
    return child;
  }

  remove() {
    if (this.parentElement) {
      this.parentElement.children = this.parentElement.children.filter((child) => child !== this);
      this.parentElement = null;
    }
  }

  cloneNode() {
    return new FakeBookElement({ classes: [...this.classList.values] });
  }

  removeEventListener() {}

  set className(value) {
    this.classList = new FakeClassList(String(value).split(/\s+/).filter(Boolean));
  }

  querySelector(selector) {
    return this.slices[selector] || null;
  }
}

class FakeDetailPanel extends FakeElement {
  constructor() {
    super({ id: 'detail-panel' });
    this.closeButton = null;
  }

  set innerHTML(value) {
    this._innerHTML = value;
    if (!value.includes('detail-close')) {
      this.closeButton = null;
      return;
    }

    const closeButton = new FakeElement({ tagName: 'BUTTON', classes: ['detail-close'] });
    closeButton.setAttribute('data-close-detail', '');
    closeButton.parentElement = this;
    closeButton.ownerDocument = this.ownerDocument;
    this.closeButton = closeButton;
  }

  querySelector(selector) {
    if (selector === '.detail-close') {
      return this.closeButton;
    }
    return null;
  }

  querySelectorAll() {
    return this.closeButton ? [this.closeButton] : [];
  }
}

function createButton(id) {
  return new FakeElement({ id, tagName: 'BUTTON' });
}

function createRuntimeStub(initialTheme = 'dark') {
  const storage = new Map([['theme', initialTheme]]);
  const writes = [];
  const reportedErrors = [];
  return {
    writes,
    reportedErrors,
    reportError(error, context) {
      reportedErrors.push({ context, error });
    },
    readStorage(key, fallbackValue = null) {
      return storage.has(key) ? storage.get(key) : fallbackValue;
    },
    writeStorage(key, value) {
      writes.push({ key, value });
      storage.set(key, value);
      return true;
    }
  };
}

function createArtifacts(count = 13) {
  return Array.from({ length: count }, (_, index) => {
    const number = index + 1;
    const id = `artifact-${String(number).padStart(2, '0')}`;
    return {
      description: `Interactive artifact ${number}`,
      id,
      name: `Artifact ${number}`,
      tags: number % 2 === 0 ? ['finance'] : ['calculator'],
      thumbnail: number % 3 === 0 ? `apps/${id}/thumbnail.webp` : null,
      tools: number % 2 === 0 ? ['claude'] : ['chatgpt'],
      url: `apps/${id}/`
    };
  });
}

function createGalleryHarness({ initialTheme = 'dark', reducedMotion = false, search = '', withBook = false } = {}) {
  const documentListeners = new Map();
  const windowListeners = new Map();
  const timers = new Map();
  const historyCalls = [];
  const scrollCalls = [];
  let nextTimerId = 1;

  const documentObj = {
    activeElement: null,
    addEventListener(type, handler) {
      const handlers = documentListeners.get(type) || [];
      handlers.push(handler);
      documentListeners.set(type, handlers);
    },
    dispatch(type, overrides = {}) {
      const event = {
        currentTarget: documentObj,
        defaultPrevented: false,
        preventDefault() {
          this.defaultPrevented = true;
        },
        target: documentObj.body,
        ...overrides
      };
      for (const handler of documentListeners.get(type) || []) {
        handler(event);
      }
      return event;
    },
    documentElement: new FakeElement({ tagName: 'HTML' }),
    getElementById(id) {
      return elementsById.get(id) || null;
    },
    querySelector(selector) {
      return selectorMap.get(selector) || null;
    }
  };

  documentObj.documentElement.ownerDocument = documentObj;

  const windowObj = {
    ARTIFACTS_CONFIG: {
      tagDisplayOrder: ['finance', 'calculator'],
      tags: {
        calculator: { label: 'Calculator' },
        finance: { label: 'Finance' }
      },
      toolDisplayOrder: ['claude', 'chatgpt'],
      tools: {
        chatgpt: { label: 'ChatGPT' },
        claude: { label: 'Claude' }
      }
    },
    ARTIFACTS_DATA: createArtifacts(),
    addEventListener(type, handler) {
      const handlers = windowListeners.get(type) || [];
      handlers.push(handler);
      windowListeners.set(type, handlers);
    },
    dispatch(type, overrides = {}) {
      const event = {
        currentTarget: windowObj,
        defaultPrevented: false,
        preventDefault() {
          this.defaultPrevented = true;
        },
        target: windowObj,
        ...overrides
      };
      for (const handler of windowListeners.get(type) || []) {
        handler(event);
      }
      return event;
    },
    history: {
      pushState(_state, _title, url) {
        historyCalls.push(url);
        const parsed = new URL(url, 'https://example.test');
        windowObj.location.pathname = parsed.pathname;
        windowObj.location.search = parsed.search;
      }
    },
    location: {
      pathname: '/gallery/',
      search
    },
    matchMedia() {
      return { matches: reducedMotion };
    },
    requestAnimationFrame(callback) {
      callback();
      return 1;
    },
    scrollTo(options) {
      scrollCalls.push(options);
    },
    scrollY: 0,
    setTimeout(callback, delay) {
      const id = nextTimerId;
      nextTimerId += 1;
      timers.set(id, { callback, delay });
      return id;
    },
    clearTimeout(id) {
      timers.delete(id);
    },
    getComputedStyle(element) {
      return {
        getPropertyValue(property) {
          if (property === '--color-bg-primary') {
            const theme = element.getAttribute('data-theme');
            return theme === 'dark' ? 'rgb(30, 26, 20)' : 'rgb(245, 239, 230)';
          }
          return '';
        }
      };
    }
  };

  const body = new FakeElement({ tagName: 'BODY', classes: ['js-loading'] });
  body.ownerDocument = documentObj;
  documentObj.body = body;
  documentObj.activeElement = body;

  const header = new FakeElement({ classes: ['header'] });
  const container = new FakeElement({ classes: ['container'] });
  const footer = new FakeElement({ classes: ['footer'] });
  const metaThemeColor = new FakeElement({ tagName: 'META' });
  metaThemeColor.setAttribute('content', 'rgb(32, 32, 32)');

  [header, container, footer, metaThemeColor].forEach((element) => {
    element.ownerDocument = documentObj;
    element.parentElement = body;
  });

  const elementsById = new Map();
  const selectorMap = new Map([
    ['.container', container],
    ['.footer', footer],
    ['.header', header],
    ['meta[name="theme-color"]', metaThemeColor]
  ]);

  function registerElement(element) {
    element.ownerDocument = documentObj;
    if (element.id) {
      elementsById.set(element.id, element);
    }
    return element;
  }

  const grid = registerElement(new FakeGrid());
  const searchInput = registerElement(new FakeElement({ id: 'search-input', tagName: 'INPUT' }));
  const searchClear = registerElement(createButton('search-clear'));
  searchClear.classList.add('hidden');
  const searchCount = registerElement(new FakeElement({ id: 'search-count' }));
  const sortToggle = registerElement(createButton('sort-toggle'));
  const filterReset = registerElement(createButton('filter-reset'));
  const themeToggle = registerElement(createButton('theme-toggle'));
  const noResults = registerElement(new FakeElement({ id: 'no-results' }));
  noResults.classList.add('hidden');
  const noResultsReset = registerElement(createButton('no-results-reset'));
  const pagination = registerElement(new FakeElement({ id: 'pagination' }));
  const scrollTop = registerElement(createButton('scroll-top'));
  scrollTop.setAttribute('aria-hidden', 'true');
  scrollTop.tabIndex = -1;
  const detailOverlay = registerElement(new FakeElement({ id: 'detail-overlay', classes: ['detail-overlay'] }));
  detailOverlay.setAttribute('aria-hidden', 'true');
  const detailPanel = registerElement(new FakeDetailPanel());
  const bookmarkTabs = registerElement(new FakeElement({ id: 'filter-notes' }));
  const galleryStatus = registerElement(new FakeElement({ id: 'gallery-status' }));
  bookmarkTabs.querySelector = (selector) => bookmarkTabs._queryResults?.get(selector) || null;
  bookmarkTabs._queryResults = new Map();

  [
    [grid, container],
    [searchInput, container],
    [searchClear, container],
    [searchCount, container],
    [sortToggle, container],
    [filterReset, container],
    [themeToggle, header],
    [noResults, container],
    [noResultsReset, noResults],
    [pagination, container],
    [scrollTop, body],
    [detailOverlay, body],
    [detailPanel, detailOverlay],
    [bookmarkTabs, container],
    [galleryStatus, body]
  ].forEach(([child, parent]) => {
    child.parentElement = parent;
  });

  let book = null;
  if (withBook) {
    const shell = registerElement(new FakeBookElement({ id: 'book-shell' }));
    shell.dataset.sceneIntro = 'open';
    const sheet = registerElement(new FakeBookElement({ id: 'book-sheet' }));
    sheet.removeEventListener = () => {};
    grid.slices = {
      '.artifact-page-left': new FakeBookElement({ classes: ['artifact-page-left'] }),
      '.artifact-page-right': new FakeBookElement({ classes: ['artifact-page-right'] })
    };
    const frames = [];
    windowObj.requestAnimationFrame = (callback) => {
      frames.push(callback);
      return frames.length;
    };
    windowObj.cancelAnimationFrame = () => {};
    windowObj.innerWidth = 1280;
    documentObj.createElement = () => {
      const element = new FakeBookElement();
      element.slices = {
        '.artifact-page-left': new FakeBookElement({ classes: ['artifact-page-left'] }),
        '.artifact-page-right': new FakeBookElement({ classes: ['artifact-page-right'] })
      };
      Object.defineProperty(element, 'innerHTML', {
        set(value) {
          this.html = value;
        },
        get() {
          return this.html;
        }
      });
      element.querySelectorAll = () => [];
      return element;
    };
    let now = 0;
    book = {
      sheet,
      shell,
      /** Run animation frames until the book has no leaf on the sheet. */
      async runFrames(steps = 80) {
        await settleMicrotasks();
        for (let index = 0; index < steps; index += 1) {
          now += 16;
          const pending = frames.splice(0);
          pending.forEach((callback) => callback(now));
          await settleMicrotasks();
        }
      }
    };
  }

  const outsideTarget = new FakeElement({ classes: ['outside'] });
  outsideTarget.ownerDocument = documentObj;

  function runTimers(delay = null) {
    const ready = [...timers.entries()].filter(([, timer]) => delay === null || timer.delay === delay);
    ready.forEach(([id, timer]) => {
      timers.delete(id);
      timer.callback();
    });
  }

  return {
    documentObj,
    elements: {
      bookmarkTabs,
      detailOverlay,
      detailPanel,
      filterReset,
      galleryStatus,
      grid,
      metaThemeColor,
      noResults,
      noResultsReset,
      pagination,
      scrollTop,
      searchClear,
      searchCount,
      searchInput,
      sortToggle,
      themeToggle
    },
    book,
    historyCalls,
    outsideTarget,
    runTimers,
    runtime: createRuntimeStub(initialTheme),
    scrollCalls,
    windowObj
  };
}

test('readGalleryStateFromSearch normalizes query params against allowed values', () => {
  const state = readGalleryStateFromSearch({
    search: '?page=0&sort=oldest&q=Loan%20Calc&tool=chatgpt,claude,unknown&tag=finance,calculator,invalid',
    allTools: ['claude', 'chatgpt'],
    allTags: ['finance', 'calculator']
  });

  assert.deepEqual(state, {
    page: 1,
    q: 'loan calc',
    sort: 'oldest',
    tools: ['claude', 'chatgpt'],
    tags: ['finance', 'calculator'],
    rawQuery: 'Loan Calc'
  });
});

test('readGalleryStateFromSearch falls back to defaults for invalid params', () => {
  const state = readGalleryStateFromSearch({
    search: '?page=abc&sort=latest&tool=unknown&tag=invalid',
    allTools: ['claude'],
    allTags: ['finance']
  });

  assert.deepEqual(state, {
    page: 1,
    q: '',
    sort: 'newest',
    tools: [],
    tags: [],
    rawQuery: ''
  });
});

test('buildGalleryUrl omits default state from the query string', () => {
  assert.equal(
    buildGalleryUrl({
      pathname: '/gallery/',
      page: 1,
      sort: 'newest',
      q: '',
      tools: [],
      tags: []
    }),
    '/gallery/'
  );
});

test('buildGalleryUrl encodes non-default gallery state', () => {
  assert.equal(
    buildGalleryUrl({
      pathname: '/gallery/',
      page: 2,
      sort: 'oldest',
      q: 'loan calc',
      tools: ['claude', 'chatgpt'],
      tags: ['finance']
    }),
    '/gallery/?page=2&tool=claude%2Cchatgpt&tag=finance&sort=oldest&q=loan+calc'
  );
});

test('initializeGalleryApp requires runtime and required elements', () => {
  const harness = createGalleryHarness();

  assert.throws(
    () => initializeGalleryApp({ documentObj: harness.documentObj, windowObj: harness.windowObj }),
    /runtime instance is required/
  );

  const missingSearchInputHarness = createGalleryHarness();
  const originalGetElementById = missingSearchInputHarness.documentObj.getElementById;
  missingSearchInputHarness.documentObj.getElementById = (id) => {
    if (id === 'search-input') {
      return null;
    }
    return originalGetElementById(id);
  };

  assert.throws(
    () => initializeGalleryApp({
      documentObj: missingSearchInputHarness.documentObj,
      runtime: missingSearchInputHarness.runtime,
      windowObj: missingSearchInputHarness.windowObj
    }),
    /Missing required element: #search-input/
  );
});

test('initializeGalleryApp restores URL and theme state on startup', () => {
  const harness = createGalleryHarness({ initialTheme: 'light', search: '?page=2&sort=oldest' });

  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });

  assert.equal(harness.documentObj.documentElement.getAttribute('data-theme'), 'light');
  assert.equal(harness.elements.metaThemeColor.getAttribute('content'), 'rgb(245, 239, 230)');
  assert.equal(harness.elements.sortToggle.getAttribute('aria-pressed'), 'true');
  assert.equal(harness.elements.themeToggle.getAttribute('aria-label'), 'Switch to dark theme');
  assert.equal(harness.elements.galleryStatus.textContent, 'Showing 13 artifacts; page 2 of 4.');
  assert.equal(harness.elements.grid.cards.length, 4);
  assert.equal(harness.documentObj.body.classList.contains('js-loading'), false);
});

test('initializeGalleryApp normalizes an invalid stored theme', () => {
  const harness = createGalleryHarness({ initialTheme: 'sepia' });

  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });

  assert.equal(harness.documentObj.documentElement.getAttribute('data-theme'), 'light');
  assert.equal(harness.elements.themeToggle.getAttribute('aria-pressed'), 'false');
  assert.equal(harness.elements.themeToggle.getAttribute('aria-label'), 'Switch to dark theme');
  assert.equal(harness.elements.galleryStatus.textContent, 'Showing 13 artifacts; page 1 of 4.');
});

test('initializeGalleryApp syncs filters, pagination, popstate, and scrolling', () => {
  const harness = createGalleryHarness();

  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });

  const pageTwoButton = new FakeElement({ tagName: 'BUTTON' });
  pageTwoButton.dataset.page = '2';
  pageTwoButton.focus = function focus() {
    harness.documentObj.activeElement = this;
  };
  harness.elements.pagination.querySelector = (selector) => {
    if (selector === '[data-page="2"]') {
      return pageTwoButton;
    }
    return null;
  };
  harness.elements.pagination.dispatch('click', { target: pageTwoButton });
  assert.equal(harness.windowObj.location.search, '?page=2');
  assert.equal(harness.elements.grid.cards.length, 4);

  harness.elements.searchInput.value = 'Artifact 13';
  harness.elements.searchInput.dispatch('input', { target: harness.elements.searchInput });
  harness.runTimers(150);
  assert.equal(harness.windowObj.location.search, '?q=artifact+13');
  assert.equal(harness.elements.grid.cards.length, 1);
  assert.equal(harness.elements.searchClear.classList.contains('hidden'), false);
  assert.equal(harness.elements.searchCount.textContent, '1 found');

  harness.elements.searchClear.dispatch('click');
  assert.equal(harness.windowObj.location.search, '');
  assert.equal(harness.elements.searchCount.textContent, '', 'the count clears with the search');
  assert.equal(harness.documentObj.activeElement, harness.elements.searchInput);

  const toolTab = new FakeElement({ tagName: 'BUTTON', classes: ['desk-note'] });
  toolTab.dataset.filterTool = 'claude';
  toolTab.parentElement = harness.elements.bookmarkTabs;
  toolTab.ownerDocument = harness.documentObj;
  harness.elements.bookmarkTabs._queryResults.set('[data-filterTool="claude"]', toolTab);
  harness.elements.bookmarkTabs._queryResults.set('[data-filter-tool="claude"]', toolTab);
  harness.elements.bookmarkTabs.dispatch('click', { target: toolTab });
  assert.match(harness.windowObj.location.search, /tool=claude/);
  assert.equal(harness.elements.filterReset.classList.contains('is-active'), true);

  harness.elements.sortToggle.dispatch('click');
  assert.match(harness.windowObj.location.search, /sort=oldest/);
  assert.equal(harness.elements.sortToggle.getAttribute('aria-pressed'), 'true');
  assert.match(harness.windowObj.location.search, /tool=claude/);

  harness.elements.searchInput.value = 'missing artifact';
  harness.elements.searchInput.dispatch('input', { target: harness.elements.searchInput });
  harness.runTimers(150);
  assert.equal(harness.elements.grid.cards.length, 0);
  assert.equal(harness.elements.noResults.classList.contains('hidden'), false);
  assert.equal(harness.elements.galleryStatus.textContent, 'No artifacts match the current search and filters.');
  assert.equal(harness.elements.searchCount.textContent, 'nothing yet');

  harness.elements.noResultsReset.dispatch('click');
  assert.equal(harness.windowObj.location.search, '?sort=oldest');
  assert.equal(harness.documentObj.activeElement, harness.elements.searchInput);

  harness.windowObj.location.search = '?q=Artifact+12&tool=claude';
  harness.windowObj.dispatch('popstate');
  assert.equal(harness.elements.searchInput.value, 'Artifact 12');
  assert.equal(harness.elements.grid.cards.length, 1);

  harness.windowObj.scrollY = 400;
  harness.windowObj.dispatch('scroll');
  assert.equal(harness.elements.scrollTop.classList.contains('visible'), true);
  assert.equal(harness.elements.scrollTop.getAttribute('aria-hidden'), 'false');
  assert.equal(harness.elements.scrollTop.tabIndex, 0);

  harness.elements.scrollTop.dispatch('click');
  assert.deepEqual(harness.scrollCalls.at(-1), { behavior: 'smooth', top: 0 });

  harness.elements.themeToggle.dispatch('click');
  assert.equal(harness.documentObj.documentElement.getAttribute('data-theme'), 'light');
  assert.equal(harness.elements.themeToggle.getAttribute('aria-pressed'), 'false');
  assert.equal(harness.elements.themeToggle.getAttribute('aria-label'), 'Switch to dark theme');
  assert.equal(harness.elements.galleryStatus.textContent, 'Theme switched to light mode.');
  assert.deepEqual(harness.runtime.writes.at(-1), { key: 'theme', value: 'light' });
});

test('initializeGalleryApp handles overlay and keyboard interactions', async () => {
  const harness = createGalleryHarness();
  const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });

  const firstCard = harness.elements.grid.cards[0];
  harness.elements.grid.dispatch('click', { target: firstCard });
  await tick();
  assert.equal(harness.elements.detailOverlay.classList.contains('open'), true);
  assert.equal(harness.elements.detailOverlay.getAttribute('aria-hidden'), 'false');
  assert.equal(harness.documentObj.activeElement, harness.elements.detailPanel.closeButton);

  const tabEvent = harness.documentObj.dispatch('keydown', { key: 'Tab', shiftKey: false });
  assert.equal(tabEvent.defaultPrevented, true);

  harness.elements.detailOverlay.dispatch('click', { target: harness.elements.detailPanel.closeButton });
  harness.runTimers(360);
  assert.equal(harness.elements.detailOverlay.classList.contains('visible'), false);

  const enterEvent = harness.elements.grid.dispatch('keydown', {
    key: 'Enter',
    target: firstCard
  });
  assert.equal(enterEvent.defaultPrevented, true);
  await tick();
  assert.equal(harness.elements.detailOverlay.classList.contains('open'), true);

  harness.documentObj.dispatch('keydown', { key: 'Escape' });
  harness.runTimers(360);
  assert.equal(harness.elements.detailOverlay.classList.contains('visible'), false);

  harness.documentObj.activeElement = harness.documentObj.body;
  const slashEvent = harness.documentObj.dispatch('keydown', { key: '/' });
  assert.equal(slashEvent.defaultPrevented, true);
  assert.equal(harness.documentObj.activeElement, harness.elements.searchInput);

  harness.elements.grid.dispatch('click', { target: firstCard });
  await tick();
  harness.windowObj.location.search = '?page=2';
  harness.windowObj.dispatch('popstate');
  assert.equal(harness.elements.detailOverlay.classList.contains('visible'), false);
  assert.equal(harness.elements.grid.cards.length, 4);
});

test('initializeGalleryApp desk notes toggle tool and tag filters', () => {
  const harness = createGalleryHarness();

  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });

  function createDeskNote(dataset) {
    const deskNote = new FakeElement({ tagName: 'BUTTON', classes: ['desk-note'] });
    Object.assign(deskNote.dataset, dataset);
    deskNote.parentElement = harness.elements.bookmarkTabs;
    deskNote.ownerDocument = harness.documentObj;
    for (const [key, value] of Object.entries(dataset)) {
      harness.elements.bookmarkTabs._queryResults.set(`[data-${key}="${value}"]`, deskNote);
      const kebabKey = key.replace(/[A-Z]/g, (char) => `-${char.toLowerCase()}`);
      harness.elements.bookmarkTabs._queryResults.set(`[data-${kebabKey}="${value}"]`, deskNote);
    }
    return deskNote;
  }

  const claudeTab = createDeskNote({ filterTool: 'claude' });
  harness.elements.bookmarkTabs.dispatch('click', { target: claudeTab });
  assert.match(harness.windowObj.location.search, /tool=claude/);
  assert.equal(harness.elements.filterReset.classList.contains('is-active'), true);

  const chatgptTab = createDeskNote({ filterTool: 'chatgpt' });
  harness.elements.bookmarkTabs.dispatch('click', { target: chatgptTab });
  const bothToolsParam = new URLSearchParams(harness.windowObj.location.search).get('tool');
  assert.match(bothToolsParam, /claude/);
  assert.match(bothToolsParam, /chatgpt/);

  harness.elements.bookmarkTabs.dispatch('click', { target: claudeTab });
  const afterRemoveParam = new URLSearchParams(harness.windowObj.location.search).get('tool');
  assert.doesNotMatch(afterRemoveParam, /claude/);
  assert.match(afterRemoveParam, /chatgpt/);

  const gameTag = createDeskNote({ filterTag: 'game' });
  harness.elements.bookmarkTabs.dispatch('click', { target: gameTag });
  assert.match(harness.windowObj.location.search, /tag=game/);
  assert.match(harness.windowObj.location.search, /tool=chatgpt/);

  harness.elements.bookmarkTabs.dispatch('click', { target: gameTag });
  assert.doesNotMatch(harness.windowObj.location.search, /tag=game/);

  const allToolsTab = createDeskNote({ filterNote: 'all-tools' });
  harness.elements.bookmarkTabs.dispatch('click', { target: allToolsTab });
  assert.doesNotMatch(harness.windowObj.location.search, /tool=/);

  const allTagsTab = createDeskNote({ filterNote: 'all-tags' });
  harness.elements.bookmarkTabs.dispatch('click', { target: allTagsTab });
  assert.doesNotMatch(harness.windowObj.location.search, /tag=/);
  assert.equal(harness.elements.filterReset.classList.contains('is-active'), false);

  const pageTwoButton = new FakeElement({ tagName: 'BUTTON' });
  pageTwoButton.dataset.page = '2';
  pageTwoButton.focus = function focus() {
    harness.documentObj.activeElement = this;
  };
  harness.elements.pagination.querySelector = (selector) => {
    if (selector === '[data-page="2"]') {
      return pageTwoButton;
    }
    return null;
  };
  harness.elements.pagination.dispatch('click', { target: pageTwoButton });
  assert.match(harness.windowObj.location.search, /page=2/);
  assert.equal(harness.documentObj.activeElement?.dataset.page, '2');
  harness.elements.bookmarkTabs.dispatch('click', { target: claudeTab });
  assert.doesNotMatch(harness.windowObj.location.search, /page=2/);
  assert.equal(harness.documentObj.activeElement, claudeTab);

  const prevSearch = harness.windowObj.location.search;
  const nonTab = new FakeElement({ tagName: 'DIV' });
  nonTab.parentElement = harness.elements.bookmarkTabs;
  harness.elements.bookmarkTabs.dispatch('click', { target: nonTab });
  assert.equal(harness.windowObj.location.search, prevSearch);
});

function createPageButton(harness, { page, step }) {
  const button = new FakeElement({ tagName: 'BUTTON' });
  button.dataset.page = String(page);
  if (step !== undefined) {
    button.dataset.pageStep = String(step);
  }
  button.focus = function focus() {
    harness.documentObj.activeElement = this;
  };
  return button;
}

test('pagination Previous and Next step from the latest requested page', () => {
  const harness = createGalleryHarness();
  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });

  const next = createPageButton(harness, { page: 2, step: 1 });
  harness.elements.pagination.dispatch('click', { target: next });
  harness.elements.pagination.dispatch('click', { target: next });
  harness.elements.pagination.dispatch('click', { target: next });
  assert.equal(harness.windowObj.location.search, '?page=4', 'repeated presses keep stepping');
  assert.equal(harness.elements.galleryStatus.textContent, 'Showing 13 artifacts; page 4 of 4.');

  harness.elements.pagination.dispatch('click', { target: next });
  assert.equal(harness.windowObj.location.search, '?page=4', 'Next on the last page is ignored');

  const previous = createPageButton(harness, { page: 3, step: -1 });
  harness.elements.pagination.dispatch('click', { target: previous });
  assert.equal(harness.windowObj.location.search, '?page=3');
});

test('pagination keeps focus on the Next button while stepping', () => {
  const harness = createGalleryHarness();
  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });

  const nextButton = createPageButton(harness, { page: 2, step: 1 });
  const pageButton = createPageButton(harness, { page: 2 });
  let stepEnabled = true;
  harness.elements.pagination.querySelector = (selector) => {
    if (selector.startsWith('[data-page-step="1"]')) {
      return stepEnabled ? nextButton : null;
    }
    if (selector === '[data-page="2"]') {
      return pageButton;
    }
    return null;
  };

  harness.elements.pagination.dispatch('click', { target: nextButton });
  assert.equal(harness.documentObj.activeElement, nextButton);

  stepEnabled = false;
  harness.elements.pagination.dispatch('click', { target: createPageButton(harness, { page: 1, step: -1 }) });
  harness.elements.pagination.dispatch('click', { target: nextButton });
  assert.equal(harness.documentObj.activeElement, pageButton, 'falls back to the page button when Next is disabled');
});

test('pagination ignores disabled buttons, the current page, and non-page targets', () => {
  const harness = createGalleryHarness();
  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });

  const disabled = createPageButton(harness, { page: 2 });
  disabled.disabled = true;
  harness.elements.pagination.dispatch('click', { target: disabled });
  harness.elements.pagination.dispatch('click', { target: createPageButton(harness, { page: 1 }) });
  harness.elements.pagination.dispatch('click', { target: new FakeElement({ tagName: 'DIV' }) });
  assert.equal(harness.historyCalls.length, 0);
});

test('broken thumbnails are caught on the whole book sheet, or on the grid without a book', () => {
  const withBook = createGalleryHarness({ withBook: true });
  initializeGalleryApp({ documentObj: withBook.documentObj, runtime: withBook.runtime, windowObj: withBook.windowObj });
  assert.equal(withBook.book.sheet.listeners.get('error')?.length, 1, 'the sheet covers turning leaves and ghost pages');
  assert.equal(withBook.elements.grid.listeners.get('error'), undefined);

  const withoutBook = createGalleryHarness();
  initializeGalleryApp({
    documentObj: withoutBook.documentObj,
    runtime: withoutBook.runtime,
    windowObj: withoutBook.windowObj
  });
  assert.equal(withoutBook.elements.grid.listeners.get('error')?.length, 1);
});

test('page turns keep the live book untouched until the leaf lands and then render the page', async () => {
  const harness = createGalleryHarness({ withBook: true });
  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });
  const { book, elements } = harness;
  const pageOneHtml = elements.grid.innerHTML;
  assert.match(elements.galleryStatus.textContent, /page 1 of 4/);
  assert.equal(book.sheet.dataset.hasPrevious, 'false');
  assert.equal(book.sheet.dataset.hasNext, 'true');

  elements.pagination.dispatch('click', { target: createPageButton(harness, { page: 3 }) });
  await settleMicrotasks();
  assert.equal(harness.windowObj.location.search, '?page=3', 'URL and pagination move at once');
  assert.equal(elements.grid.innerHTML, pageOneHtml, 'the pages under the leaf are untouched');
  assert.equal(book.sheet.children.length, 2, 'a ghost page and one leaf');

  await book.runFrames();
  assert.notEqual(elements.grid.innerHTML, pageOneHtml);
  assert.match(elements.grid.innerHTML, /page-number" aria-hidden="true">5</);
  assert.equal(book.sheet.children.length, 0, 'no leaf or ghost remains');
  assert.equal(elements.galleryStatus.textContent, 'Showing 13 artifacts; page 3 of 4.');
  assert.equal(book.sheet.dataset.hasNext, 'true');
});

test('rapid Next presses during a turn coalesce and end on the right page', async () => {
  const harness = createGalleryHarness({ withBook: true });
  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });
  const { book, elements } = harness;
  const next = createPageButton(harness, { page: 2, step: 1 });

  elements.pagination.dispatch('click', { target: next });
  await settleMicrotasks();
  await book.runFrames(5);
  elements.pagination.dispatch('click', { target: next });
  elements.pagination.dispatch('click', { target: next });
  assert.equal(harness.windowObj.location.search, '?page=4');

  await book.runFrames(200);
  assert.equal(elements.galleryStatus.textContent, 'Showing 13 artifacts; page 4 of 4.');
  assert.match(elements.grid.innerHTML, /page-number" aria-hidden="true">7</);
  assert.equal(book.sheet.children.length, 0);
  assert.equal(harness.runtime.reportedErrors.length, 0);
});

test('search, filter, and sort changes during a page turn render the new results and drop the leaf', async () => {
  const harness = createGalleryHarness({ withBook: true });
  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });
  const { book, elements } = harness;

  elements.pagination.dispatch('click', { target: createPageButton(harness, { page: 3 }) });
  await settleMicrotasks();
  assert.equal(book.sheet.children.length, 2);

  elements.sortToggle.dispatch('click');
  assert.equal(book.sheet.children.length, 0, 'the leaf is dropped');
  assert.equal(harness.windowObj.location.search, '?sort=oldest');
  assert.match(elements.galleryStatus.textContent, /page 1 of 4/);

  await book.runFrames(200);
  assert.match(elements.galleryStatus.textContent, /page 1 of 4/, 'a dropped turn never lands later');
  assert.equal(elements.grid.cards.length, 4);
});

test('the browser back button during a page turn renders the URL state', async () => {
  const harness = createGalleryHarness({ withBook: true });
  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });
  const { book, elements } = harness;

  elements.pagination.dispatch('click', { target: createPageButton(harness, { page: 2 }) });
  await settleMicrotasks();
  assert.equal(book.sheet.children.length, 2);
  harness.windowObj.location.search = '';
  harness.windowObj.dispatch('popstate');
  assert.equal(book.sheet.children.length, 0);
  assert.match(elements.galleryStatus.textContent, /page 1 of 4/);
});

test('an error while a page turn lands is reported to the runtime', async () => {
  const harness = createGalleryHarness({ withBook: true });
  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });
  const { book, elements } = harness;

  elements.pagination.dispatch('click', { target: createPageButton(harness, { page: 2 }) });
  await settleMicrotasks();
  Object.defineProperty(elements.galleryStatus, 'textContent', {
    set() {
      throw new Error('status failed');
    },
    get() {
      return '';
    }
  });
  await book.runFrames(200);
  assert.equal(book.sheet.children.length, 0);
  assert.equal(harness.runtime.reportedErrors.length, 1);
  assert.equal(harness.runtime.reportedErrors[0].context, 'page turn');
});

test('page turns on an empty result set do not build a leaf', async () => {
  const harness = createGalleryHarness({ withBook: true, search: '?q=missing+artifact' });
  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });

  assert.equal(harness.elements.grid.cards.length, 0);
  assert.equal(harness.elements.pagination.innerHTML, '');
  assert.equal(harness.book.sheet.dataset.hasNext, 'false');
});
