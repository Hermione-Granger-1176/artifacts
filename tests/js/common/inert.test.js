import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { setBackgroundContentInert } from '../../../js/modules/inert.js';

function createFakeElement(ariaHidden = null) {
  const attrs = {};
  if (ariaHidden !== null) {
    attrs['aria-hidden'] = ariaHidden;
  }
  return {
    inert: false,
    dataset: {},
    getAttribute(name) { return attrs[name] ?? null; },
    setAttribute(name, value) { attrs[name] = value; },
    removeAttribute(name) { delete attrs[name]; },
    _attrs: attrs
  };
}

describe('setBackgroundContentInert', () => {
  it('sets inert and aria-hidden on element', () => {
    const el = createFakeElement();
    setBackgroundContentInert([el], true);
    assert.equal(el.inert, true);
    assert.equal(el._attrs['aria-hidden'], 'true');
    assert.equal(el.dataset.prevAriaHidden, '');
  });

  it('preserves existing aria-hidden value', () => {
    const el = createFakeElement('false');
    setBackgroundContentInert([el], true);
    assert.equal(el.inert, true);
    assert.equal(el._attrs['aria-hidden'], 'true');
    assert.equal(el.dataset.prevAriaHidden, 'false');
  });

  it('is idempotent when already inert', () => {
    const el = createFakeElement();
    setBackgroundContentInert([el], true);
    const saved = el.dataset.prevAriaHidden;
    setBackgroundContentInert([el], true);
    assert.equal(el.dataset.prevAriaHidden, saved);
  });

  it('restores element from inert state', () => {
    const el = createFakeElement();
    setBackgroundContentInert([el], true);
    setBackgroundContentInert([el], false);
    assert.equal(el.inert, false);
    assert.equal(el._attrs['aria-hidden'], undefined);
    assert.equal(el.dataset.prevAriaHidden, undefined);
  });

  it('restores previous aria-hidden value', () => {
    const el = createFakeElement('false');
    setBackgroundContentInert([el], true);
    setBackgroundContentInert([el], false);
    assert.equal(el.inert, false);
    assert.equal(el._attrs['aria-hidden'], 'false');
  });

  it('is a no-op when element is not inert', () => {
    const el = createFakeElement();
    setBackgroundContentInert([el], false);
    assert.equal(el.inert, false);
    assert.equal(el._attrs['aria-hidden'], undefined);
  });

  it('makes all elements inert when isInert is true', () => {
    const elements = [createFakeElement(), createFakeElement()];
    setBackgroundContentInert(elements, true);
    assert.equal(elements[0].inert, true);
    assert.equal(elements[1].inert, true);
  });

  it('restores all elements when isInert is false', () => {
    const elements = [createFakeElement(), createFakeElement()];
    setBackgroundContentInert(elements, true);
    setBackgroundContentInert(elements, false);
    assert.equal(elements[0].inert, false);
    assert.equal(elements[1].inert, false);
  });
});
