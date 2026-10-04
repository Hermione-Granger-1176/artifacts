import test from 'node:test';
import assert from 'node:assert/strict';

import { createBookScene } from '../../../js/modules/gallery/book-scene.js';

class FakeClassList {
  constructor(owner) {
    this.owner = owner;
    this.values = new Set();
    this.history = [];
  }

  set(value) {
    this.values = new Set(String(value).split(/\s+/).filter(Boolean));
  }

  add(...names) {
    names.forEach((name) => {
      this.values.add(name);
      this.history.push(`add:${name}`);
    });
  }

  remove(...names) {
    names.forEach((name) => {
      this.values.delete(name);
      this.history.push(`remove:${name}`);
    });
  }

  contains(name) {
    return this.values.has(name);
  }
}

class FakeAnimation {
  constructor(env, options) {
    this.cancelled = false;
    this.finished = new Promise((resolve, reject) => {
      this.resolve = resolve;
      this.reject = reject;
    });
    if (options.manual) {
      return;
    }
    env.setTimeout(() => {
      if (!this.cancelled) {
        this.resolve();
      }
    }, (options.duration || 0) + (options.delay || 0));
  }

  cancel() {
    this.cancelled = true;
    this.reject(new DOMException('cancelled', 'AbortError'));
    this.finished.catch(() => undefined);
  }
}

class FakeElement {
  constructor(env, id = '', className = '') {
    this.env = env;
    this.id = id;
    this.classList = new FakeClassList(this);
    this.classList.set(className);
    this.dataset = {};
    this.attributes = {};
    this.children = [];
    this.parent = null;
    this.listeners = new Map();
    this.animateCalls = [];
    this.style = {
      props: {},
      setProperty(name, value) {
        this.props[name] = value;
      }
    };
    this.rect = { left: 0, top: 0, width: 100, height: 100 };
    this.captured = new Set();
    this.inert = false;
    this.throwOnCapture = false;
  }

  get className() {
    return [...this.classList.values].join(' ');
  }

  set className(value) {
    this.classList.set(value);
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  appendChild(child) {
    child.parent = this;
    this.children.push(child);
    return child;
  }

  remove() {
    if (this.parent) {
      this.parent.children = this.parent.children.filter((child) => child !== this);
      this.parent = null;
    }
  }

  cloneNode() {
    const clone = new FakeElement(this.env, '', this.className);
    clone.clonedFrom = this;
    return clone;
  }

  matches(selector) {
    if (selector.startsWith('.')) {
      return this.classList.contains(selector.slice(1));
    }
    return false;
  }

  closest(selector) {
    for (let node = this; node; node = node.parent) {
      if (node.matches(selector)) {
        return node;
      }
    }
    return null;
  }

  querySelectorAll(selector) {
    const found = [];
    for (const child of this.children) {
      if (child.matches(selector)) {
        found.push(child);
      }
      found.push(...child.querySelectorAll(selector));
    }
    return found;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  getBoundingClientRect() {
    return this.rect;
  }

  animate(keyframes, options) {
    const animation = new FakeAnimation(this.env, options);
    this.animateCalls.push({ animation, keyframes, options });
    if (this.env.animateError) {
      throw this.env.animateError;
    }
    return animation;
  }

  addEventListener(type, handler) {
    const handlers = this.listeners.get(type) || [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  removeEventListener(type, handler) {
    this.listeners.set(type, (this.listeners.get(type) || []).filter((entry) => entry !== handler));
  }

  listenerCount(type) {
    return (this.listeners.get(type) || []).length;
  }

  dispatch(type, overrides = {}) {
    const event = {
      type,
      target: this,
      pointerId: 1,
      button: 0,
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      ...overrides
    };
    for (const handler of [...(this.listeners.get(type) || [])]) {
      handler(event);
    }
    return event;
  }

  setPointerCapture(pointerId) {
    if (this.throwOnCapture) {
      throw new DOMException('inactive pointer', 'InvalidStateError');
    }
    this.captured.add(pointerId);
  }

  hasPointerCapture(pointerId) {
    return this.captured.has(pointerId);
  }

  releasePointerCapture(pointerId) {
    this.captured.delete(pointerId);
  }
}

const GRID_RECT = { left: 100, top: 0, width: 1000, height: 800 };
const RIGHT_EDGE_X = 1090;
const CENTER_X = 600;

/** Build a fake book, page model, and clock. Pages 1 to `pageCount`, shown page starts at 1. */
function createHarness({
  includeCover = true,
  includeGrid = true,
  includeShell = true,
  includeSheet = true,
  innerWidth = 1280,
  open = false,
  pageCount = 5,
  reducedMotion = false,
  withPages = true,
  withOnError = true,
  withMotion = true
} = {}) {
  const env = {
    now: 0,
    timers: [],
    frames: [],
    nextId: 1,
    animateError: null,
    setTimeout(callback, ms) {
      const id = env.nextId;
      env.nextId += 1;
      env.timers.push({ id, callback, at: env.now + ms });
      return id;
    },
    requestAnimationFrame(callback) {
      const id = env.nextId;
      env.nextId += 1;
      env.frames.push({ id, callback });
      return id;
    },
    cancelAnimationFrame(id) {
      env.frames = env.frames.filter((frame) => frame.id !== id);
    }
  };

  const elements = new Map();
  const make = (id, className = '') => {
    const element = new FakeElement(env, id, className);
    if (id) {
      elements.set(id, element);
    }
    return element;
  };

  const shell = includeShell ? make('book-shell') : null;
  const sheet = includeSheet ? make('book-sheet') : null;
  const cover = includeCover ? make('book-cover') : null;
  const grid = includeGrid ? make('artifacts-grid') : null;
  if (sheet) {
    sheet.rect = GRID_RECT;
    for (const className of ['book-shadow', 'book-cast-left', 'book-cast-right', 'book-inner']) {
      sheet.appendChild(new FakeElement(env, '', className));
    }
  }
  if (cover) {
    cover.appendChild(new FakeElement(env, '', 'book-ribbon'));
    cover.appendChild(new FakeElement(env, '', 'book-cover-shade'));
    cover.appendChild(new FakeElement(env, '', 'book-endpaper'));
  }
  const surface = sheet?.querySelector('.book-inner');
  if (grid) {
    grid.rect = GRID_RECT;
    grid.appendChild(new FakeElement(env, '', 'artifact-page-left'));
    grid.appendChild(new FakeElement(env, '', 'artifact-page-right'));
    for (const page of grid.children) {
      page.appendChild(new FakeElement(env, '', 'artifact-card'));
      page.appendChild(new FakeElement(env, '', 'artifact-card'));
    }
  }
  if (shell && open) {
    shell.dataset.sceneIntro = 'open';
  }

  const windowListeners = new Map();
  const windowObj = {
    innerWidth,
    matchMedia: () => ({ matches: reducedMotion }),
    setTimeout: env.setTimeout,
    requestAnimationFrame: env.requestAnimationFrame,
    cancelAnimationFrame: env.cancelAnimationFrame,
    addEventListener(type, handler) {
      const handlers = windowListeners.get(type) || [];
      handlers.push(handler);
      windowListeners.set(type, handlers);
    },
    resize(width) {
      windowObj.innerWidth = width;
      for (const handler of windowListeners.get('resize') || []) {
        handler({ type: 'resize' });
      }
    }
  };
  const created = [];
  const documentObj = {
    getElementById: (id) => elements.get(id) || null,
    createElement() {
      const element = new FakeElement(env, '');
      created.push(element);
      return element;
    }
  };

  const model = {
    shown: 1,
    selects: [],
    commits: [],
    builds: [],
    commitError: null,
    nullFaces: false,
    getShownPage: () => model.shown,
    getPageCount: () => pageCount,
    buildFaces(page) {
      model.builds.push(page);
      if (model.nullFaces) {
        return { left: null, right: null };
      }
      return {
        left: new FakeElement(env, '', `artifact-page-left built-${page}`),
        right: new FakeElement(env, '', `artifact-page-right built-${page}`)
      };
    },
    select(page) {
      model.selects.push(page);
    },
    commit(page) {
      model.commits.push(page);
      if (model.commitError) {
        throw model.commitError;
      }
      model.shown = page;
    }
  };

  const errors = [];
  const scene = createBookScene({
    documentObj,
    windowObj,
    motion: withMotion ? { prefersReducedMotion: () => windowObj.matchMedia().matches } : undefined,
    pages: withPages ? model : undefined,
    onError: withOnError ? (error) => errors.push(error) : undefined
  });

  const flush = async () => {
    for (let index = 0; index < 12; index += 1) {
      await Promise.resolve();
    }
  };

  /** Advance the fake clock, firing timers and animation frames in order. */
  async function advance(ms, step = 16) {
    await flush();
    for (let remaining = ms; remaining > 0; remaining -= step) {
      env.now += Math.min(step, remaining);
      const dueTimers = env.timers.filter((timer) => timer.at <= env.now);
      env.timers = env.timers.filter((timer) => timer.at > env.now);
      dueTimers.forEach((timer) => timer.callback());
      const frames = env.frames;
      env.frames = [];
      frames.forEach((frame) => frame.callback(env.now));
      await flush();
    }
  }

  const leafOf = () => sheet.children.find((child) => child.classList.contains('book-leaf'));
  const ghostOf = () => sheet.children.find((child) => child.classList.contains('book-ghost'));

  return {
    advance,
    cover,
    created,
    env,
    errors,
    ghostOf,
    grid,
    leafOf,
    model,
    scene,
    shell,
    sheet,
    surface,
    windowObj
  };
}

/** Open the book so page turns can animate. */
function openBook(harness) {
  harness.shell.dataset.sceneIntro = 'open';
}

function pointer(x, y = 400, overrides = {}) {
  return { clientX: x, clientY: y, ...overrides };
}

/** Start a drag from the right edge of the book and return the pointer-down event. */
function dragFromRight(harness, overrides = {}) {
  return harness.sheet.dispatch('pointerdown', pointer(RIGHT_EDGE_X, 400, overrides));
}

/* ------------------------------------------------------------------ */
/* Intro                                                              */
/* ------------------------------------------------------------------ */

test('startIntro resolves when the shell is missing and when the book is already open', async () => {
  const missing = createHarness({ includeShell: false });
  await missing.scene.startIntro();

  const opened = createHarness({ open: true });
  await opened.scene.startIntro();
  assert.equal(opened.cover.animateCalls.length, 0);
});

test('startIntro swings the cover open, reveals the left side mid-swing, and cleans up', async () => {
  const harness = createHarness();
  const intro = harness.scene.startIntro();

  assert.equal(harness.shell.dataset.sceneIntro, 'opening');
  assert.ok(harness.shell.classList.contains('is-opening'));
  assert.equal(harness.scene.startIntro(), intro, 'a second call shares the same intro');

  await harness.advance(500 + 520 + 100);
  const swing = harness.cover.animateCalls[0];
  assert.equal(swing.keyframes[0].transform, 'rotateY(0deg)');
  assert.equal(swing.keyframes.at(-1).transform, 'rotateY(-180deg)', 'a full 180 degree swing');
  assert.ok(swing.keyframes.every((frame) => frame.opacity === undefined), 'the cover never fades');
  assert.equal(harness.sheet.animateCalls[0].keyframes[0].transform, 'translateX(-25%)');
  assert.equal(harness.sheet.animateCalls[0].keyframes[1].transform, 'translateX(0)');
  assert.equal(swing.keyframes.length, 2, 'one smooth swing with no lift step');

  await harness.advance(500);
  assert.ok(!harness.shell.classList.contains('is-open'), 'the left half waits for the cover to land');

  await harness.advance(1000);
  await intro;

  assert.equal(harness.shell.dataset.sceneIntro, 'open');
  assert.ok(harness.shell.classList.contains('is-open'));
  assert.ok(!harness.shell.classList.contains('is-opening'));
  const allAnimations = [harness.cover, harness.sheet, ...harness.sheet.children, ...harness.cover.children]
    .flatMap((element) => element.animateCalls);
  assert.ok(allAnimations.length >= 6);
  assert.ok(allAnimations.every(({ animation }) => animation.cancelled), 'every animation is cancelled at the end');
  assert.equal(Object.keys(harness.cover.style.props).length, 0);
});

test('startIntro starts the cover swing while the ribbon is still sliding off', async () => {
  const harness = createHarness();
  const intro = harness.scene.startIntro();

  await harness.advance(500 + 250);
  assert.equal(harness.cover.animateCalls.length, 0, 'the ribbon moves first');

  await harness.advance(100);
  assert.equal(harness.cover.animateCalls.length, 1, 'the swing overlaps the end of the ribbon');
  const ribbon = harness.cover.querySelector('.book-ribbon').animateCalls[0];
  assert.ok(!ribbon.animation.cancelled);

  await harness.advance(3000);
  await intro;
  assert.ok(harness.shell.classList.contains('is-open'));
});

test('startIntro slides the ribbon off, then the cover lands carrying the first left page', async () => {
  const harness = createHarness();
  const leftPage = harness.grid.querySelector('.artifact-page-left');
  const cards = leftPage.querySelectorAll('.artifact-card');
  const endpaper = harness.cover.querySelector('.book-endpaper');

  const intro = harness.scene.startIntro();
  // Past the start delay and the ribbon, part way through the swing.
  await harness.advance(1500);
  const inside = endpaper.children[0];
  assert.ok(inside, 'the inside of the cover holds a copy of the left page');
  assert.equal(inside.clonedFrom, leftPage);
  assert.equal(inside.attributes['aria-hidden'], 'true');
  assert.equal(inside.inert, true);

  await harness.advance(3000);
  await intro;

  const ribbon = harness.cover.querySelector('.book-ribbon').animateCalls[0];
  assert.equal(ribbon.options.duration, 520);
  assert.ok(ribbon.keyframes.at(-1).opacity === 0);
  assert.ok(ribbon.animation.cancelled);
  // The live left page takes over as is: nothing fades or drops in.
  assert.equal(leftPage.animateCalls.length, 0);
  assert.ok(cards.every((card) => card.animateCalls.length === 0));
  assert.equal(endpaper.children.length, 0, 'the copy is removed once the book is open');
});

test('startIntro tolerates a book without a left page or a cover endpaper', async () => {
  const harness = createHarness();
  harness.cover.querySelector('.book-endpaper').remove();

  const intro = harness.scene.startIntro();
  await harness.advance(3000);
  await intro;
  assert.equal(harness.shell.dataset.sceneIntro, 'open');

  const noLeft = createHarness();
  noLeft.grid.children.forEach((child) => child.remove());
  const second = noLeft.scene.startIntro();
  await noLeft.advance(3000);
  await second;
  assert.equal(noLeft.shell.dataset.sceneIntro, 'open');
});

test('startIntro cross-fades the sheet for reduced motion without rotation', async () => {
  const harness = createHarness({ reducedMotion: true });
  const intro = harness.scene.startIntro();
  await harness.advance(1000);
  await intro;

  assert.equal(harness.cover.animateCalls.length, 0);
  assert.equal(harness.sheet.animateCalls.length, 2);
  for (const { keyframes } of harness.sheet.animateCalls) {
    assert.ok(keyframes.every((frame) => frame.transform === undefined));
  }
  assert.deepEqual(harness.sheet.animateCalls[0].keyframes, [{ opacity: 1 }, { opacity: 0 }]);
  assert.deepEqual(harness.sheet.animateCalls[1].keyframes, [{ opacity: 0 }, { opacity: 1 }]);
  assert.ok(harness.shell.classList.contains('is-open'));
  assert.equal(harness.shell.dataset.sceneIntro, 'open');
  assert.ok(harness.sheet.animateCalls.every(({ animation }) => animation.cancelled));
});

test('startIntro cross-fades on a mobile viewport', async () => {
  const harness = createHarness({ innerWidth: 390 });
  const intro = harness.scene.startIntro();
  await harness.advance(1000);
  await intro;

  assert.equal(harness.cover.animateCalls.length, 0);
  assert.equal(harness.sheet.animateCalls.length, 2);
  assert.ok(harness.shell.classList.contains('is-open'));
});

test('startIntro opens the shell even when cover, sheet, or grid markup is missing', async () => {
  for (const options of [{ includeCover: false }, { includeSheet: false }, { includeGrid: false }]) {
    const harness = createHarness(options);
    await harness.scene.startIntro();
    assert.equal(harness.shell.dataset.sceneIntro, 'open');
    assert.ok(harness.shell.classList.contains('is-open'));
    assert.ok(!harness.shell.classList.contains('is-opening'));
  }
});

test('startIntro cleans up and still opens the book when an animation throws', async () => {
  const harness = createHarness();
  harness.env.animateError = new Error('animate failed');
  const intro = harness.scene.startIntro();
  intro.catch(() => undefined);
  await harness.advance(2000);

  await assert.rejects(intro, /animate failed/);
  assert.equal(harness.shell.dataset.sceneIntro, 'open');
  assert.ok(harness.shell.classList.contains('is-open'));
  assert.ok(!harness.shell.classList.contains('is-opening'));
});

test('startIntro skips elements that cannot animate', async () => {
  const harness = createHarness();
  harness.cover.querySelector('.book-ribbon').animate = undefined;
  const intro = harness.scene.startIntro();
  await harness.advance(3000);
  await intro;
  assert.equal(harness.shell.dataset.sceneIntro, 'open');
});

test('a resize across the mobile breakpoint ends the intro in the open state', async () => {
  const harness = createHarness();
  const intro = harness.scene.startIntro();
  await harness.advance(200);

  harness.windowObj.resize(500);
  await harness.advance(2000);
  await intro;

  assert.equal(harness.shell.dataset.sceneIntro, 'open');
  assert.equal(harness.cover.animateCalls.length, 0, 'no swing is started after the abort');
  assert.ok(!harness.shell.classList.contains('is-opening'));
});

test('an abort mid-swing stops the remaining intro steps and cancels running animations', async () => {
  const harness = createHarness();
  const intro = harness.scene.startIntro();
  await harness.advance(500 + 520 + 200);
  assert.equal(harness.cover.animateCalls.length, 1);

  harness.windowObj.resize(500);
  assert.ok(harness.cover.animateCalls[0].animation.cancelled);
  await harness.advance(1500);
  await intro;

  assert.ok(harness.shell.classList.contains('is-open'));
  assert.equal(harness.grid.querySelector('.artifact-page-left').animateCalls.length, 0);
});

test('a resize that stays on the same side of the breakpoint leaves the intro alone', async () => {
  const harness = createHarness();
  const intro = harness.scene.startIntro();
  harness.windowObj.resize(1100);
  await harness.advance(3000);
  await intro;
  assert.equal(harness.cover.animateCalls.length, 1);
  assert.ok(!harness.cover.animateCalls[0].animation.cancelled === false);
});

/* ------------------------------------------------------------------ */
/* Page position                                                      */
/* ------------------------------------------------------------------ */

test('setPosition publishes stack depth and which corner peels apply', () => {
  const harness = createHarness();

  harness.scene.setPosition({ page: 1, totalPages: 4 });
  assert.equal(harness.sheet.style.props['--stack-left-n'], '1');
  assert.equal(harness.sheet.style.props['--stack-right-n'], '4');
  assert.equal(harness.sheet.dataset.hasPrevious, 'false');
  assert.equal(harness.sheet.dataset.hasNext, 'true');

  harness.scene.setPosition({ page: 4, totalPages: 4 });
  assert.equal(harness.sheet.style.props['--stack-left-n'], '4');
  assert.equal(harness.sheet.style.props['--stack-right-n'], '1');
  assert.equal(harness.sheet.dataset.hasPrevious, 'true');
  assert.equal(harness.sheet.dataset.hasNext, 'false');

  const noSheet = createHarness({ includeSheet: false });
  assert.doesNotThrow(() => noSheet.scene.setPosition({ page: 1, totalPages: 2 }));
});

/* ------------------------------------------------------------------ */
/* Instant paths                                                      */
/* ------------------------------------------------------------------ */

test('turnPage without a page model resolves without touching the DOM', async () => {
  const harness = createHarness({ open: true, withPages: false });
  await harness.scene.turnPage(2);
  harness.scene.cancelTurn();
  assert.equal(harness.created.length, 0);
});

test('turnPage selects and renders immediately when the book is missing or not yet open', async () => {
  const missing = createHarness({ includeSheet: false, open: true });
  await missing.scene.turnPage(3);
  assert.deepEqual(missing.model.selects, [3]);
  assert.deepEqual(missing.model.commits, [3]);

  const closed = createHarness();
  await closed.scene.turnPage(2);
  assert.deepEqual(closed.model.commits, [2]);
  assert.equal(closed.created.length, 0);
});

test('turnPage renders without animating when animation frames are unavailable', async () => {
  const harness = createHarness({ open: true });
  harness.windowObj.requestAnimationFrame = undefined;
  await harness.scene.turnPage(2);
  assert.deepEqual(harness.model.commits, [2]);

  const noCancel = createHarness({ open: true });
  noCancel.windowObj.cancelAnimationFrame = undefined;
  await noCancel.scene.turnPage(2);
  assert.deepEqual(noCancel.model.commits, [2]);
});

test('turnPage during the intro commits at once and keeps the latest request', async () => {
  const harness = createHarness({ open: true });
  harness.scene.turnPage(2);
  await harness.advance(100);
  assert.ok(harness.leafOf());

  harness.shell.dataset.sceneIntro = 'opening';
  await harness.scene.turnPage(4);
  assert.deepEqual(harness.model.commits, [4], 'the in-flight leaf is settled straight to the latest page');
  assert.equal(harness.leafOf(), undefined);
  assert.ok(!harness.sheet.classList.contains('is-turning'));
});

/* ------------------------------------------------------------------ */
/* Leaf turns                                                         */
/* ------------------------------------------------------------------ */

test('a next turn lifts one two-faced leaf and renders the page only when it lands', async () => {
  const harness = createHarness({ open: true });
  const liveRight = harness.grid.querySelector('.artifact-page-right');
  const done = harness.scene.turnPage(2);

  assert.deepEqual(harness.model.selects, [2], 'the page model hears about the request at once');
  await harness.advance(32);
  const leaf = harness.leafOf();
  const ghost = harness.ghostOf();
  assert.ok(leaf);
  assert.ok(harness.sheet.classList.contains('is-turning'));
  assert.equal(leaf.attributes['aria-hidden'], 'true');
  assert.equal(leaf.inert, true);
  assert.equal(ghost.className, 'book-ghost book-ghost-right');
  const [front, back] = leaf.children;
  assert.equal(front.className, 'book-leaf-face book-leaf-front');
  assert.equal(back.className, 'book-leaf-face book-leaf-back');
  assert.equal(front.children[0].clonedFrom, liveRight, 'the front face is the page that is turning');
  assert.match(back.children[0].className, /artifact-page-left built-2/, 'the back face is the new left page');
  assert.match(ghost.children[0].className, /artifact-page-right built-2/, 'the page underneath is the new right page');
  assert.match(leaf.style.transform, /^rotateY\(-?\d/);
  assert.deepEqual(harness.model.commits, [], 'the live pages are untouched mid-turn');

  await harness.advance(300);
  const angle = Number.parseFloat(leaf.style.transform.replace('rotateY(', ''));
  assert.ok(angle < -20 && angle > -170, `mid-turn angle ${angle}`);
  assert.ok(Number(front.children[1].style.opacity) > 0, 'the front shade darkens as the leaf lifts');
  assert.ok(Number(harness.sheet.querySelector('.book-cast-right').style.opacity) > 0, 'cast shadow under the leaf');

  await harness.advance(600);
  await done;
  assert.deepEqual(harness.model.commits, [2]);
  assert.equal(harness.leafOf(), undefined);
  assert.equal(harness.ghostOf(), undefined);
  assert.ok(!harness.sheet.classList.contains('is-turning'));
  assert.equal(harness.sheet.querySelector('.book-cast-right').style.opacity, '');
  assert.equal(harness.sheet.querySelector('.book-cast-left').style.opacity, '');
});

test('a next turn ends flat on the left side with the landing page shaded then clear', async () => {
  const harness = createHarness({ open: true });
  const done = harness.scene.turnPage(2);
  await harness.advance(32);
  const leaf = harness.leafOf();
  const backShade = leaf.children[1].children[1];

  await harness.advance(520);
  assert.ok(Number(harness.sheet.querySelector('.book-cast-left').style.opacity) >= 0);
  assert.ok(Number(backShade.style.opacity) >= 0);
  const late = Number.parseFloat(leaf.style.transform.replace('rotateY(', ''));
  assert.ok(late < -90, `late-turn angle ${late}`);

  await harness.advance(400);
  await done;
  assert.equal(leaf.style.transform, 'rotateY(-180deg)');
});

test('a previous turn is the physical reverse and keeps the live left page as the back face', async () => {
  const harness = createHarness({ open: true });
  harness.model.shown = 3;
  const liveLeft = harness.grid.querySelector('.artifact-page-left');
  const done = harness.scene.turnPage(2);
  await harness.advance(32);

  const leaf = harness.leafOf();
  const ghost = harness.ghostOf();
  const [front, back] = leaf.children;
  assert.equal(ghost.className, 'book-ghost book-ghost-left');
  assert.match(front.children[0].className, /artifact-page-right built-2/, 'the front face is the target right page');
  assert.equal(back.children[0].clonedFrom, liveLeft, 'the back face is the page that is turning');
  assert.ok(Number.parseFloat(leaf.style.transform.replace('rotateY(', '')) < -150, 'starts lying on the left');

  await harness.advance(300);
  const mid = Number.parseFloat(leaf.style.transform.replace('rotateY(', ''));
  assert.ok(mid > -150 && mid < -20, `mid-turn angle ${mid}`);
  assert.ok(Number(harness.sheet.querySelector('.book-cast-left').style.opacity) >= 0);

  await harness.advance(700);
  await done;
  assert.equal(leaf.style.transform, 'rotateY(0deg)');
  assert.deepEqual(harness.model.commits, [2]);
  assert.equal(harness.leafOf(), undefined);
});

test('jumping several pages is one leaf straight to the target', async () => {
  const harness = createHarness({ open: true });
  const done = harness.scene.turnPage(4);
  await harness.advance(1000);
  await done;

  assert.deepEqual(harness.model.builds, [4]);
  assert.deepEqual(harness.model.commits, [4]);
  assert.equal(harness.created.filter((element) => element.classList.contains('book-leaf')).length, 1);
});

test('turning to the page already shown does nothing', async () => {
  const harness = createHarness({ open: true });
  await harness.scene.turnPage(1);
  assert.deepEqual(harness.model.commits, []);
  assert.deepEqual(harness.model.builds, []);
  assert.equal(harness.created.length, 0);
});

test('rapid requests coalesce: the book finishes the turn it is on, then jumps to the latest page', async () => {
  const harness = createHarness({ open: true });
  const first = harness.scene.turnPage(2);
  await harness.advance(100);
  harness.scene.turnPage(3);
  harness.scene.turnPage(4);
  const last = harness.scene.turnPage(5);

  await harness.advance(3000);
  await Promise.all([first, last]);

  assert.deepEqual(harness.model.selects, [2, 3, 4, 5], 'every request is recorded');
  assert.deepEqual(harness.model.commits, [2, 5], 'one turn to 2, then one jump to 5');
  assert.deepEqual(harness.model.builds, [2, 5]);
  assert.equal(harness.model.shown, 5);
  assert.equal(harness.leafOf(), undefined);
  assert.ok(!harness.sheet.classList.contains('is-turning'));
});

test('a request that returns to the page the book started from turns back after landing', async () => {
  const harness = createHarness({ open: true });
  harness.scene.turnPage(2);
  await harness.advance(100);
  const back = harness.scene.turnPage(1);

  await harness.advance(3000);
  await back;
  assert.deepEqual(harness.model.commits, [2, 1]);
  assert.equal(harness.model.shown, 1);
});

test('a request that matches the page already shown is dropped from the queue', async () => {
  const harness = createHarness({ open: true });
  harness.model.shown = 2;
  const done = harness.scene.turnPage(2);
  await harness.advance(50);
  await done;
  assert.deepEqual(harness.model.commits, []);
  assert.equal(harness.created.length, 0);
});

test('turns cross-fade under reduced motion with no rotation and clear the opacity', async () => {
  const harness = createHarness({ open: true, reducedMotion: true });
  const done = harness.scene.turnPage(2);
  await harness.advance(60);

  assert.equal(harness.leafOf(), undefined);
  assert.ok(harness.sheet.classList.contains('is-turning'));
  assert.ok(Number(harness.surface.style.opacity) < 1);
  assert.deepEqual(harness.model.commits, []);

  await harness.advance(150);
  assert.deepEqual(harness.model.commits, [2], 'content swaps while the pages are hidden');
  await harness.advance(400);
  await done;
  assert.equal(harness.surface.style.opacity, '');
  assert.ok(!harness.sheet.classList.contains('is-turning'));
  assert.equal(harness.created.length, 0);
});

test('mobile turns use the fade timing and fall back to the grid when there is no inner surface', async () => {
  const harness = createHarness({ open: true, innerWidth: 390 });
  const done = harness.scene.turnPage(2);
  await harness.advance(500);
  await done;
  assert.deepEqual(harness.model.commits, [2]);
  assert.equal(harness.surface.style.opacity, '');

  const bare = createHarness({ open: true, innerWidth: 390 });
  bare.surface.remove();
  const bareDone = bare.scene.turnPage(2);
  await bare.advance(60);
  assert.ok(Number(bare.grid.style.opacity) < 1);
  await bare.advance(500);
  await bareDone;
  assert.equal(bare.grid.style.opacity, '');
});

test('a fade turn that is settled mid-flight still lands on the latest page', async () => {
  const harness = createHarness({ open: true, reducedMotion: true });
  harness.scene.turnPage(2);
  await harness.advance(60);
  harness.scene.turnPage(3);

  harness.windowObj.matchMedia = () => ({ matches: false });
  harness.shell.dataset.sceneIntro = 'opening';
  await harness.scene.turnPage(4);
  assert.deepEqual(harness.model.commits, [4]);
  assert.equal(harness.surface.style.opacity, '');
  assert.ok(!harness.sheet.classList.contains('is-turning'));
});

test('cancelTurn removes the leaf without rendering it and drops queued requests', async () => {
  const harness = createHarness({ open: true });
  harness.scene.turnPage(2);
  await harness.advance(100);
  harness.scene.turnPage(3);
  assert.ok(harness.leafOf());

  harness.scene.cancelTurn();
  assert.equal(harness.leafOf(), undefined);
  assert.equal(harness.ghostOf(), undefined);
  assert.ok(!harness.sheet.classList.contains('is-turning'));
  assert.equal(harness.sheet.querySelector('.book-cast-right').style.opacity, '');

  await harness.advance(2000);
  assert.deepEqual(harness.model.commits, []);

  harness.model.shown = 1;
  const next = harness.scene.turnPage(2);
  await harness.advance(1000);
  await next;
  assert.deepEqual(harness.model.commits, [2], 'the book is not stuck after a cancel');
});

test('cancelTurn with nothing in flight is a no-op', () => {
  const harness = createHarness({ open: true });
  assert.doesNotThrow(() => harness.scene.cancelTurn());
});

test('a resize across the mobile breakpoint mid-turn settles to the latest page with nothing left behind', async () => {
  const harness = createHarness({ open: true });
  harness.scene.turnPage(2);
  await harness.advance(150);
  harness.scene.turnPage(3);
  assert.ok(harness.leafOf());

  harness.windowObj.resize(500);
  assert.deepEqual(harness.model.commits, [3]);
  assert.equal(harness.leafOf(), undefined);
  assert.equal(harness.ghostOf(), undefined);
  assert.ok(!harness.sheet.classList.contains('is-turning'));
  assert.equal(harness.sheet.querySelector('.book-cast-left').style.opacity, '');
  assert.equal(harness.surface.style.opacity, undefined);

  await harness.advance(2000);
  assert.deepEqual(harness.model.commits, [3], 'nothing replays after the settle');
});

test('a resize that stays desktop-sized does not disturb a turn, and a mobile fade settles when widened', async () => {
  const desktop = createHarness({ open: true });
  const done = desktop.scene.turnPage(2);
  await desktop.advance(100);
  desktop.windowObj.resize(1400);
  assert.ok(desktop.leafOf());
  await desktop.advance(1000);
  await done;
  assert.deepEqual(desktop.model.commits, [2]);

  const mobile = createHarness({ open: true, innerWidth: 390 });
  mobile.scene.turnPage(2);
  await mobile.advance(60);
  mobile.windowObj.resize(1200);
  assert.deepEqual(mobile.model.commits, [2]);
  assert.equal(mobile.surface.style.opacity, '');
});

test('a resize while idle does nothing', () => {
  const harness = createHarness({ open: true });
  assert.doesNotThrow(() => harness.windowObj.resize(500));
  assert.deepEqual(harness.model.commits, []);
});

/* ------------------------------------------------------------------ */
/* Error paths                                                        */
/* ------------------------------------------------------------------ */

test('an error while landing is reported, the leaf is removed, and the queue keeps going', async () => {
  const harness = createHarness({ open: true });
  harness.model.commitError = new Error('render failed');
  const first = harness.scene.turnPage(2);
  await harness.advance(1000);
  await first;

  assert.equal(harness.errors.length, 1);
  assert.match(harness.errors[0].message, /render failed/);
  assert.equal(harness.leafOf(), undefined);
  assert.equal(harness.ghostOf(), undefined);
  assert.ok(!harness.sheet.classList.contains('is-turning'));

  harness.model.commitError = null;
  harness.model.shown = 1;
  const second = harness.scene.turnPage(2);
  await harness.advance(1000);
  await second;
  assert.equal(harness.model.shown, 2);
});

test('an error thrown while animating the leaf cleans up and is reported', async () => {
  const harness = createHarness({ open: true });
  const done = harness.scene.turnPage(2);
  await harness.advance(32);
  const leaf = harness.leafOf();
  Object.defineProperty(leaf.style, 'transform', {
    set() {
      throw new Error('style failed');
    },
    get() {
      return '';
    }
  });

  await harness.advance(100);
  await done;
  assert.equal(harness.errors.length, 1);
  assert.match(harness.errors[0].message, /style failed/);
  assert.equal(harness.leafOf(), undefined);
  assert.ok(!harness.sheet.classList.contains('is-turning'));
});

test('missing page faces fall back to rendering the page directly', async () => {
  const harness = createHarness({ open: true });
  harness.model.nullFaces = true;
  await harness.scene.turnPage(2);
  assert.deepEqual(harness.model.commits, [2]);
  assert.equal(harness.leafOf(), undefined);

  const noLive = createHarness({ open: true });
  noLive.grid.children.forEach((child) => child.remove());
  await noLive.scene.turnPage(2);
  assert.deepEqual(noLive.model.commits, [2]);
});

test('without an onError handler errors go to the console', async () => {
  const harness = createHarness({ open: true, withOnError: false });
  const original = console.error;
  const logged = [];
  console.error = (error) => logged.push(error);
  try {
    harness.model.commitError = new Error('boom');
    const done = harness.scene.turnPage(2);
    await harness.advance(1000);
    await done;
  } finally {
    console.error = original;
  }
  assert.equal(logged.length, 1);
  assert.match(logged[0].message, /boom/);
});

/* ------------------------------------------------------------------ */
/* Drag to scrub                                                      */
/* ------------------------------------------------------------------ */

test('dragging from the right edge scrubs the leaf with the pointer', async () => {
  const harness = createHarness({ open: true });
  const down = dragFromRight(harness);

  assert.equal(down.defaultPrevented, true);
  assert.ok(harness.sheet.captured.has(1), 'the pointer is captured');
  const leaf = harness.leafOf();
  assert.ok(leaf);
  assert.equal(leaf.style.transform, 'rotateY(0deg)');
  assert.deepEqual(harness.model.selects, [], 'a drag is not a navigation until it completes');

  harness.sheet.dispatch('pointermove', pointer(CENTER_X));
  const angle = Number.parseFloat(leaf.style.transform.replace('rotateY(', ''));
  assert.ok(angle < -70 && angle > -110, `leaf follows the pointer, angle ${angle}`);

  harness.sheet.dispatch('pointermove', pointer(200));
  const far = Number.parseFloat(leaf.style.transform.replace('rotateY(', ''));
  assert.ok(far < angle);
  harness.sheet.dispatch('pointercancel');
  await harness.advance(1000);
});

test('releasing past the threshold completes the turn and then renders the page', async () => {
  const harness = createHarness({ open: true });
  dragFromRight(harness);
  harness.sheet.dispatch('pointermove', pointer(CENTER_X));
  harness.sheet.dispatch('pointerup', pointer(CENTER_X));

  assert.deepEqual(harness.model.selects, [2], 'the page model is told when the drag completes');
  assert.equal(harness.sheet.captured.size, 0, 'capture is released');
  assert.equal(harness.sheet.listenerCount('pointermove'), 0);
  assert.deepEqual(harness.model.commits, []);

  await harness.advance(1000);
  assert.deepEqual(harness.model.commits, [2]);
  assert.equal(harness.leafOf(), undefined);
  assert.equal(harness.ghostOf(), undefined);
  assert.ok(!harness.sheet.classList.contains('is-turning'));
});

test('a page requested during a drag keeps its selection when the drag completes', async () => {
  const harness = createHarness({ open: true });
  dragFromRight(harness);
  harness.sheet.dispatch('pointermove', pointer(CENTER_X));
  void harness.scene.turnPage(4);
  harness.sheet.dispatch('pointerup', pointer(CENTER_X));
  await harness.advance(3000);

  assert.deepEqual(harness.model.selects, [4], 'the drag does not select its own, older page');
  assert.deepEqual(harness.model.commits, [2, 4], 'the drag lands, then the queued page');
});

test('releasing short of the threshold springs back without changing the page', async () => {
  const harness = createHarness({ open: true });
  dragFromRight(harness);
  harness.sheet.dispatch('pointermove', pointer(700));
  harness.sheet.dispatch('pointerup', pointer(700));
  await harness.advance(40);
  assert.ok(harness.leafOf(), 'the leaf is still springing back');

  await harness.advance(1000);
  assert.deepEqual(harness.model.selects, []);
  assert.deepEqual(harness.model.commits, []);
  assert.equal(harness.leafOf(), undefined);
  assert.equal(harness.ghostOf(), undefined);
  assert.ok(!harness.sheet.classList.contains('is-turning'));
  assert.equal(harness.sheet.querySelector('.book-cast-right').style.opacity, '');
});

test('pointercancel and lost capture spring the leaf back', async () => {
  for (const type of ['pointercancel', 'lostpointercapture']) {
    const harness = createHarness({ open: true });
    dragFromRight(harness);
    harness.sheet.dispatch('pointermove', pointer(CENTER_X));
    harness.sheet.dispatch(type);
    await harness.advance(1000);

    assert.deepEqual(harness.model.commits, [], type);
    assert.deepEqual(harness.model.selects, [], type);
    assert.equal(harness.leafOf(), undefined, type);
    assert.equal(harness.sheet.listenerCount('pointerup'), 0, type);
  }
});

test('a left-edge drag turns to the previous page', async () => {
  const harness = createHarness({ open: true });
  harness.model.shown = 3;
  const down = harness.sheet.dispatch('pointerdown', pointer(110));
  assert.equal(down.defaultPrevented, true);
  const leaf = harness.leafOf();
  assert.ok(Number.parseFloat(leaf.style.transform.replace('rotateY(', '')) < -150);

  harness.sheet.dispatch('pointermove', pointer(CENTER_X));
  harness.sheet.dispatch('pointerup', pointer(CENTER_X));
  await harness.advance(1000);
  assert.deepEqual(harness.model.selects, [2]);
  assert.deepEqual(harness.model.commits, [2]);
});

test('drags only start from edge and corner zones on a primary press', () => {
  const cases = [
    ['a card press', pointer(RIGHT_EDGE_X, 400, { target: { closest: (selector) => (selector === '.artifact-card' ? {} : null) } })],
    ['the middle of a page', pointer(800)],
    ['outside the book', pointer(50)],
    ['above the book', pointer(RIGHT_EDGE_X, -10)],
    ['below the book', pointer(RIGHT_EDGE_X, 900)],
    ['past the right edge', pointer(1200)],
    ['a secondary button', pointer(RIGHT_EDGE_X, 400, { button: 2 })]
  ];

  for (const [label, event] of cases) {
    const harness = createHarness({ open: true });
    const down = harness.sheet.dispatch('pointerdown', event);
    assert.equal(down.defaultPrevented, false, label);
    assert.equal(harness.leafOf(), undefined, label);
  }
});

test('a bottom corner starts a drag even away from the edge strip', () => {
  const harness = createHarness({ open: true });
  const down = harness.sheet.dispatch('pointerdown', pointer(1100 - 60, 800 - 30));
  assert.equal(down.defaultPrevented, true);
  assert.ok(harness.leafOf());

  const high = createHarness({ open: true });
  const miss = high.sheet.dispatch('pointerdown', pointer(1100 - 60, 400));
  assert.equal(miss.defaultPrevented, false);
});

test('drags are ignored at the book ends, when reduced motion is on, on mobile, or before the book opens', () => {
  const first = createHarness({ open: true });
  assert.equal(first.sheet.dispatch('pointerdown', pointer(110)).defaultPrevented, false, 'no page before the first');

  const last = createHarness({ open: true, pageCount: 3 });
  last.model.shown = 3;
  assert.equal(dragFromRight(last).defaultPrevented, false, 'no page after the last');

  const reduced = createHarness({ open: true, reducedMotion: true });
  assert.equal(dragFromRight(reduced).defaultPrevented, false);

  const mobile = createHarness({ open: true, innerWidth: 390 });
  assert.equal(dragFromRight(mobile).defaultPrevented, false);

  const closed = createHarness();
  assert.equal(dragFromRight(closed).defaultPrevented, false);
});

test('a drag cannot start when the target page cannot be built', () => {
  const harness = createHarness({ open: true });
  harness.model.nullFaces = true;
  dragFromRight(harness);
  assert.equal(harness.leafOf(), undefined);
  assert.equal(harness.sheet.captured.size, 0);
});

test('tapping a page corner turns the page while tapping an edge strip does not', async () => {
  const corner = createHarness({ open: true });
  corner.sheet.dispatch('pointerdown', pointer(1100 - 30, 800 - 30));
  corner.sheet.dispatch('pointerup', pointer(1100 - 30, 800 - 30));
  await corner.advance(1000);
  assert.deepEqual(corner.model.commits, [2]);

  const edge = createHarness({ open: true });
  dragFromRight(edge);
  edge.sheet.dispatch('pointerup', pointer(RIGHT_EDGE_X));
  await edge.advance(1000);
  assert.deepEqual(edge.model.commits, []);
  assert.equal(edge.leafOf(), undefined);

  const dragged = createHarness({ open: true });
  dragged.sheet.dispatch('pointerdown', pointer(1100 - 30, 800 - 30));
  dragged.sheet.dispatch('pointermove', pointer(1000));
  dragged.sheet.dispatch('pointerup', pointer(1000));
  await dragged.advance(1000);
  assert.deepEqual(dragged.model.commits, [], 'a small drag from a corner is a drag, not a tap');
});

test('events from a second pointer are ignored during a drag', async () => {
  const harness = createHarness({ open: true });
  dragFromRight(harness);
  harness.sheet.dispatch('pointermove', pointer(200, 400, { pointerId: 9 }));
  assert.equal(harness.leafOf().style.transform, 'rotateY(0deg)');
  harness.sheet.dispatch('pointerup', pointer(200, 400, { pointerId: 9 }));
  harness.sheet.dispatch('pointercancel', { pointerId: 9 });
  assert.ok(harness.leafOf());
  assert.equal(harness.sheet.listenerCount('pointermove'), 1);

  harness.sheet.dispatch('pointercancel');
  await harness.advance(1000);
  assert.equal(harness.leafOf(), undefined);
});

test('a drag released after a resize abort does nothing', async () => {
  const harness = createHarness({ open: true });
  dragFromRight(harness);
  harness.sheet.dispatch('pointermove', pointer(CENTER_X));
  harness.sheet.dispatch('pointerup', pointer(CENTER_X));
  harness.sheet.dispatch('pointermove', pointer(1000));
  harness.sheet.dispatch('pointerup', pointer(1000));
  await harness.advance(1000);
  assert.deepEqual(harness.model.commits, [2]);
  assert.deepEqual(harness.model.selects, [2], 'the late events do not select again');
});

test('the drag still works when pointer capture is refused', async () => {
  const harness = createHarness({ open: true });
  harness.sheet.throwOnCapture = true;
  dragFromRight(harness);
  assert.ok(harness.leafOf());
  harness.sheet.dispatch('pointermove', pointer(CENTER_X));
  harness.sheet.dispatch('pointerup', pointer(CENTER_X));
  await harness.advance(1000);
  assert.deepEqual(harness.model.commits, [2]);
});

test('grabbing the page during an automatic turn settles it instead of dropping the input', async () => {
  const harness = createHarness({ open: true });
  harness.scene.turnPage(2);
  await harness.advance(100);
  assert.ok(harness.leafOf());

  const down = dragFromRight(harness);
  assert.equal(down.defaultPrevented, true);
  assert.deepEqual(harness.model.commits, [2], 'the running turn lands at once');
  assert.equal(harness.created.filter((element) => element.classList.contains('book-leaf')).length, 2);
  assert.equal(harness.sheet.children.filter((child) => child.classList.contains('book-leaf')).length, 1);
  assert.match(harness.model.builds.join(','), /2,3$/, 'the new drag leaf is for the next page');

  harness.sheet.dispatch('pointercancel');
  await harness.advance(1000);
  assert.equal(harness.leafOf(), undefined);
});

test('grabbing the page after queued requests drags from the latest requested page', async () => {
  const harness = createHarness({ open: true });
  harness.scene.turnPage(2);
  await harness.advance(100);
  harness.scene.turnPage(4);

  dragFromRight(harness);
  assert.deepEqual(harness.model.commits, [4]);
  assert.equal(harness.model.builds.at(-1), 5);
  harness.sheet.dispatch('pointercancel');
  await harness.advance(1000);
  assert.deepEqual(harness.model.commits, [4]);
});

test('a request made while scrubbing is queued and runs after the leaf is released', async () => {
  const harness = createHarness({ open: true });
  dragFromRight(harness);
  const queued = harness.scene.turnPage(3);
  assert.deepEqual(harness.model.commits, [], 'nothing replaces the page under the pointer');

  harness.sheet.dispatch('pointermove', pointer(700));
  harness.sheet.dispatch('pointerup', pointer(700));
  await harness.advance(3000);
  await queued;
  assert.deepEqual(harness.model.commits, [3]);
  assert.equal(harness.leafOf(), undefined);
});

test('a request made while a drag settles lands after the drag completes', async () => {
  const harness = createHarness({ open: true });
  dragFromRight(harness);
  harness.sheet.dispatch('pointermove', pointer(CENTER_X));
  harness.sheet.dispatch('pointerup', pointer(CENTER_X));
  harness.scene.turnPage(4);

  await harness.advance(3000);
  assert.deepEqual(harness.model.commits, [2, 4]);
  assert.equal(harness.leafOf(), undefined);
});

test('a resize mid-drag drops the drag and detaches its listeners', async () => {
  const harness = createHarness({ open: true });
  dragFromRight(harness);
  harness.sheet.dispatch('pointermove', pointer(CENTER_X));

  harness.windowObj.resize(500);
  assert.equal(harness.leafOf(), undefined);
  assert.equal(harness.sheet.listenerCount('pointermove'), 0);
  assert.equal(harness.sheet.captured.size, 0);
  assert.deepEqual(harness.model.commits, [], 'an unfinished drag never changes the page');

  harness.sheet.dispatch('pointerup', pointer(CENTER_X));
  await harness.advance(1000);
  assert.deepEqual(harness.model.commits, []);
});

test('a resize while a drag is settling after release is safe', async () => {
  const harness = createHarness({ open: true });
  dragFromRight(harness);
  harness.sheet.dispatch('pointermove', pointer(CENTER_X));
  harness.sheet.dispatch('pointerup', pointer(CENTER_X));
  await harness.advance(60);

  harness.windowObj.resize(500);
  assert.deepEqual(harness.model.commits, [2], 'the selected page is rendered by the settle');
  assert.equal(harness.leafOf(), undefined);
  await harness.advance(1000);
  assert.deepEqual(harness.model.commits, [2]);
});

test('an error while a drag lands is reported and the leaf is removed', async () => {
  const harness = createHarness({ open: true });
  harness.model.commitError = new Error('drag render failed');
  dragFromRight(harness);
  harness.sheet.dispatch('pointermove', pointer(CENTER_X));
  harness.sheet.dispatch('pointerup', pointer(CENTER_X));
  await harness.advance(1000);

  assert.equal(harness.errors.length, 1);
  assert.equal(harness.leafOf(), undefined);
  assert.ok(!harness.sheet.classList.contains('is-turning'));
});

test('a scene built without a sheet still exposes a working API', async () => {
  const harness = createHarness({ includeSheet: false, includeShell: false });
  await harness.scene.startIntro();
  await harness.scene.turnPage(2);
  assert.deepEqual(harness.model.commits, [2]);
});

test('an abort during each intro phase still ends open with no later steps', async () => {
  const ribbon = createHarness();
  const ribbonIntro = ribbon.scene.startIntro();
  await ribbon.advance(500 + 200);
  ribbon.windowObj.resize(500);
  await ribbon.advance(2000);
  await ribbonIntro;
  assert.equal(ribbon.cover.animateCalls.length, 0);
  assert.ok(ribbon.shell.classList.contains('is-open'));

  const lateSwing = createHarness();
  const lateIntro = lateSwing.scene.startIntro();
  await lateSwing.advance(500 + 520 + 700);
  assert.equal(lateSwing.cover.animateCalls.length, 1);
  assert.ok(!lateSwing.shell.classList.contains('is-open'));
  lateSwing.windowObj.resize(500);
  await lateSwing.advance(2000);
  await lateIntro;
  assert.ok(lateSwing.shell.classList.contains('is-open'));
  assert.equal(lateSwing.grid.querySelector('.artifact-page-left').animateCalls.length, 0);

  const fade = createHarness({ reducedMotion: true });
  const fadeIntro = fade.scene.startIntro();
  await fade.advance(50);
  fade.windowObj.resize(500);
  await fade.advance(1000);
  await fadeIntro;
  assert.equal(fade.sheet.animateCalls.length, 1, 'the second fade never starts');
  assert.ok(fade.shell.classList.contains('is-open'));
});

test('a queued turn that finds the book closed renders directly', async () => {
  const harness = createHarness({ open: true });
  const done = harness.scene.turnPage(2);
  harness.shell.dataset.sceneIntro = 'opening';
  await harness.advance(50);
  await done;
  assert.deepEqual(harness.model.commits, [2]);
  assert.equal(harness.created.length, 0);
});

test('reduced motion falls back to matchMedia when no motion helper is given', async () => {
  const reduced = createHarness({ reducedMotion: true, withMotion: false });
  const intro = reduced.scene.startIntro();
  await reduced.advance(1000);
  await intro;
  assert.equal(reduced.cover.animateCalls.length, 0);
  assert.equal(reduced.sheet.animateCalls.length, 2);

  const plain = createHarness({ withMotion: false });
  const swing = plain.scene.startIntro();
  await plain.advance(3000);
  await swing;
  assert.equal(plain.cover.animateCalls.length, 1);
});
