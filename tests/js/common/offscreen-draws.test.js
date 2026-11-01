import test from 'node:test';
import assert from 'node:assert/strict';

import { createOffscreenDraws } from '../../../js/modules/offscreen-draws.js';

/** Install a controllable IntersectionObserver for the duration of `run`. */
function withObserver(run) {
  const saved = globalThis.IntersectionObserver;
  const observers = [];
  globalThis.IntersectionObserver = class {
    constructor(callback, init) {
      this.callback = callback;
      this.init = init;
      this.targets = [];
      observers.push(this);
    }

    observe(target) {
      this.targets.push(target);
    }
  };
  try {
    run(observers);
  } finally {
    if (saved) globalThis.IntersectionObserver = saved;
    else delete globalThis.IntersectionObserver;
  }
}

test('createOffscreenDraws draws on screen at once and holds only the latest off-screen draw', () => {
  withObserver((observers) => {
    const a = {};
    const b = {};
    const draws = createOffscreenDraws([a, b]);
    const [observer] = observers;
    assert.deepEqual(observer.targets, [a, b]);
    assert.equal(observer.init.rootMargin, '200px 0px');

    const log = [];
    draws.draw(a, () => log.push('a1'));
    assert.deepEqual(log, ['a1'], 'an unreported canvas counts as on screen');

    observer.callback([{ target: b, isIntersecting: false }]);
    draws.draw(b, () => log.push('b1'));
    draws.draw(b, () => log.push('b2'));
    assert.deepEqual(log, ['a1']);
    observer.callback([{ target: b, isIntersecting: true }]);
    assert.deepEqual(log, ['a1', 'b2'], 'only the latest draw runs on entry');
    observer.callback([{ target: b, isIntersecting: true }]);
    assert.deepEqual(log, ['a1', 'b2'], 'nothing pending, nothing drawn');

    observer.callback([{ target: a, isIntersecting: false }]);
    draws.draw(a, () => log.push('a2'));
    draws.draw(a, () => log.push('a3'), true);
    observer.callback([{ target: a, isIntersecting: true }]);
    assert.deepEqual(log, ['a1', 'b2', 'a3'], 'a forced draw runs at once and drops the pending one');
  });
});

test('createOffscreenDraws draws everything at once without IntersectionObserver', () => {
  const saved = globalThis.IntersectionObserver;
  delete globalThis.IntersectionObserver;
  try {
    const target = {};
    const log = [];
    createOffscreenDraws([target], '0px').draw(target, () => log.push('x'));
    assert.deepEqual(log, ['x']);
  } finally {
    if (saved) globalThis.IntersectionObserver = saved;
  }
});
