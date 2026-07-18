import assert from 'node:assert/strict';
import test from 'node:test';

import { initSectionNav } from '../../../js/modules/section-nav.js';

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
  globalThis.window = {
    matchMedia() { return { matches: reduceMotion }; }
  };
  globalThis.document = {
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
  return { observers, registry, restore };
}

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
    assert.equal(observers[0].options.threshold, 0.3);
    assert.equal(observers[0].targets.length, SECTIONS.length);
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
