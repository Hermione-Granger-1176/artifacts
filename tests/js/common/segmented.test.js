import assert from 'node:assert/strict';
import test from 'node:test';

import { initSegmented } from '../../../js/modules/segmented.js';

function makeButton(id, active = false) {
  const classes = new Set(active ? ['active'] : []);
  const attrs = {};
  let clickHandler = null;
  return {
    id,
    classList: {
      toggle(cls, force) {
        force ? classes.add(cls) : classes.delete(cls);
      },
      contains(cls) {
        return classes.has(cls);
      }
    },
    setAttribute(key, value) {
      attrs[key] = value;
    },
    getAttribute(key) {
      return attrs[key] ?? null;
    },
    addEventListener(type, handler) {
      if (type === 'click') {
        clickHandler = handler;
      }
    },
    click() {
      if (clickHandler) {
        clickHandler();
      }
    }
  };
}

function makeContainer(buttons) {
  return {
    querySelectorAll() {
      return buttons;
    }
  };
}

test('initSegmented syncs aria-pressed from the initial active state', () => {
  const a = makeButton('a', true);
  const b = makeButton('b');
  initSegmented(makeContainer([a, b]), () => {});

  assert.equal(a.getAttribute('aria-pressed'), 'true');
  assert.equal(b.getAttribute('aria-pressed'), 'false');
});

test('initSegmented activates the clicked button and notifies onSelect', () => {
  const a = makeButton('a', true);
  const b = makeButton('b');
  const selected = [];
  const buttons = initSegmented(makeContainer([a, b]), (btn) => selected.push(btn.id));

  b.click();

  assert.equal(a.classList.contains('active'), false);
  assert.equal(b.classList.contains('active'), true);
  assert.equal(a.getAttribute('aria-pressed'), 'false');
  assert.equal(b.getAttribute('aria-pressed'), 'true');
  assert.deepEqual(selected, ['b']);
  assert.deepEqual(buttons, [a, b]);
});
