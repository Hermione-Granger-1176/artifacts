import test from 'node:test';
import assert from 'node:assert/strict';

import { createFrameScheduler } from '../../../js/modules/frame-scheduler.js';

/** Install a manual frame clock as the global window for one test. */
function createFrameClock(t) {
  const callbacks = [];
  const original = globalThis.window;
  globalThis.window = {
    requestAnimationFrame(callback) {
      callbacks.push(callback);
      return callbacks.length;
    }
  };
  t.after(() => {
    if (original === undefined) {
      delete globalThis.window;
    } else {
      globalThis.window = original;
    }
  });
  return {
    callbacks,
    flush() {
      const pending = callbacks.splice(0);
      pending.forEach((callback) => callback());
    }
  };
}

test('createFrameScheduler runs the callback once per frame for a burst of requests', (t) => {
  const clock = createFrameClock(t);
  let calls = 0;
  const schedule = createFrameScheduler(() => {
    calls += 1;
  });

  schedule();
  schedule();
  schedule();
  assert.equal(clock.callbacks.length, 1);
  assert.equal(calls, 0);

  clock.flush();
  assert.equal(calls, 1);
});

test('createFrameScheduler schedules a new frame after the pending one runs', (t) => {
  const clock = createFrameClock(t);
  let calls = 0;
  const schedule = createFrameScheduler(() => {
    calls += 1;
  });

  schedule();
  clock.flush();
  schedule();
  assert.equal(clock.callbacks.length, 1);

  clock.flush();
  assert.equal(calls, 2);
});
