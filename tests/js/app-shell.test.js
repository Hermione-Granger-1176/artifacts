import test from 'node:test';
import assert from 'node:assert/strict';

import { renderAppShell } from '../../js/modules/app-shell.js';

function createSlot() {
  return {
    childElementCount: 0,
    innerHTML: ''
  };
}

test('renderAppShell fills shared shell placeholders', () => {
  const slots = {
    '[data-app-shell="header"]': createSlot(),
    '[data-app-shell="runtime-error"]': createSlot(),
    '[data-app-shell="scroll-top"]': createSlot()
  };

  renderAppShell({
    documentObj: {
      querySelector(selector) {
        return slots[selector] ?? null;
      }
    },
    homePath: '../'
  });

  assert.match(slots['[data-app-shell="header"]'].innerHTML, /id="theme-toggle"/);
  assert.match(slots['[data-app-shell="header"]'].innerHTML, /href="\.\.\/"/);
  assert.match(slots['[data-app-shell="runtime-error"]'].innerHTML, /id="runtime-error"/);
  assert.match(slots['[data-app-shell="scroll-top"]'].innerHTML, /id="scroll-top"/);
});

test('renderAppShell leaves populated placeholders unchanged', () => {
  const slot = {
    childElementCount: 1,
    innerHTML: '<p>Keep existing content</p>'
  };

  renderAppShell({
    documentObj: {
      querySelector(selector) {
        return selector === '[data-app-shell="header"]' ? slot : null;
      }
    }
  });

  assert.equal(slot.innerHTML, '<p>Keep existing content</p>');
});
