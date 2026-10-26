import test from 'node:test';
import assert from 'node:assert/strict';

import { createElement, setAttr, setText } from '../../../js/modules/dom-sync.js';

/** A node that counts writes to its text and attributes. */
function createNode() {
  const attrs = new Map();
  const node = { writes: 0, text: '' };
  Object.defineProperty(node, 'textContent', {
    get: () => node.text,
    set: (value) => { node.writes += 1; node.text = value; }
  });
  node.getAttribute = (name) => (attrs.has(name) ? attrs.get(name) : null);
  node.setAttribute = (name, value) => { node.writes += 1; attrs.set(name, value); };
  return node;
}

test('setText and setAttr write only when the value changes', () => {
  const node = createNode();
  setText(node, '');
  setAttr(node, 'aria-label', 'x');
  setAttr(node, 'aria-label', 'x');
  setText(node, 'b');
  setText(node, 'b');
  assert.equal(node.writes, 2);
  assert.equal(node.textContent, 'b');
  assert.equal(node.getAttribute('aria-label'), 'x');
});

test('createElement applies class, text, attributes, and children', () => {
  const saved = globalThis.document;
  globalThis.document = {
    createElement: (tag) => {
      const node = createNode();
      node.tag = tag;
      node.children = [];
      node.append = (...kids) => node.children.push(...kids);
      return node;
    }
  };
  try {
    const child = { tag: 'span' };
    const node = createElement('div', { className: 'a b', text: 'hi', attrs: { id: 'x' } }, [child]);
    assert.equal(node.tag, 'div');
    assert.equal(node.className, 'a b');
    assert.equal(node.textContent, 'hi');
    assert.equal(node.getAttribute('id'), 'x');
    assert.deepEqual(node.children, [child]);

    const bare = createElement('p');
    assert.equal(bare.className, undefined);
    assert.equal(bare.writes, 0);
    assert.deepEqual(bare.children, []);
  } finally {
    globalThis.document = saved;
  }
});
