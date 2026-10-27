import test from 'node:test';
import assert from 'node:assert/strict';

import { createElement, setAttr, setText, skipFirstTransition } from '../../../js/modules/dom-sync.js';

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

test('setText rewrites a lone text node in place instead of replacing it', () => {
  const textNode = { nodeType: 3, data: 'a' };
  const element = { firstChild: textNode, lastChild: textNode, textContent: 'a' };
  setText(element, 'b');
  assert.equal(element.firstChild, textNode, 'the same text node is kept');
  assert.equal(textNode.data, 'b');

  const clearing = { firstChild: textNode, lastChild: textNode, textContent: 'b' };
  setText(clearing, '');
  assert.equal(clearing.textContent, '', 'emptying an element still clears it');
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

test('skipFirstTransition holds only the first value without a transition', async () => {
  const frames = [];
  const saved = globalThis.requestAnimationFrame;
  globalThis.requestAnimationFrame = (callback) => frames.push(callback);
  try {
    const element = { style: { transition: '' } };
    skipFirstTransition(element);
    assert.equal(element.style.transition, 'none', 'the first value lands without a transition');
    frames.shift()();
    assert.equal(element.style.transition, 'none', 'held through the frame that styles the value');
    frames.shift()();
    assert.equal(element.style.transition, '', 'restored after');

    skipFirstTransition(element);
    assert.equal(element.style.transition, '', 'later values animate');
    assert.equal(frames.length, 0);
  } finally {
    if (saved) globalThis.requestAnimationFrame = saved; else delete globalThis.requestAnimationFrame;
  }
});

test('skipFirstTransition leaves the element alone without animation frames', () => {
  const saved = globalThis.requestAnimationFrame;
  delete globalThis.requestAnimationFrame;
  try {
    const element = { style: { transition: '' } };
    skipFirstTransition(element);
    assert.equal(element.style.transition, '');
  } finally {
    if (saved) globalThis.requestAnimationFrame = saved;
  }
});
