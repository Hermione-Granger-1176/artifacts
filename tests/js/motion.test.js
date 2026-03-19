import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { createMotionHelper } from '../../js/modules/motion.js';

describe('createMotionHelper', () => {
  it('prefersReducedMotion returns the media query match state', () => {
    const query = { matches: true };
    const win = { scrollTo() {} };
    const motion = createMotionHelper(query, win);
    assert.equal(motion.prefersReducedMotion(), true);

    query.matches = false;
    assert.equal(motion.prefersReducedMotion(), false);
  });

  it('getScrollBehavior returns auto when reduced motion is preferred', () => {
    const motion = createMotionHelper({ matches: true }, { scrollTo() {} });
    assert.equal(motion.getScrollBehavior(), 'auto');
  });

  it('getScrollBehavior returns smooth when reduced motion is not preferred', () => {
    const motion = createMotionHelper({ matches: false }, { scrollTo() {} });
    assert.equal(motion.getScrollBehavior(), 'smooth');
  });

  it('scrollToTop calls windowObj.scrollTo with correct args', () => {
    const calls = [];
    const win = { scrollTo(opts) { calls.push(opts); } };
    const motion = createMotionHelper({ matches: false }, win);
    motion.scrollToTop();
    assert.deepEqual(calls, [{ top: 0, behavior: 'smooth' }]);
  });

  it('scrollToTop uses auto behavior when reduced motion is preferred', () => {
    const calls = [];
    const win = { scrollTo(opts) { calls.push(opts); } };
    const motion = createMotionHelper({ matches: true }, win);
    motion.scrollToTop();
    assert.deepEqual(calls, [{ top: 0, behavior: 'auto' }]);
  });
});
