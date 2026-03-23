import test from 'node:test';
import assert from 'node:assert/strict';

import { createBookScene } from '../../js/modules/book-scene.js';

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

  contains(name) {
    return this.values.has(name);
  }
}

class FakeAnimation {
  constructor({ deferred = false } = {}) {
    this.cancelled = false;
    if (deferred) {
      this.finished = new Promise((resolve) => {
        this._resolve = resolve;
      });
    } else {
      this.finished = Promise.resolve();
    }
    this.commitStylesCalls = 0;
  }

  cancel() {
    this.cancelled = true;
  }

  commitStyles() {
    this.commitStylesCalls += 1;
  }

  resolve() {
    this._resolve?.();
  }
}

class FakeElement {
  constructor(id = '') {
    this.id = id;
    this.classList = new FakeClassList();
    this.dataset = {};
    this.style = {};
    this.animateCalls = [];
    this.animationFactories = [];
  }

  animate(keyframes, options) {
    const animation = this.animationFactories.length > 0
      ? this.animationFactories.shift()(keyframes, options)
      : new FakeAnimation();
    this.animateCalls.push({ animation, keyframes, options });
    return animation;
  }

  querySelector() {
    return null;
  }
}

function createHarness({
  deferTimers = false,
  includeCover = true,
  includeGrid = true,
  includeLeftPage = true,
  includeRightPage = true,
  includeSheet = true,
  includeShell = true,
  innerWidth = 1024,
  reducedMotion = false,
  sceneIntro = ''
} = {}) {
  const shell = includeShell ? new FakeElement('book-shell') : null;
  const cover = includeCover ? new FakeElement('book-cover') : null;
  const sheet = includeSheet ? new FakeElement('book-sheet') : null;
  const grid = includeGrid ? new FakeElement('artifacts-grid') : null;
  const leftPage = includeLeftPage ? new FakeElement('left-page') : null;
  const rightPage = includeRightPage ? new FakeElement('right-page') : null;
  const timers = [];

  if (shell) {
    shell.dataset.sceneIntro = sceneIntro;
  }

  if (grid) {
    let currentLeft = leftPage;
    let currentRight = rightPage;
    grid.setPages = (nextLeft, nextRight) => {
      currentLeft = nextLeft;
      currentRight = nextRight;
    };
    grid.querySelector = (selector) => {
      if (selector === '.artifact-page-left') {
        return currentLeft;
      }
      if (selector === '.artifact-page-right') {
        return currentRight;
      }
      return null;
    };
  }

  const elements = new Map([
    ['book-shell', shell],
    ['book-cover', cover],
    ['book-sheet', sheet],
    ['artifacts-grid', grid]
  ].filter(([, value]) => Boolean(value)));

  const documentObj = {
    getElementById(id) {
      return elements.get(id) || null;
    }
  };

  const windowObj = {
    innerWidth,
    matchMedia() {
      return { matches: reducedMotion };
    },
    setTimeout(callback, _delay) {
      if (deferTimers) {
        timers.push(callback);
      } else {
        callback();
      }
      return timers.length;
    }
  };

  async function flushTimers() {
    for (; timers.length > 0; ) {
      timers.shift()();
      await Promise.resolve();
    }
  }

  return {
    cover,
    documentObj,
    flushTimers,
    grid,
    leftPage,
    rightPage,
    sheet,
    shell,
    windowObj
  };
}

test('startIntro no-ops when #book-shell is missing', async () => {
  const harness = createHarness({ includeShell: false });
  const bookScene = createBookScene({
    documentObj: harness.documentObj,
    motion: { prefersReducedMotion: () => false },
    windowObj: harness.windowObj
  });

  await bookScene.startIntro();
});

test('startIntro short-circuits when the intro is already open', async () => {
  const harness = createHarness({ sceneIntro: 'open' });
  const bookScene = createBookScene({
    documentObj: harness.documentObj,
    motion: { prefersReducedMotion: () => false },
    windowObj: harness.windowObj
  });

  await bookScene.startIntro();

  assert.equal(harness.cover.animateCalls.length, 0);
  assert.equal(harness.leftPage.animateCalls.length, 0);
});

test('startIntro opens immediately when reduced motion is preferred', async () => {
  const harness = createHarness({ reducedMotion: true });
  const bookScene = createBookScene({
    documentObj: harness.documentObj,
    windowObj: harness.windowObj
  });

  await bookScene.startIntro();

  assert.equal(harness.shell.dataset.sceneIntro, 'open');
  assert.equal(harness.shell.classList.contains('is-opening'), false);
  assert.equal(harness.shell.classList.contains('is-open'), true);
  assert.equal(harness.cover.style.visibility, 'hidden');
  assert.equal(harness.cover.animateCalls.length, 0);
});

test('startIntro handles missing cover, sheet, or grid gracefully', async () => {
  const harness = createHarness({ includeCover: false });
  const bookScene = createBookScene({
    documentObj: harness.documentObj,
    motion: { prefersReducedMotion: () => false },
    windowObj: harness.windowObj
  });

  await bookScene.startIntro();

  assert.equal(harness.shell.dataset.sceneIntro, 'open');
  assert.equal(harness.shell.classList.contains('is-open'), true);
});

test('startIntro animates the cover and left page then clears temporary styles', async () => {
  const harness = createHarness();
  const bookScene = createBookScene({
    documentObj: harness.documentObj,
    motion: { prefersReducedMotion: () => false },
    windowObj: harness.windowObj
  });

  await bookScene.startIntro();

  assert.equal(harness.cover.animateCalls.length, 1);
  assert.equal(harness.leftPage.animateCalls.length, 1);
  assert.equal(harness.cover.animateCalls[0].keyframes[1].transform, 'perspective(1600px) rotateY(-92deg)');
  assert.equal(harness.leftPage.animateCalls[0].keyframes[0].transform, 'perspective(1600px) rotateY(92deg)');
  assert.equal(harness.rightPage.style.transition, '');
  assert.equal(harness.rightPage.style.opacity, '');
  assert.equal(harness.leftPage.style.transformOrigin, '');
  assert.equal(harness.leftPage.style.position, '');
  assert.equal(harness.leftPage.style.zIndex, '');
  assert.equal(harness.leftPage.style.opacity, '');
  assert.equal(harness.cover.style.transformOrigin, '');
  assert.equal(harness.cover.style.transform, '');
  assert.equal(harness.cover.style.opacity, '');
  assert.equal(harness.cover.style.visibility, 'hidden');
  assert.equal(harness.shell.dataset.sceneIntro, 'open');
  assert.equal(harness.shell.classList.contains('is-open'), true);
});

test('startIntro reuses the in-flight intro promise', async () => {
  const harness = createHarness({ deferTimers: true });
  const bookScene = createBookScene({
    documentObj: harness.documentObj,
    motion: { prefersReducedMotion: () => false },
    windowObj: harness.windowObj
  });

  const first = bookScene.startIntro();
  const second = bookScene.startIntro();

  assert.notEqual(first, second);

  await harness.flushTimers();
  await Promise.all([first, second]);
  assert.equal(harness.cover.animateCalls.length, 1);
});

test('turnPage renders immediately when reduced motion is preferred', async () => {
  const harness = createHarness({ reducedMotion: true });
  const bookScene = createBookScene({
    documentObj: harness.documentObj,
    windowObj: harness.windowObj
  });
  let renders = 0;

  await bookScene.turnPage(() => {
    renders += 1;
  });

  assert.equal(renders, 1);
  assert.equal(harness.sheet.classList.contains('is-turning'), false);
});

test('turnPage renders immediately when the book sheet is missing', async () => {
  const harness = createHarness({ includeSheet: false });
  const bookScene = createBookScene({
    documentObj: harness.documentObj,
    motion: { prefersReducedMotion: () => false },
    windowObj: harness.windowObj
  });
  let renders = 0;

  await bookScene.turnPage(() => {
    renders += 1;
    return 'done';
  });

  assert.equal(renders, 1);
});

test('turnPage uses mobile fade-out and fade-in on narrow screens', async () => {
  const harness = createHarness({ innerWidth: 600 });
  const bookScene = createBookScene({
    documentObj: harness.documentObj,
    motion: { prefersReducedMotion: () => false },
    windowObj: harness.windowObj
  });
  let renders = 0;

  await bookScene.turnPage(() => {
    renders += 1;
  });

  assert.equal(renders, 1);
  assert.equal(harness.sheet.animateCalls.length, 2);
  assert.deepEqual(harness.sheet.animateCalls[0].keyframes, [{ opacity: 1 }, { opacity: 0 }]);
  assert.deepEqual(harness.sheet.animateCalls[1].keyframes, [{ opacity: 0 }, { opacity: 1 }]);
  assert.equal(harness.sheet.classList.contains('is-turning'), false);
});

test('turnPage falls back cleanly when current pages are missing', async () => {
  const harness = createHarness({ includeLeftPage: false, includeRightPage: false });
  const bookScene = createBookScene({
    documentObj: harness.documentObj,
    motion: { prefersReducedMotion: () => false },
    windowObj: harness.windowObj
  });
  let renders = 0;

  await bookScene.turnPage(() => {
    renders += 1;
  });

  assert.equal(renders, 1);
  assert.equal(harness.sheet.classList.contains('is-turning'), false);
});

test('turnPage uses desktop next-page flip directions', async () => {
  const harness = createHarness();
  const nextLeft = new FakeElement('next-left');
  const nextRight = new FakeElement('next-right');
  const bookScene = createBookScene({
    documentObj: harness.documentObj,
    motion: { prefersReducedMotion: () => false },
    windowObj: harness.windowObj
  });

  await bookScene.turnPage(() => {
    harness.grid.setPages(nextLeft, nextRight);
  }, { direction: 'next' });

  assert.equal(harness.rightPage.style.transformOrigin, 'left center');
  assert.equal(harness.rightPage.animateCalls[0].keyframes[1].transform, 'perspective(1600px) rotateY(-92deg)');
  assert.equal(nextLeft.style.transformOrigin, '');
  assert.equal(nextLeft.animateCalls[0].keyframes[0].transform, 'perspective(1600px) rotateY(92deg)');
  assert.equal(harness.grid.style.perspective, '');
  assert.equal(harness.grid.style.transformStyle, '');
  assert.equal(harness.sheet.classList.contains('is-turning'), false);
});

test('turnPage uses desktop previous-page flip directions', async () => {
  const harness = createHarness();
  const nextLeft = new FakeElement('next-left');
  const nextRight = new FakeElement('next-right');
  const bookScene = createBookScene({
    documentObj: harness.documentObj,
    motion: { prefersReducedMotion: () => false },
    windowObj: harness.windowObj
  });

  await bookScene.turnPage(() => {
    harness.grid.setPages(nextLeft, nextRight);
  }, { direction: 'previous' });

  assert.equal(harness.leftPage.style.transformOrigin, 'right center');
  assert.equal(harness.leftPage.animateCalls[0].keyframes[1].transform, 'perspective(1600px) rotateY(92deg)');
  assert.equal(nextRight.animateCalls[0].keyframes[0].transform, 'perspective(1600px) rotateY(-92deg)');
  assert.equal(harness.grid.style.perspective, '');
  assert.equal(harness.grid.style.transformStyle, '');
});

test('turnPage handles missing new pages after render', async () => {
  const harness = createHarness();
  const bookScene = createBookScene({
    documentObj: harness.documentObj,
    motion: { prefersReducedMotion: () => false },
    windowObj: harness.windowObj
  });

  await bookScene.turnPage(() => {
    harness.grid.setPages(null, null);
  });

  assert.equal(harness.rightPage.animateCalls[0].animation.cancelled, true);
  assert.equal(harness.grid.style.perspective, '');
  assert.equal(harness.grid.style.transformStyle, '');
  assert.equal(harness.sheet.classList.contains('is-turning'), false);
});

test('turnPage queues overlapping turns sequentially', async () => {
  const harness = createHarness({ innerWidth: 600 });
  const firstAnimation = new FakeAnimation({ deferred: true });
  harness.sheet.animationFactories.push(
    () => firstAnimation,
    () => new FakeAnimation(),
    () => new FakeAnimation(),
    () => new FakeAnimation()
  );
  const bookScene = createBookScene({
    documentObj: harness.documentObj,
    motion: { prefersReducedMotion: () => false },
    windowObj: harness.windowObj
  });
  const renderOrder = [];

  const firstTurn = bookScene.turnPage(() => {
    renderOrder.push('first');
  });
  const secondTurn = bookScene.turnPage(() => {
    renderOrder.push('second');
  });

  await Promise.resolve();
  assert.deepEqual(renderOrder, []);

  firstAnimation.resolve();
  await firstTurn;
  await secondTurn;

  assert.deepEqual(renderOrder, ['first', 'second']);
});

test('startIntro ignores invalid-state commitStyles errors from hidden elements', async () => {
  const harness = createHarness();
  harness.cover.animationFactories.push(() => ({
    finished: Promise.resolve(),
    cancel() {},
    commitStyles() {
      throw new DOMException('Target element is not rendered.', 'InvalidStateError');
    }
  }));
  const bookScene = createBookScene({
    documentObj: harness.documentObj,
    motion: { prefersReducedMotion: () => false },
    windowObj: harness.windowObj
  });

  await bookScene.startIntro();

  assert.equal(harness.shell.dataset.sceneIntro, 'open');
});
