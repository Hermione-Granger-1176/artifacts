import assert from 'node:assert/strict';
import test from 'node:test';

import { initSectionNav, renderSectionNav, scrollProgress, sectionAnchors } from '../../../js/modules/section-nav.js';

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
    // Like the DOM, className and classList read and write one set of classes.
    get className() { return [...classes].join(' '); },
    set className(value) {
      classes.clear();
      String(value).split(/\s+/).filter(Boolean).forEach((name) => classes.add(name));
    },
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
    SECTIONS.forEach((section, index) => {
      const target = makeElement('section');
      target.id = section.id;
      target.rectTop = index * 1000;
      registry[section.id] = target;
    });
  }

  const observers = [];
  const originalDocument = globalThis.document;
  const originalWindow = globalThis.window;
  const originalObserver = globalThis.ResizeObserver;
  const windowListeners = {};
  const frames = [];
  globalThis.window = {
    innerHeight: 800,
    scrollY: 0,
    requestAnimationFrame(callback) { frames.push(callback); return frames.length; },
    matchMedia() { return { matches: reduceMotion }; },
    addEventListener(type, handler, options) {
      windowListeners[type] = { handler, options };
    }
  };
  globalThis.document = {
    documentElement: { scrollHeight: 10000 },
    body: makeElement('body'),
    getElementById(id) { return registry[id] ?? null; },
    createElement(tagName) { return makeElement(tagName); }
  };
  globalThis.ResizeObserver = class {
    constructor(callback) {
      this.callback = callback;
      this.targets = [];
      observers.push(this);
    }

    observe(target) { this.targets.push(target); }
  };

  const restore = () => {
    if (originalDocument) globalThis.document = originalDocument; else delete globalThis.document;
    if (originalWindow) globalThis.window = originalWindow; else delete globalThis.window;
    if (originalObserver) globalThis.ResizeObserver = originalObserver;
    else delete globalThis.ResizeObserver;
  };
  // Run the animation-frame callbacks queued so far, as one frame would.
  const flushFrames = () => frames.splice(0).forEach((callback) => callback());
  return { observers, registry, windowListeners, flushFrames, restore };
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
    assert.equal(nodes[0].className, 'section-nav-node active', 'created active, so it never fades in on load');
    assert.equal(nodes[1].className, 'section-nav-node');
    assert.equal(nodes[0].getAttribute('aria-label'), 'Alpha');
    assert.equal(nodes[0].children[0].textContent, '1');
    assert.equal(nodes[0].children[1].textContent, 'Alpha');
    assert.ok(nodes[0].classList.contains('active'));
    assert.ok(!nodes[1].classList.contains('active'));
    assert.equal(registry['nav-fill'].style.scale, '0 1');
    assert.equal(registry['nav-label'].textContent, 'Alpha');

    assert.equal(observers.length, 1);
    assert.deepEqual(observers[0].targets, [globalThis.document.body], 'layout changes re-measure the sections');
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

// Scroll the mock page: section rects move up by the scroll distance.
function scrollMockTo(registry, windowListeners, flushFrames, scrollY) {
  const delta = scrollY - globalThis.window.scrollY;
  globalThis.window.scrollY = scrollY;
  for (const section of SECTIONS) {
    if (registry[section.id]) registry[section.id].rectTop -= delta;
  }
  windowListeners.scroll.handler();
  flushFrames();
}

test('sectionAnchors activates a section when its top reaches the scanline', () => {
  assert.deepEqual(sectionAnchors([100, 1000, 2000], 300, 5000), [0, 700, 1700]);
  assert.deepEqual(sectionAnchors([], 300, 5000), []);
});

test('sectionAnchors splits the last stretch of scrolling among the sections the page cannot reach', () => {
  assert.deepEqual(sectionAnchors([0, 1000, 1500, 1800], 300, 1000), [0, 700, 800, 900]);
  assert.deepEqual(sectionAnchors([0, 2000, 3000], 300, 900), [0, 300, 600]);
  assert.deepEqual(sectionAnchors([400], 300, 0), [100], 'a single section is left alone');
});

test('scrollProgress is the active section plus the way to the next one', () => {
  const anchors = [0, 700, 1700];
  assert.equal(scrollProgress(anchors, -50), 0);
  assert.equal(scrollProgress(anchors, 350), 0.5);
  assert.equal(scrollProgress(anchors, 700), 1);
  assert.equal(scrollProgress(anchors, 1200), 1.5);
  assert.equal(scrollProgress(anchors, 1700), 2);
  assert.equal(scrollProgress(anchors, 9000), 2);
  assert.equal(scrollProgress([0, 0, 600], 0), 1, 'a zero-length stretch is passed at once');
  assert.equal(scrollProgress([], 0), 0);
});

test('scrolling moves the fill smoothly and switches the active node at each section', () => {
  const { registry, windowListeners, flushFrames, restore } = setupNavMocks();
  try {
    initSectionNav(SECTIONS);
    const nodes = registry['nav-nodes'].children;
    const fill = registry['nav-fill'].style;

    // Scanline at 280px: Beta becomes active at scrollY 720, Gamma at 1720.
    scrollMockTo(registry, windowListeners, flushFrames, 360);
    assert.equal(fill.scale, `${0.5 / 3} 1`);
    assert.equal(registry['nav-label'].textContent, 'Alpha');

    scrollMockTo(registry, windowListeners, flushFrames, 1220);
    assert.equal(fill.scale, `${1.5 / 3} 1`);
    assert.ok(nodes[0].classList.contains('done'));
    assert.ok(nodes[1].classList.contains('active'));
    assert.ok(!nodes[2].classList.contains('done'));
    assert.equal(registry['nav-label'].textContent, 'Beta');

    scrollMockTo(registry, windowListeners, flushFrames, 2720);
    assert.equal(fill.scale, '1 1');
    assert.ok(nodes[3].classList.contains('active'));
    assert.equal(registry['nav-label'].textContent, 'Delta');
  } finally {
    restore();
  }
});

test('the last section is reached before the bottom of a page too short to scroll it to the scanline', () => {
  const { registry, windowListeners, flushFrames, restore } = setupNavMocks();
  try {
    globalThis.document.documentElement.scrollHeight = 3000;
    initSectionNav(SECTIONS);

    // Delta cannot reach the scanline, so it takes the second half of the
    // stretch after Gamma (1720 to 2199) and holds it a few pixels short of the bottom.
    scrollMockTo(registry, windowListeners, flushFrames, 1900);
    assert.equal(registry['nav-label'].textContent, 'Gamma');
    scrollMockTo(registry, windowListeners, flushFrames, 2190);
    assert.equal(registry['nav-fill'].style.scale, '1 1');
    assert.equal(registry['nav-label'].textContent, 'Delta');
  } finally {
    restore();
  }
});

test('a layout change re-measures the sections once per frame', () => {
  const { observers, registry, windowListeners, flushFrames, restore } = setupNavMocks();
  try {
    initSectionNav(SECTIONS);
    let reads = 0;
    const read = registry['sec-beta'].getBoundingClientRect;
    registry['sec-beta'].getBoundingClientRect = function () { reads += 1; return read.call(this); };

    scrollMockTo(registry, windowListeners, flushFrames, 100);
    assert.equal(reads, 0, 'scrolling reads no layout');

    // Beta moves down 500px: it now becomes active 500px later.
    registry['sec-beta'].rectTop += 500;
    observers[0].callback();
    windowListeners.resize.handler();
    flushFrames();
    assert.equal(reads, 1);
    scrollMockTo(registry, windowListeners, flushFrames, 1000);
    assert.equal(registry['nav-label'].textContent, 'Alpha');
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

test('section nav works without ResizeObserver and leaves out sections missing from the page', () => {
  const { registry, windowListeners, flushFrames, restore } = setupNavMocks();
  try {
    delete globalThis.ResizeObserver;
    delete registry['sec-gamma'];
    initSectionNav(SECTIONS);
    assert.deepEqual(registry['nav-nodes'].children.map((node) => node.getAttribute('aria-label')), ['Alpha', 'Beta', 'Delta']);
    windowListeners.resize.handler();
    flushFrames();
    assert.equal(registry['nav-label'].textContent, 'Alpha');
  } finally {
    restore();
  }
});

test('scrolling within a section leaves the nodes and label alone', () => {
  const { registry, windowListeners, flushFrames, restore } = setupNavMocks();
  try {
    initSectionNav(SECTIONS);
    scrollMockTo(registry, windowListeners, flushFrames, 800);
    assert.equal(registry['nav-label'].textContent, 'Beta');

    let writes = 0;
    let label = registry['nav-label'].textContent;
    Object.defineProperty(registry['nav-label'], 'textContent', {
      get: () => label,
      set: (value) => { writes += 1; label = value; }
    });
    for (const node of registry['nav-nodes'].children) {
      const toggle = node.classList.toggle;
      node.classList.toggle = (...args) => { writes += 1; return toggle.apply(node.classList, args); };
    }

    scrollMockTo(registry, windowListeners, flushFrames, 900);
    scrollMockTo(registry, windowListeners, flushFrames, 900);
    assert.equal(writes, 0);
  } finally {
    restore();
  }
});
