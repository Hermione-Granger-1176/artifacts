import test from 'node:test';
import assert from 'node:assert/strict';

import {
  initializeGalleryApp,
  buildGalleryUrl,
  readGalleryStateFromSearch
} from '../../js/modules/gallery-app.js';

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
    let node = target;
    while (node) {
      if (node === this) {
        return true;
      }
      node = node.parentElement;
    }
    return false;
  }

  matches(selector) {
    if (selector.startsWith('#')) {
      return this.id === selector.slice(1);
    }

    if (selector === '[data-close-detail]') {
      return this.hasAttribute('data-close-detail');
    }

    if (selector === '[data-page]') {
      return Object.hasOwn(this.dataset, 'page');
    }

    if (selector.startsWith('.')) {
      return this.classList.contains(selector.slice(1));
    }

    return false;
  }

  closest(selector) {
    let node = this;
    while (node) {
      if (node.matches(selector)) {
        return node;
      }
      node = node.parentElement;
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

class FakeCheckbox extends FakeElement {
  constructor(value) {
    super({ tagName: 'INPUT', classes: ['filter-dropdown-checkbox'] });
    this.value = value;
    this.checked = false;
  }
}

class FakeFilterOption extends FakeElement {
  constructor() {
    super({ tagName: 'LABEL', classes: ['filter-dropdown-item'] });
  }
}

class FakeFilterPanel extends FakeElement {
  constructor(id) {
    super({ id });
    this.checkboxes = [];
  }

  set innerHTML(value) {
    this._innerHTML = value;
    this.checkboxes = [];
    for (const [, checkboxValue] of value.matchAll(/value="([^"]+)"/g)) {
      const option = new FakeFilterOption();
      option.parentElement = this;
      option.ownerDocument = this.ownerDocument;
      const checkbox = new FakeCheckbox(checkboxValue);
      checkbox.parentElement = option;
      checkbox.ownerDocument = this.ownerDocument;
      this.checkboxes.push(checkbox);
    }
  }

  querySelectorAll(selector) {
    if (selector === '.filter-dropdown-checkbox') {
      return this.checkboxes;
    }
    return [];
  }
}

class FakeCard extends FakeElement {
  constructor(id, classes, expanded) {
    super({ tagName: 'ARTICLE', classes });
    this.dataset.id = id;
    this.setAttribute('aria-expanded', String(expanded));
  }

  matches(selector) {
    if (selector === '.artifact-card') {
      return true;
    }

    if (selector.startsWith('.artifact-card[data-id=')) {
      const match = selector.match(/data-id="([^"]+)"/);
      return this.dataset.id === match?.[1];
    }

    return super.matches(selector);
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

  set innerHTML(value) {
    this._innerHTML = value;
    this.cards = [];
    for (const [, classNames, id, expanded] of value.matchAll(/<article class="([^"]*artifact-card[^"]*)" data-id="([^"]+)"[^>]*aria-expanded="([^"]+)"/g)) {
      const classes = classNames.trim().split(/\s+/).filter(Boolean);
      const card = new FakeCard(id, classes, expanded === 'true');
      card.parentElement = this;
      card.ownerDocument = this.ownerDocument;
      this.cards.push(card);
    }
  }

  querySelector(selector) {
    if (selector.startsWith('.artifact-card[data-id=')) {
      const match = selector.match(/data-id="([^"]+)"/);
      return this.cards.find((card) => card.dataset.id === match?.[1]) || null;
    }
    return null;
  }

  querySelectorAll(selector) {
    if (selector === '.artifact-card') {
      return this.cards;
    }
    return [];
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
  return {
    writes,
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

function createGalleryHarness({ initialTheme = 'dark', reducedMotion = false, search = '' } = {}) {
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
  metaThemeColor.setAttribute('content', '#202020');

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
  const sortToggle = registerElement(createButton('sort-toggle'));
  const filterReset = registerElement(createButton('filter-reset'));
  filterReset.classList.add('hidden');
  const themeToggle = registerElement(createButton('theme-toggle'));
  const noResults = registerElement(new FakeElement({ id: 'no-results' }));
  noResults.classList.add('hidden');
  const noResultsReset = registerElement(createButton('no-results-reset'));
  const pagination = registerElement(new FakeElement({ id: 'pagination' }));
  const scrollTop = registerElement(createButton('scroll-top'));
  const detailOverlay = registerElement(new FakeElement({ id: 'detail-overlay', classes: ['detail-overlay'] }));
  detailOverlay.setAttribute('aria-hidden', 'true');
  const detailPanel = registerElement(new FakeDetailPanel());

  const toolDropdown = registerElement(new FakeElement({ id: 'tool-dropdown' }));
  const toolFilterToggle = registerElement(createButton('tool-filter-toggle'));
  const toolFilterLabel = registerElement(new FakeElement({ id: 'tool-filter-label' }));
  const toolFilterPanel = registerElement(new FakeFilterPanel('tool-filter-panel'));
  toolFilterPanel.setAttribute('aria-hidden', 'true');

  const tagDropdown = registerElement(new FakeElement({ id: 'tag-dropdown' }));
  const tagFilterToggle = registerElement(createButton('tag-filter-toggle'));
  const tagFilterLabel = registerElement(new FakeElement({ id: 'tag-filter-label' }));
  const tagFilterPanel = registerElement(new FakeFilterPanel('tag-filter-panel'));
  tagFilterPanel.setAttribute('aria-hidden', 'true');

  [
    [toolFilterToggle, toolDropdown],
    [toolFilterLabel, toolDropdown],
    [toolFilterPanel, toolDropdown],
    [tagFilterToggle, tagDropdown],
    [tagFilterLabel, tagDropdown],
    [tagFilterPanel, tagDropdown],
    [grid, container],
    [searchInput, container],
    [searchClear, container],
    [sortToggle, container],
    [filterReset, container],
    [themeToggle, header],
    [noResults, container],
    [noResultsReset, noResults],
    [pagination, container],
    [scrollTop, body],
    [detailOverlay, body],
    [detailPanel, detailOverlay]
  ].forEach(([child, parent]) => {
    child.parentElement = parent;
  });

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
      detailOverlay,
      detailPanel,
      filterReset,
      grid,
      metaThemeColor,
      noResults,
      noResultsReset,
      pagination,
      scrollTop,
      searchClear,
      searchInput,
      sortToggle,
      tagDropdown,
      tagFilterLabel,
      tagFilterPanel,
      tagFilterToggle,
      themeToggle,
      toolDropdown,
      toolFilterLabel,
      toolFilterPanel,
      toolFilterToggle
    },
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
  assert.equal(harness.elements.metaThemeColor.getAttribute('content'), '#f0f0f0');
  assert.equal(harness.elements.sortToggle.getAttribute('aria-pressed'), 'true');
  assert.equal(harness.elements.grid.cards.length, 1);
  assert.equal(harness.documentObj.body.classList.contains('js-loading'), false);
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
  harness.elements.pagination.dispatch('click', { target: pageTwoButton });
  assert.equal(harness.windowObj.location.search, '?page=2');
  assert.equal(harness.elements.grid.cards.length, 1);

  harness.elements.searchInput.value = 'Artifact 13';
  harness.elements.searchInput.dispatch('input', { target: harness.elements.searchInput });
  harness.runTimers(150);
  assert.equal(harness.windowObj.location.search, '?q=artifact+13');
  assert.equal(harness.elements.grid.cards.length, 1);
  assert.equal(harness.elements.searchClear.classList.contains('hidden'), false);

  harness.elements.searchClear.dispatch('click');
  assert.equal(harness.windowObj.location.search, '');
  assert.equal(harness.documentObj.activeElement, harness.elements.searchInput);

  harness.elements.toolFilterToggle.dispatch('click');
  assert.equal(harness.elements.toolDropdown.classList.contains('open'), true);
  const chatgptCheckbox = harness.elements.toolFilterPanel.checkboxes.find((checkbox) => checkbox.value === 'chatgpt');
  chatgptCheckbox.checked = true;
  harness.elements.toolFilterPanel.dispatch('change', { target: chatgptCheckbox });
  assert.match(harness.windowObj.location.search, /tool=chatgpt/);
  assert.equal(harness.elements.toolFilterLabel.textContent, 'ChatGPT');

  harness.elements.tagFilterToggle.dispatch('click');
  const calculatorCheckbox = harness.elements.tagFilterPanel.checkboxes.find((checkbox) => checkbox.value === 'calculator');
  calculatorCheckbox.checked = true;
  harness.elements.tagFilterPanel.dispatch('change', { target: calculatorCheckbox });
  assert.match(harness.windowObj.location.search, /tag=calculator/);
  assert.equal(harness.elements.tagFilterLabel.textContent, 'Calculator');
  assert.equal(harness.elements.filterReset.classList.contains('hidden'), false);

  harness.documentObj.dispatch('click', { target: harness.outsideTarget });
  assert.equal(harness.elements.tagDropdown.classList.contains('open'), false);

  harness.elements.sortToggle.dispatch('click');
  assert.match(harness.windowObj.location.search, /sort=oldest/);
  assert.equal(harness.elements.sortToggle.getAttribute('aria-pressed'), 'true');

  harness.elements.searchInput.value = 'missing artifact';
  harness.elements.searchInput.dispatch('input', { target: harness.elements.searchInput });
  harness.runTimers(150);
  assert.equal(harness.elements.grid.cards.length, 0);
  assert.equal(harness.elements.noResults.classList.contains('hidden'), false);

  harness.elements.noResultsReset.dispatch('click');
  assert.equal(harness.windowObj.location.search, '?sort=oldest');
  assert.equal(harness.documentObj.activeElement, harness.elements.searchInput);

  harness.windowObj.location.search = '?q=Artifact+12&tool=claude';
  harness.windowObj.dispatch('popstate');
  assert.equal(harness.elements.searchInput.value, 'Artifact 12');
  assert.equal(harness.elements.toolFilterLabel.textContent, 'Claude');
  assert.equal(harness.elements.grid.cards.length, 1);

  harness.windowObj.scrollY = 400;
  harness.windowObj.dispatch('scroll');
  assert.equal(harness.elements.scrollTop.classList.contains('visible'), true);

  harness.elements.scrollTop.dispatch('click');
  assert.deepEqual(harness.scrollCalls.at(-1), { behavior: 'smooth', top: 0 });

  harness.elements.themeToggle.dispatch('click');
  assert.equal(harness.documentObj.documentElement.getAttribute('data-theme'), 'light');
  assert.deepEqual(harness.runtime.writes.at(-1), { key: 'theme', value: 'light' });
});

test('initializeGalleryApp handles overlay and keyboard interactions', () => {
  const harness = createGalleryHarness();

  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });

  const firstCard = harness.elements.grid.cards[0];
  harness.elements.grid.dispatch('click', { target: firstCard });
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
  assert.equal(harness.elements.detailOverlay.classList.contains('open'), true);

  harness.documentObj.dispatch('keydown', { key: 'Escape' });
  harness.runTimers(360);
  assert.equal(harness.elements.detailOverlay.classList.contains('visible'), false);

  harness.documentObj.activeElement = harness.documentObj.body;
  const slashEvent = harness.documentObj.dispatch('keydown', { key: '/' });
  assert.equal(slashEvent.defaultPrevented, true);
  assert.equal(harness.documentObj.activeElement, harness.elements.searchInput);

  harness.elements.grid.dispatch('click', { target: firstCard });
  harness.windowObj.location.search = '?page=2';
  harness.windowObj.dispatch('popstate');
  assert.equal(harness.elements.detailOverlay.classList.contains('visible'), false);
  assert.equal(harness.elements.grid.cards.length, 1);
});
