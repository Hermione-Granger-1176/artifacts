import test from 'node:test';
import assert from 'node:assert/strict';

import { cacheElements } from '../../../js/modules/element-cache.js';

function createMockDocument(elementMap) {
  return {
    getElementById(id) {
      return Object.hasOwn(elementMap, id) ? elementMap[id] : null;
    }
  };
}

test('cacheElements returns a map of id to element', () => {
  const mockA = { id: 'alpha' };
  const mockB = { id: 'beta' };
  const doc = createMockDocument({ alpha: mockA, beta: mockB });

  const result = cacheElements(['alpha', 'beta'], doc);

  assert.equal(result.alpha, mockA);
  assert.equal(result.beta, mockB);
});

test('cacheElements returns null for missing elements', () => {
  const doc = createMockDocument({});

  const result = cacheElements(['missing', 'absent'], doc);

  assert.equal(result.missing, null);
  assert.equal(result.absent, null);
});

test('cacheElements returns empty object for empty id list', () => {
  const doc = createMockDocument({ something: { id: 'something' } });

  const result = cacheElements([], doc);

  assert.deepEqual(result, {});
});

test('cacheElements preserves original id as key', () => {
  const el = { id: 'my-element' };
  const doc = createMockDocument({ 'my-element': el });

  const result = cacheElements(['my-element'], doc);

  assert.equal(result['my-element'], el);
  assert.equal(Object.keys(result).length, 1);
});

test('cacheElements mixes found and missing elements', () => {
  const el = { id: 'exists' };
  const doc = createMockDocument({ exists: el });

  const result = cacheElements(['exists', 'gone'], doc);

  assert.equal(result.exists, el);
  assert.equal(result.gone, null);
});
