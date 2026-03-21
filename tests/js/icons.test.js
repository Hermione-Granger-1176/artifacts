import test from 'node:test';
import assert from 'node:assert/strict';

import { ICONS } from '../../js/modules/icons.js';

test('ICONS exports the expected inline SVG fragments', () => {
  const keys = [
    'open',
    'reset',
    'chevronLeft',
    'chevronRight',
    'chevronFirst',
    'chevronLast',
    'close'
  ];

  assert.deepEqual(Object.keys(ICONS), keys);
  for (const key of keys) {
    assert.match(ICONS[key], /^<svg[\s\S]*<\/svg>$/);
  }
});
