import test from 'node:test';
import assert from 'node:assert/strict';

import { createFrameScheduler } from '../../../js/modules/frame-scheduler.js';

function createFrameClock() {
  const callbacks = [];
  return {
    callbacks,
    requestAnimationFrame(callback) {
      callbacks.push(callback);
      return callbacks.length;
    },
    flush() {
      const pending = callbacks.splice(0);
      pending.forEach((callback) => callback());
    }
  };
}

test('createFrameScheduler runs the callback once per frame for a burst of requests', () => {
  const clock = createFrameClock();
  let calls = 0;
  const schedule = createFrameScheduler(() => {
    calls += 1;
  }, clock);

  schedule();
  schedule();
  schedule();
  assert.equal(clock.callbacks.length, 1);
  assert.equal(calls, 0);

  clock.flush();
  assert.equal(calls, 1);
});

test('createFrameScheduler schedules a new frame after the pending one runs', () => {
  const clock = createFrameClock();
  let calls = 0;
  const schedule = createFrameScheduler(() => {
    calls += 1;
  }, clock);

  schedule();
  clock.flush();
  schedule();
  assert.equal(clock.callbacks.length, 1);

  clock.flush();
  assert.equal(calls, 2);
});
