import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { prefersReducedMotion, scrollBehavior } from '../../../js/modules/motion.js';
import { createMotionHelper } from '../../../js/modules/gallery/motion.js';

/** A window whose reduced-motion query matches `state.reduce`, recording queries and scrolls. */
function fakeWindow(state = { reduce: false }) {
  const queries = [];
  const scrolls = [];
  return {
    state,
    queries,
    scrolls,
    matchMedia(query) {
      queries.push(query);
      return { matches: state.reduce };
    },
    scrollTo(options) {
      scrolls.push(options);
    }
  };
}

describe('prefersReducedMotion', () => {
  it('reads the live reduced-motion media query', () => {
    const win = fakeWindow();
    assert.equal(prefersReducedMotion(win), false);
    win.state.reduce = true;
    assert.equal(prefersReducedMotion(win), true);
    assert.deepEqual(win.queries, ['(prefers-reduced-motion: reduce)', '(prefers-reduced-motion: reduce)']);
  });

  it('queries the global window by default', () => {
    const saved = globalThis.window;
    globalThis.window = fakeWindow({ reduce: true });
    try {
      assert.equal(prefersReducedMotion(), true);
      assert.equal(scrollBehavior(), 'auto');
    } finally {
      if (saved) globalThis.window = saved; else delete globalThis.window;
    }
  });
});

describe('scrollBehavior', () => {
  it('is auto under reduced motion and smooth otherwise', () => {
    assert.equal(scrollBehavior(fakeWindow({ reduce: true })), 'auto');
    assert.equal(scrollBehavior(fakeWindow({ reduce: false })), 'smooth');
  });
});

describe('createMotionHelper', () => {
  it('binds the shared helpers to the given window', () => {
    const win = fakeWindow();
    const motion = createMotionHelper(win);
    assert.equal(motion.prefersReducedMotion(), false);
    assert.equal(motion.getScrollBehavior(), 'smooth');
    win.state.reduce = true;
    assert.equal(motion.prefersReducedMotion(), true);
    assert.equal(motion.getScrollBehavior(), 'auto');
  });

  it('scrollToTop scrolls to the top with the behavior the preference allows', () => {
    const win = fakeWindow();
    const motion = createMotionHelper(win);
    motion.scrollToTop();
    win.state.reduce = true;
    motion.scrollToTop();
    assert.deepEqual(win.scrolls, [{ top: 0, behavior: 'smooth' }, { top: 0, behavior: 'auto' }]);
  });
});
