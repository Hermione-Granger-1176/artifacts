import assert from 'node:assert/strict';
import test from 'node:test';

import { initSectionNav, renderSectionNav } from '../../../js/modules/section-nav.js';

const SECTIONS = [
  { id: 'sec-alpha', label: 'Alpha' },
  { id: 'sec-beta', label: 'Beta' },
  { id: 'sec-gamma', label: 'Gamma' },
  { id: 'sec-delta', label: 'Delta' }
];

function makeElement(tagName = 'div') {
  const classes = new Set();
  const attrs = {};
  const listeners = {};
  return {
    tagName,
    id: '',
    className: '',
    type: '',
    textContent: '',
    children: [],
    style: {},
    scrolledTo: false,
    rectTop: 0,
    getBoundingClientRect() { return { top: this.rectTop }; },
    classList: {
      contains(className) { return classes.has(className); },
      toggle(className, force) {
        const next = force ?? !classes.has(className);
        next ? classes.add(className) : classes.delete(className);
        return next;
      }
    },
    addEventListener(type, handler) {
      listeners[type] = listeners[type] || [];
      listeners[type].push(handler);
    },
    append(...nodes) { this.children.push(...nodes); },
    appendChild(child) { this.children.push(child); return child; },
    getAttribute(name) { return attrs[name] ?? null; },
    setAttribute(name, value) { attrs[name] = value; },
    scrollIntoView(options) {
      this.scrolledTo = true;
      this.scrollBehavior = options?.behavior;
    },
    _listeners: listeners
  };
}

function setupNavMocks({
  anchorIds = ['nav-nodes', 'nav-fill', 'nav-label'],
  withSections = true,
  reduceMotion = false
} = {}) {
  const registry = {};
  for (const id of anchorIds) {
    registry[id] = makeElement();
  }
  if (withSections) {
    for (const section of SECTIONS) {
      const target = makeElement('section');
      target.id = section.id;
      registry[section.id] = target;
    }
  }

  const observers = [];
  const originalDocument = globalThis.document;
  const originalWindow = globalThis.window;
  const originalObserver = globalThis.IntersectionObserver;
  const windowListeners = {};
  globalThis.window = {
    innerHeight: 800,
    scrollY: 0,
    matchMedia() { return { matches: reduceMotion }; },
    addEventListener(type, handler, options) {
      windowListeners[type] = { handler, options };
    }
  };
  globalThis.document = {
    documentElement: { scrollHeight: 10000 },
    getElementById(id) { return registry[id] ?? null; },
    createElement(tagName) { return makeElement(tagName); }
  };
  globalThis.IntersectionObserver = class {
    constructor(callback, options) {
      this.callback = callback;
      this.options = options;
      this.targets = [];
      observers.push(this);
    }

    observe(target) { this.targets.push(target); }
  };

  const restore = () => {
    if (originalDocument) globalThis.document = originalDocument; else delete globalThis.document;
    if (originalWindow) globalThis.window = originalWindow; else delete globalThis.window;
    if (originalObserver) globalThis.IntersectionObserver = originalObserver;
    else delete globalThis.IntersectionObserver;
  };
  return { observers, registry, windowListeners, restore };
}

test('renderSectionNav injects the shared skeleton into an empty mount', () => {
  const mount = { childElementCount: 0, innerHTML: '' };
  renderSectionNav(mount);
  assert.match(mount.innerHTML, /class="section-nav"/);
  assert.match(mount.innerHTML, /id="nav-fill"/);
  assert.match(mount.innerHTML, /id="nav-nodes"/);
  assert.match(mount.innerHTML, /id="nav-label"/);
});

test('renderSectionNav is a no-op for a missing or already-filled mount', () => {
  assert.doesNotThrow(() => renderSectionNav(null));
  const filled = { childElementCount: 3, innerHTML: 'existing' };
  renderSectionNav(filled);
  assert.equal(filled.innerHTML, 'existing');
});

test('section nav builds one numbered node per section and starts on the first', () => {
  const { observers, registry, restore } = setupNavMocks();
  try {
    initSectionNav(SECTIONS);

    const nodes = registry['nav-nodes'].children;
    assert.equal(nodes.length, SECTIONS.length);
    assert.equal(nodes[0].className, 'section-nav-node');
    assert.equal(nodes[0].getAttribute('aria-label'), 'Alpha');
    assert.equal(nodes[0].children[0].textContent, '1');
    assert.equal(nodes[0].children[1].textContent, 'Alpha');
    assert.ok(nodes[0].classList.contains('active'));
    assert.ok(!nodes[1].classList.contains('active'));
    assert.equal(registry['nav-fill'].style.width, '0%');
    assert.equal(registry['nav-label'].textContent, 'Alpha');

    assert.equal(observers.length, 1);
    assert.equal(observers[0].options.threshold, 0);
    assert.equal(observers[0].targets.length, SECTIONS.length);
  } finally {
    restore();
  }
});

test('discovers sections from data-nav-label markup when no list is passed', () => {
  const { registry, restore } = setupNavMocks();
  try {
    const sectionEls = SECTIONS.map((section) => {
      const el = registry[section.id];
      el.setAttribute('data-nav-label', section.label);
      return el;
    });
    globalThis.document.querySelectorAll = (sel) =>
      sel === '[data-nav-label]' ? sectionEls : [];

    initSectionNav();

    const nodes = registry['nav-nodes'].children;
    assert.equal(nodes.length, SECTIONS.length);
    assert.equal(nodes[0].getAttribute('aria-label'), 'Alpha');
    assert.equal(registry['nav-label'].textContent, 'Alpha');
  } finally {
    restore();
  }
});

test('discovery skips elements missing an id or a label value', () => {
  const { registry, restore } = setupNavMocks();
  try {
    const anonymous = makeElement('section');
    anonymous.setAttribute('data-nav-label', 'No Anchor');
    const unlabeled = registry['sec-beta'];
    unlabeled.setAttribute('data-nav-label', '');
    const labeled = registry['sec-alpha'];
    labeled.setAttribute('data-nav-label', 'Alpha');
    globalThis.document.querySelectorAll = () => [anonymous, unlabeled, labeled];

    initSectionNav();

    assert.equal(registry['nav-nodes'].children.length, 1);
    assert.equal(registry['nav-label'].textContent, 'Alpha');
  } finally {
    restore();
  }
});

test('section nav honors custom camelCase anchor ids', () => {
  const { registry, restore } = setupNavMocks({ anchorIds: ['navNodes', 'navFill', 'navLabel'] });
  try {
    initSectionNav(SECTIONS, { nodesId: 'navNodes', fillId: 'navFill', labelId: 'navLabel' });
    assert.equal(registry['navNodes'].children.length, SECTIONS.length);
    assert.equal(registry['navLabel'].textContent, 'Alpha');
  } finally {
    restore();
  }
});

test('clicking a node scrolls its section into view smoothly', () => {
  const { registry, restore } = setupNavMocks();
  try {
    initSectionNav(SECTIONS);

    registry['nav-nodes'].children[2]._listeners.click[0]();
    assert.ok(registry['sec-gamma'].scrolledTo);
    assert.equal(registry['sec-gamma'].scrollBehavior, 'smooth');
    assert.ok(!registry['sec-alpha'].scrolledTo);
  } finally {
    restore();
  }
});

test('clicking a node uses an instant scroll when reduced motion is preferred', () => {
  const { registry, restore } = setupNavMocks({ reduceMotion: true });
  try {
    initSectionNav(SECTIONS);

    registry['nav-nodes'].children[0]._listeners.click[0]();
    assert.equal(registry['sec-alpha'].scrollBehavior, 'auto');
  } finally {
    restore();
  }
});

test('intersection updates mark earlier nodes done and move the fill and label', () => {
  const { observers, registry, restore } = setupNavMocks();
  try {
    initSectionNav(SECTIONS);

    registry['sec-gamma'].rectTop = 100;
    observers[0].callback([
      { isIntersecting: false, target: registry['sec-alpha'] },
      { isIntersecting: true, target: registry['sec-gamma'] },
      { isIntersecting: true, target: { id: 'unrelated-section' } }
    ]);

    const nodes = registry['nav-nodes'].children;
    assert.ok(nodes[0].classList.contains('done'));
    assert.ok(nodes[1].classList.contains('done'));
    assert.ok(nodes[2].classList.contains('active'));
    assert.ok(!nodes[3].classList.contains('active'));
    assert.equal(registry['nav-label'].textContent, 'Gamma');
    assert.ok(registry['nav-fill'].style.width.startsWith('66.6'));
  } finally {
    restore();
  }
});

test('the last visible section past the scanline beats earlier visible ones', () => {
  const { observers, registry, restore } = setupNavMocks();
  try {
    initSectionNav(SECTIONS);

    // A short heading hovering above the viewport top and the tall card the
    // reader is actually looking at are both on screen; the card wins because
    // it is the later section whose top has passed the scanline (800 * 0.35).
    registry['sec-beta'].rectTop = -50;
    registry['sec-gamma'].rectTop = 60;
    observers[0].callback([
      { isIntersecting: true, target: registry['sec-beta'] },
      { isIntersecting: true, target: registry['sec-gamma'] }
    ]);
    assert.equal(registry['nav-label'].textContent, 'Gamma');

    // Once the card leaves, the heading is the only candidate again.
    observers[0].callback([
      { isIntersecting: false, target: registry['sec-gamma'] }
    ]);
    assert.equal(registry['nav-label'].textContent, 'Beta');
  } finally {
    restore();
  }
});

test('falls back to the first visible section when none has passed the scanline', () => {
  const { observers, registry, restore } = setupNavMocks();
  try {
    initSectionNav(SECTIONS);

    registry['sec-beta'].rectTop = 500;
    registry['sec-gamma'].rectTop = 700;
    observers[0].callback([
      { isIntersecting: true, target: registry['sec-beta'] },
      { isIntersecting: true, target: registry['sec-gamma'] }
    ]);
    assert.equal(registry['nav-label'].textContent, 'Beta');
  } finally {
    restore();
  }
});

test('keeps the current section when nothing is on screen', () => {
  const { observers, registry, restore } = setupNavMocks();
  try {
    initSectionNav(SECTIONS);

    registry['sec-beta'].rectTop = 100;
    observers[0].callback([
      { isIntersecting: true, target: registry['sec-beta'] }
    ]);
    assert.equal(registry['nav-label'].textContent, 'Beta');

    observers[0].callback([
      { isIntersecting: false, target: registry['sec-beta'] }
    ]);
    assert.equal(registry['nav-label'].textContent, 'Beta');
  } finally {
    restore();
  }
});

test('scrolling re-runs the position check between enter and leave events', () => {
  const { observers, registry, windowListeners, restore } = setupNavMocks();
  try {
    initSectionNav(SECTIONS);

    registry['sec-beta'].rectTop = 100;
    registry['sec-gamma'].rectTop = 600;
    observers[0].callback([
      { isIntersecting: true, target: registry['sec-beta'] },
      { isIntersecting: true, target: registry['sec-gamma'] }
    ]);
    assert.equal(registry['nav-label'].textContent, 'Beta');

    // The card's top crosses the scanline without any enter/leave firing; the
    // passive scroll listener picks up the change.
    registry['sec-gamma'].rectTop = 200;
    assert.equal(windowListeners.scroll.options.passive, true);
    windowListeners.scroll.handler();
    assert.equal(registry['nav-label'].textContent, 'Gamma');
  } finally {
    restore();
  }
});

test('pins the deepest visible section at the bottom of the page', () => {
  const { observers, registry, windowListeners, restore } = setupNavMocks();
  try {
    initSectionNav(SECTIONS);

    // The page has run out of scroll but the last section's top never reaches
    // the scanline; the bottom pin promotes it anyway (via the resize listener
    // here, which shares the same position check as scroll).
    registry['sec-gamma'].rectTop = -100;
    registry['sec-delta'].rectTop = 500;
    observers[0].callback([
      { isIntersecting: true, target: registry['sec-gamma'] },
      { isIntersecting: true, target: registry['sec-delta'] }
    ]);
    assert.equal(registry['nav-label'].textContent, 'Gamma');

    globalThis.document.documentElement.scrollHeight = 1600;
    globalThis.window.scrollY = 800;
    windowListeners.resize.handler();
    assert.equal(registry['nav-label'].textContent, 'Delta');
    assert.equal(registry['nav-fill'].style.width, '100%');
  } finally {
    restore();
  }
});

test('sections without a matching element are skipped by the observer', () => {
  const { observers, registry, restore } = setupNavMocks();
  try {
    delete registry['sec-delta'];
    initSectionNav(SECTIONS);
    assert.equal(observers[0].targets.length, SECTIONS.length - 1);
  } finally {
    restore();
  }
});

test('section nav is a no-op for missing anchors or empty sections', () => {
  const { observers, registry, restore } = setupNavMocks({ anchorIds: ['nav-fill', 'nav-label'] });
  try {
    assert.doesNotThrow(() => initSectionNav(SECTIONS));
    assert.equal(observers.length, 0);

    registry['nav-nodes'] = makeElement();
    assert.doesNotThrow(() => initSectionNav([]));
    assert.equal(registry['nav-nodes'].children.length, 0);
  } finally {
    restore();
  }
});

test('section nav still renders nodes when IntersectionObserver is unavailable', () => {
  const { registry, restore } = setupNavMocks({ withSections: false });
  try {
    delete globalThis.IntersectionObserver;
    assert.doesNotThrow(() => initSectionNav(SECTIONS));
    assert.equal(registry['nav-nodes'].children.length, SECTIONS.length);
    assert.equal(registry['nav-label'].textContent, 'Alpha');
  } finally {
    restore();
  }
});

test('section nav skips observing section targets that are not in the document', () => {
  const { observers, restore } = setupNavMocks({ withSections: false });
  try {
    initSectionNav(SECTIONS);
    assert.equal(observers[0].targets.length, 0);
  } finally {
    restore();
  }
});
