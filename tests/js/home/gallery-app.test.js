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
      case '[data-close-filter-panel]':
        return this.hasAttribute('data-close-filter-panel');
      case '[data-filter-panel-search]':
        return this.hasAttribute('data-filter-panel-search');
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

/** Native dialog stand-in: showModal and close flip `open`, and close fires the close event. */
class FakeDialog extends FakeElement {
  constructor(id) {
    super({ id, tagName: 'DIALOG', classes: ['filter-panel'] });
    this.open = false;
  }

  showModal() {
    this.open = true;
  }

  close() {
    if (this.open) {
      this.open = false;
      this.dispatch('close');
    }
  }
}

/** Children list whose appendChild moves an existing child to the end, like the DOM. */
class FakeList extends FakeElement {
  constructor() {
    super({ classes: ['filter-panel-options'] });
    this.children = [];
  }

  appendChild(child) {
    this.children = [...this.children.filter((entry) => entry !== child), child];
    child.parentElement = this;
    return child;
  }

  prepend(...nodes) {
    this.children = [...nodes, ...this.children.filter((entry) => !nodes.includes(entry))];
    nodes.forEach((node) => {
      node.parentElement = this;
    });
  }

  querySelectorAll(selector) {
    if (selector === '[aria-pressed="true"]') {
      return this.children.filter((child) => child.getAttribute('aria-pressed') === 'true');
    }
    return super.querySelectorAll(selector);
  }
}

/**
 * Build one fake filter dropdown: its button, summary, panel, option list, and search box,
 * wired so the container's selector lookups find them.
 * @param {FakeElement} container - The #filter-dropdowns container.
 * @param {(element: FakeElement) => FakeElement} registerElement - Harness registration.
 * @param {{ kind: string, dataset: string, values: string[] }} group - Group shape.
 */
function addFakeDropdown(container, registerElement, { kind, dataset, values }) {
  const panelId = `filter-panel-${kind}`;
  const toggle = new FakeElement({ tagName: 'BUTTON', classes: ['filter-dropdown-toggle'] });
  toggle.setAttribute('aria-controls', panelId);
  toggle.setAttribute('aria-expanded', 'false');
  toggle.dataset.filterOpen = kind;
  toggle.parentElement = container;
  const summary = new FakeElement({ tagName: 'SPAN' });
  const panel = registerElement(new FakeDialog(panelId));
  panel.parentElement = container;
  const list = new FakeList();
  list.parentElement = panel;
  const options = values.map((value) => {
    const option = new FakeElement({ tagName: 'BUTTON', classes: ['filter-option'] });
    option.dataset[dataset] = value;
    option.dataset.filterSurface = 'mobile';
    option.textContent = value.toUpperCase();
    option.setAttribute('aria-pressed', 'false');
    list.appendChild(option);
    return option;
  });
  const searchBox = new FakeElement({ tagName: 'INPUT' });
  searchBox.setAttribute('data-filter-panel-search', '');
  searchBox.parentElement = panel;
  const clear = new FakeElement({ tagName: 'BUTTON', classes: ['filter-panel-clear'] });
  clear.dataset.filterNote = `all-${kind}`;
  clear.dataset.filterSurface = 'mobile';
  clear.parentElement = panel;
  clear.ownerDocument = container.ownerDocument;
  panel.querySelector = (selector) => ({ '.filter-panel-options': list, '[data-filter-panel-search]': searchBox })[selector] || null;
  panel.querySelectorAll = (selector) => (selector === '.filter-option' ? list.children : []);
  container._queryResults.set(`[aria-controls="${panelId}"]`, toggle);
  container._queryResults.set(`[data-filter-open="${kind}"]`, toggle);
  container._queryResults.set(`[data-filter-summary="${kind}"]`, summary);
  container._queryResults.set(`[data-filter-surface="mobile"][data-filter-note="all-${kind}"]`, clear);
  container._panels.push(panel);
  container._options.push(...options);
  return { toggle, summary, panel, list, options, searchBox, clear };
}

function createGalleryHarness({
  initialTheme = 'dark',
  reducedMotion = false,
  search = '',
  withBook = false,
  withDropdowns = false,
  withSheet = false,
  notepad = false
} = {}) {
  const documentListeners = new Map();
  const mediaListeners = [];
  let notepadLayout = notepad;
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
    matchMedia(query = '') {
      const isMotionQuery = query.includes('reduced-motion');
      return {
        get matches() {
          return isMotionQuery ? reducedMotion : notepadLayout;
        },
        addEventListener(_type, handler) {
          if (!isMotionQuery) {
            mediaListeners.push(handler);
          }
        }
      };
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
  const filterDropdowns = registerElement(new FakeElement({ id: 'filter-dropdowns' }));
  filterDropdowns._queryResults = new Map();
  filterDropdowns._panels = [];
  filterDropdowns._options = [];
  filterDropdowns.querySelector = (selector) => filterDropdowns._queryResults.get(selector) || null;
  filterDropdowns.querySelectorAll = (selector) => {
    if (selector === '.filter-panel') {
      return filterDropdowns._panels;
    }
    const match = selector.match(/^\[data-(filter-tag|filter-tool)\]$/);
    const key = match && (match[1] === 'filter-tag' ? 'filterTag' : 'filterTool');
    return key ? filterDropdowns._options.filter((option) => option.dataset[key] !== undefined) : [];
  };
  const dropdowns = withDropdowns
    ? {
      tags: addFakeDropdown(filterDropdowns, registerElement, { kind: 'tags', dataset: 'filterTag', values: ['finance', 'calculator'] }),
      tools: addFakeDropdown(filterDropdowns, registerElement, { kind: 'tools', dataset: 'filterTool', values: ['claude', 'chatgpt'] })
    }
    : null;

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
  if (withSheet && !withBook) {
    // A bare sheet takes swipes; with no book shell the scene renders each page at once.
    book = { sheet: registerElement(new FakeElement({ id: 'book-sheet' })) };
  }
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
    // Leaf turns play as Web Animations; each one finishes when the frame clock passes its duration.
    const animations = [];
    const animate = (keyframes, options) => {
      const animation = {
        endsAt: now + (options.duration || 0),
        cancelled: false,
        cancel() {
          this.cancelled = true;
          this.reject(new DOMException('cancelled', 'AbortError'));
        }
      };
      animation.finished = new Promise((resolve, reject) => {
        animation.resolve = resolve;
        animation.reject = reject;
      });
      animation.finished.catch(() => undefined);
      animations.push(animation);
      return animation;
    };
    documentObj.createElement = () => {
      const element = new FakeBookElement();
      element.animate = animate;
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
          for (const animation of animations.splice(0)) {
            if (animation.cancelled) {
              continue;
            }
            if (animation.endsAt <= now) {
              animation.resolve();
            } else {
              animations.push(animation);
            }
          }
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
      filterDropdowns,
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
    dropdowns,
    /** Cross the notepad breakpoint, where the dropdowns replace the desk notes, firing its change listeners. */
    setNotepadLayout(matches) {
      notepadLayout = matches;
      mediaListeners.forEach((handler) => handler());
    },
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
  button.focus = function focus(options) {
    harness.documentObj.activeElement = this;
    this.focusOptions = options;
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
  assert.deepEqual(nextButton.focusOptions, { preventScroll: true }, 'restoring focus never scrolls the page');

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
  assert.match(harness.elements.pagination.innerHTML, /page-slot-empty/, 'the pagination row keeps its shape');
  assert.equal(harness.elements.pagination.innerHTML.match(/<button/g).length, 5);
  assert.equal(harness.elements.pagination.innerHTML.match(/ disabled /g).length, 4, 'every control is disabled');
  assert.equal(harness.book.sheet.dataset.hasNext, 'false');
});

test('a render that would write the same cards leaves the grid alone', () => {
  const harness = createGalleryHarness();
  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });
  const grid = harness.elements.grid;
  const cards = grid.cards;
  // Every artifact matches "artifact", so the first page shows the same cards.
  harness.elements.searchInput.value = 'artifact';
  harness.elements.searchInput.dispatch('input', { target: harness.elements.searchInput });
  harness.runTimers();
  assert.equal(grid.cards, cards, 'the same matches keep the same card elements');

  harness.elements.searchInput.value = 'Artifact 13';
  harness.elements.searchInput.dispatch('input', { target: harness.elements.searchInput });
  harness.runTimers();
  assert.notEqual(grid.cards, cards, 'different matches render new cards');
});

test('the filtered list is computed once per search, filter, and sort state', async () => {
  const harness = createGalleryHarness({ withBook: true });
  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });
  // A filter pass sorts a fresh list of every matching artifact, so count the sorts of 13 items.
  const originalSort = Array.prototype.sort;
  let passes = 0;
  Array.prototype.sort = function countingSort(...args) {
    passes += this.length === 13 ? 1 : 0;
    return originalSort.apply(this, args);
  };
  const filterPasses = () => passes;
  try {
    harness.elements.pagination.dispatch('click', { target: createPageButton(harness, { page: 2 }) });
    await settleMicrotasks();
    await harness.book.runFrames();
    assert.equal(filterPasses(), 0, 'a page turn and its faces reuse the list the render made');

    harness.elements.sortToggle.dispatch('click');
    assert.equal(filterPasses(), 1, 'a new sort order filters once');

    harness.elements.sortToggle.dispatch('click');
    assert.equal(filterPasses(), 2, 'going back is a new state again, because only the last list is kept');
  } finally {
    Array.prototype.sort = originalSort;
  }
});

test('switching theme turns transitions off for two frames and restores them', async () => {
  const harness = createGalleryHarness({ initialTheme: 'light', withBook: true });
  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });
  const root = harness.documentObj.documentElement;
  await harness.book.runFrames(4);
  assert.equal(root.classList.contains('theme-switching'), false, 'the first paint settles');

  harness.elements.themeToggle.dispatch('click');
  assert.equal(root.getAttribute('data-theme'), 'dark');
  assert.equal(root.classList.contains('theme-switching'), true, 'the class is on before the colors change');

  await harness.book.runFrames(1);
  assert.equal(root.classList.contains('theme-switching'), true, 'it stays through the first frame');
  await harness.book.runFrames(3);
  assert.equal(root.classList.contains('theme-switching'), false);

  // A second switch inside the window keeps transitions off until its own frames are done.
  harness.elements.themeToggle.dispatch('click');
  await harness.book.runFrames(1);
  harness.elements.themeToggle.dispatch('click');
  await harness.book.runFrames(1);
  assert.equal(root.classList.contains('theme-switching'), true, 'the earlier switch does not end the later one early');
  await harness.book.runFrames(3);
  assert.equal(root.classList.contains('theme-switching'), false);
});

test('applying the theme that is already set does not touch transitions', () => {
  const harness = createGalleryHarness({ initialTheme: 'dark' });
  harness.documentObj.documentElement.setAttribute('data-theme', 'dark');
  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });
  assert.equal(harness.documentObj.documentElement.classList.contains('theme-switching'), false);
});

test('the filter summaries are only rewritten when their text changes', () => {
  const harness = createGalleryHarness();
  const writes = [];
  const summaries = new Map();
  const notes = harness.elements.bookmarkTabs;
  const dropdowns = harness.elements.filterDropdowns;
  notes.querySelectorAll = () => [];
  dropdowns.querySelector = (selector) => {
    const kind = selector.match(/data-filter-summary="(\w+)"/)?.[1];
    if (!kind) {
      return null;
    }
    if (!summaries.has(kind)) {
      let text = '';
      summaries.set(kind, {
        get textContent() {
          return text;
        },
        set textContent(value) {
          text = value;
          writes.push(`${kind}:${value}`);
        }
      });
    }
    return summaries.get(kind);
  };
  initializeGalleryApp({
    documentObj: harness.documentObj,
    runtime: harness.runtime,
    windowObj: harness.windowObj
  });
  assert.deepEqual(writes, [], 'nothing to write at startup');

  const note = new FakeElement({ tagName: 'BUTTON', classes: ['desk-note'] });
  note.dataset.filterTool = 'claude';
  note.parentElement = notes;
  notes.dispatch('click', { target: note });
  assert.deepEqual(writes, ['tools:1'], 'only the changed summary is written');
});

test('a dropdown button opens its panel with picked options first, and the panel closes from its buttons and backdrop', () => {
  const harness = createGalleryHarness({ withDropdowns: true, search: '?tag=calculator' });
  initializeGalleryApp({ documentObj: harness.documentObj, runtime: harness.runtime, windowObj: harness.windowObj });
  const { filterDropdowns } = harness.elements;
  const { toggle, panel, list, options } = harness.dropdowns.tags;

  assert.deepEqual(list.children, options, 'options start in their display order');
  filterDropdowns.dispatch('click', { target: toggle });
  assert.equal(panel.open, true);
  assert.equal(toggle.getAttribute('aria-expanded'), 'true');
  assert.deepEqual(list.children.map((option) => option.dataset.filterTag), ['calculator', 'finance'], 'the picked tag moves to the top as the panel opens');

  filterDropdowns.dispatch('click', { target: toggle });
  assert.equal(panel.open, true, 'a second press leaves the open panel alone');

  const done = new FakeElement({ tagName: 'BUTTON' });
  done.setAttribute('data-close-filter-panel', '');
  done.parentElement = panel;
  filterDropdowns.dispatch('click', { target: done });
  assert.equal(panel.open, false);
  assert.equal(toggle.getAttribute('aria-expanded'), 'false');

  filterDropdowns.dispatch('click', { target: toggle });
  filterDropdowns.dispatch('click', { target: options[0] });
  assert.equal(panel.open, true, 'ticking an option keeps the panel open');
  filterDropdowns.dispatch('click', { target: panel });
  assert.equal(panel.open, false, 'a tap on the backdrop closes it');

  const outside = new FakeElement({ tagName: 'DIV' });
  outside.parentElement = filterDropdowns;
  assert.doesNotThrow(() => filterDropdowns.dispatch('click', { target: outside }));
});

test('dropdown options filter the gallery live and their buttons count the picks', () => {
  const harness = createGalleryHarness({ withDropdowns: true });
  initializeGalleryApp({ documentObj: harness.documentObj, runtime: harness.runtime, windowObj: harness.windowObj });
  const { filterDropdowns } = harness.elements;
  const { tags, tools } = harness.dropdowns;

  assert.equal(tags.summary.textContent, '');
  assert.equal(tags.toggle.getAttribute('aria-label'), 'Tags');
  filterDropdowns.dispatch('click', { target: tags.options[0] });
  filterDropdowns.dispatch('click', { target: tools.options[0] });
  assert.match(harness.windowObj.location.search, /tag=finance/);
  assert.match(harness.windowObj.location.search, /tool=claude/);
  assert.equal(tags.summary.textContent, '1');
  assert.equal(tags.toggle.getAttribute('aria-label'), 'Tags, 1 selected');
  assert.equal(tags.options[0].getAttribute('aria-pressed'), 'true');
  assert.equal(tags.options[0].classList.contains('is-active'), true);

  filterDropdowns.dispatch('click', { target: tags.clear });
  assert.doesNotMatch(harness.windowObj.location.search, /tag=/);
  assert.match(harness.windowObj.location.search, /tool=claude/, 'clear only resets its own group');
  assert.equal(tags.summary.textContent, '');
  assert.equal(harness.documentObj.activeElement, tags.clear);
});

test('a long panel search shows only the options that match and resets when the panel reopens', () => {
  const harness = createGalleryHarness({ withDropdowns: true });
  initializeGalleryApp({ documentObj: harness.documentObj, runtime: harness.runtime, windowObj: harness.windowObj });
  const { filterDropdowns } = harness.elements;
  const { toggle, panel, options, searchBox } = harness.dropdowns.tags;

  filterDropdowns.dispatch('click', { target: toggle });
  searchBox.value = ' FIN ';
  filterDropdowns.dispatch('input', { target: searchBox });
  assert.deepEqual(options.map((option) => option.hidden), [false, true]);

  const stray = new FakeElement({ tagName: 'INPUT' });
  filterDropdowns.dispatch('input', { target: stray });
  const loose = new FakeElement({ tagName: 'INPUT' });
  loose.setAttribute('data-filter-panel-search', '');
  assert.doesNotThrow(() => filterDropdowns.dispatch('input', { target: loose }), 'a search box outside a panel is ignored');

  panel.close();
  filterDropdowns.dispatch('click', { target: toggle });
  assert.equal(searchBox.value, '');
  assert.deepEqual(options.map((option) => option.hidden), [false, false]);
});

test('widening past the dropdown layout closes an open panel', () => {
  const harness = createGalleryHarness({ withDropdowns: true });
  initializeGalleryApp({ documentObj: harness.documentObj, runtime: harness.runtime, windowObj: harness.windowObj });
  const { filterDropdowns } = harness.elements;
  const { toggle, panel } = harness.dropdowns.tags;

  filterDropdowns.dispatch('click', { target: toggle });
  harness.setNotepadLayout(true);
  assert.equal(panel.open, true);
  harness.setNotepadLayout(false);
  assert.equal(panel.open, false);
});

test('a dropdown button whose panel is missing does nothing', () => {
  const harness = createGalleryHarness({ withDropdowns: true });
  initializeGalleryApp({ documentObj: harness.documentObj, runtime: harness.runtime, windowObj: harness.windowObj });
  const orphan = new FakeElement({ tagName: 'BUTTON', classes: ['filter-dropdown-toggle'] });
  orphan.parentElement = harness.elements.filterDropdowns;
  assert.doesNotThrow(() => harness.elements.filterDropdowns.dispatch('click', { target: orphan }));
  assert.equal(orphan.getAttribute('aria-expanded'), null);

test('a page turn scrolls the book back into view only when its top is above the screen', () => {
  const harness = createGalleryHarness();
  initializeGalleryApp({ documentObj: harness.documentObj, runtime: harness.runtime, windowObj: harness.windowObj });
  let bookTop = 40;
  const bookShell = new FakeElement({ id: 'book-shell' });
  bookShell.getBoundingClientRect = () => ({ top: bookTop });
  const getElementById = harness.documentObj.getElementById;
  harness.documentObj.getElementById = (id) => (id === 'book-shell' ? bookShell : getElementById(id));
  harness.windowObj.scrollY = 900;

  harness.elements.pagination.dispatch('click', { target: createPageButton(harness, { page: 2 }) });
  assert.deepEqual(harness.scrollCalls, []);

  bookTop = -600;
  harness.elements.pagination.dispatch('click', { target: createPageButton(harness, { page: 1 }) });
  assert.deepEqual(harness.scrollCalls, [{ top: 288, behavior: 'smooth' }]);
});

test('the notepad shows one artifact per page and keeps the reader in place across a layout switch', () => {
  const harness = createGalleryHarness({ notepad: true, search: '?page=5' });
  initializeGalleryApp({ documentObj: harness.documentObj, runtime: harness.runtime, windowObj: harness.windowObj });
  assert.equal(harness.elements.grid.cards.length, 1);
  assert.match(harness.elements.galleryStatus.textContent, /page 5 of 13/);

  harness.setNotepadLayout(false);
  assert.equal(harness.elements.grid.cards.length, 4);
  assert.match(harness.elements.galleryStatus.textContent, /page 2 of 4/, 'the fifth artifact sits on book page 2');

  harness.setNotepadLayout(false);
  assert.match(harness.elements.galleryStatus.textContent, /page 2 of 4/, 'a change that keeps the layout leaves the page alone');

  harness.setNotepadLayout(true);
  assert.equal(harness.elements.grid.cards.length, 1);
  assert.match(harness.elements.galleryStatus.textContent, /page 5 of 13/);
});

test('notepad swipes turn the page up for next and down for previous', async () => {
  const harness = createGalleryHarness({ notepad: true, withSheet: true });
  initializeGalleryApp({ documentObj: harness.documentObj, runtime: harness.runtime, windowObj: harness.windowObj });
  const { sheet } = harness.book;
  /** @param {number} dx @param {number} dy @param {object} [down] */
  const swipe = (dx, dy, down = {}) => {
    sheet.dispatch('pointerdown', { isPrimary: true, clientX: 100, clientY: 500, ...down });
    sheet.dispatch('pointerup', { clientX: 100 + dx, clientY: 500 + dy });
  };
  const status = () => harness.elements.galleryStatus.textContent;

  swipe(0, -120);
  assert.match(status(), /page 2 of 13/);
  swipe(0, -120);
  assert.match(status(), /page 3 of 13/);
  swipe(0, 120);
  assert.match(status(), /page 2 of 13/);

  swipe(0, -20);
  swipe(200, -60);
  swipe(0, -120, { isPrimary: false });
  assert.match(status(), /page 2 of 13/, 'short, sideways, and second-finger moves do not turn');

  sheet.dispatch('pointerdown', { isPrimary: true, clientX: 100, clientY: 500 });
  sheet.dispatch('pointercancel');
  sheet.dispatch('pointerup', { clientX: 100, clientY: 300 });
  assert.match(status(), /page 2 of 13/, 'a cancelled pointer does not turn');

  swipe(0, 120);
  swipe(0, 120);
  assert.match(status(), /page 1 of 13/, 'there is no page before the first');

  swipe(0, -120);
  const card = harness.elements.grid.cards[0];
  harness.elements.grid.dispatch('click', { target: card });
  await settleMicrotasks();
  assert.equal(harness.elements.detailOverlay.classList.contains('visible'), false, 'the click a swipe leaves behind does not open the card');

  harness.setNotepadLayout(false);
  swipe(0, -120);
  assert.match(status(), /page 1 of 4/, 'the book takes no swipes');
});

test('the notepad blocks native drags so a mouse swipe on the photo or link still turns', () => {
  const harness = createGalleryHarness({ notepad: true, withSheet: true });
  initializeGalleryApp({ documentObj: harness.documentObj, runtime: harness.runtime, windowObj: harness.windowObj });
  assert.equal(harness.book.sheet.dispatch('dragstart').defaultPrevented, true);
  harness.setNotepadLayout(false);
  assert.equal(harness.book.sheet.dispatch('dragstart').defaultPrevented, false);
});
});

