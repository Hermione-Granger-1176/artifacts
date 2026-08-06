import test from 'node:test';
import assert from 'node:assert/strict';

import { closest } from '../../../js/modules/dom-events.js';

test('closest returns the matching ancestor from an event target', () => {
  const match = {};
  const target = {
    closest(selector) {
      assert.equal(selector, '.artifact-card');
      return match;
    }
  };

  assert.equal(closest({ target }, '.artifact-card'), match);
});

test('closest returns null for missing or non-element event targets', () => {
  assert.equal(closest(null, '.artifact-card'), null);
  assert.equal(closest({ target: null }, '.artifact-card'), null);
  assert.equal(closest({ target: {} }, '.artifact-card'), null);
});
