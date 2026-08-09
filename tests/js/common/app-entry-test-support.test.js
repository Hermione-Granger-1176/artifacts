import assert from 'node:assert/strict';
import test from 'node:test';

import { makeElement } from './app-entry-test-support.js';

test('makeElement keeps childElementCount synchronized with its children', () => {
  const firstParent = makeElement('first');
  const secondParent = makeElement('second');
  const firstChild = makeElement('first-child');
  const secondChild = makeElement('second-child');

  firstParent.append(firstChild, secondChild);
  assert.equal(firstParent.childElementCount, 2);

  secondParent.appendChild(firstChild);
  assert.equal(firstParent.childElementCount, 1);
  assert.equal(secondParent.childElementCount, 1);

  secondParent.replaceChildren(secondChild);
  assert.equal(firstParent.childElementCount, 0);
  assert.equal(secondParent.childElementCount, 1);

  secondChild.remove();
  assert.equal(secondParent.childElementCount, 0);
});
