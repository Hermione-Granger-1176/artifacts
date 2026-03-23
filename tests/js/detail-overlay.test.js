import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { createDetailOverlay } from '../../js/modules/detail-overlay.js';

function createFakeElement(id = '') {
  const classes = new Set();
  const attrs = {};
  const styleProps = {};
  const children = [];
  let focusCalled = false;
  return {
    id,
    dataset: {},
    classList: {
      add(c) { classes.add(c); },
      remove(c) { classes.delete(c); },
      toggle(c, force) { force ? classes.add(c) : classes.delete(c); },
      contains(c) { return classes.has(c); },
      _classes: classes
    },
    getAttribute(name) { return attrs[name] ?? null; },
    setAttribute(name, value) { attrs[name] = value; },
    removeAttribute(name) { delete attrs[name]; },
    hasAttribute(name) { return name in attrs; },
    getBoundingClientRect() {
      return { left: 100, top: 100, width: 400, height: 300 };
    },
    querySelector(selector) {
      if (selector.includes('data-id=')) {
        const match = selector.match(/data-id="([^"]+)"/);
        return children.find((c) => c.dataset.id === match?.[1]) || null;
      }
      if (selector === '.detail-close') {
        return { focus() { focusCalled = true; } };
      }
      return null;
    },
    querySelectorAll(selector) {
      if (selector.includes('artifact-card')) {
        return children;
      }
      return children.filter((c) => c._focusable);
    },
    contains(el) { return children.includes(el); },
    focus() { focusCalled = true; },
    get _focusCalled() { return focusCalled; },
    set _focusCalled(v) { focusCalled = v; },
    style: {
      getPropertyValue(name) { return styleProps[name] || ''; },
      setProperty(name, value) { styleProps[name] = value; },
      removeProperty(name) { delete styleProps[name]; },
      _props: styleProps
    },
    innerHTML: '',
    _attrs: attrs,
    _classes: classes,
    _children: children
  };
}

function createFocusableElement(hidden = false, ariaHidden = null) {
  const attrs = {};
  if (ariaHidden !== null) {
    attrs['aria-hidden'] = ariaHidden;
  }
  if (hidden) {
    attrs['hidden'] = '';
  }
  let focusCalled = false;
  return {
    _focusable: true,
    hasAttribute(name) { return name in attrs; },
    getAttribute(name) { return attrs[name] ?? null; },
    focus() { focusCalled = true; },
    get _focusCalled() { return focusCalled; }
  };
}

function createTestDeps(opts = {}) {
  const detailOverlay = createFakeElement('detail-overlay');
  const detailPanel = createFakeElement('detail-panel');
  const grid = createFakeElement('artifacts-grid');
  const bodyClassAdds = [];
  const bodyClassRemoves = [];
  const body = {
    classList: {
      add(c) { bodyClassAdds.push(c); },
      remove(c) { bodyClassRemoves.push(c); }
    },
    contains() { return opts.bodyContainsTrigger ?? true; }
  };
  const inertCalls = [];

  const rafCallbacks = [];
  const timeoutCallbacks = [];
  let timeoutId = 1;

  return {
    detailOverlay,
    detailPanel,
    grid,
    documentObj: {
      body,
      activeElement: opts.activeElement ?? null
    },
    windowObj: {
      requestAnimationFrame(cb) { rafCallbacks.push(cb); cb(); },
      setTimeout(cb, delay) { timeoutCallbacks.push({ cb, delay }); return timeoutId++; },
      clearTimeout() {}
    },
    motion: {
      prefersReducedMotion() { return opts.reducedMotion ?? true; }
    },
    setBackgroundContentInert(elements, isInert) {
      inertCalls.push({ elements, isInert });
    },
    backgroundElements: [],
    detailCloseDelay: 360,
    _inertCalls: inertCalls,
    _rafCallbacks: rafCallbacks,
    _timeoutCallbacks: timeoutCallbacks,
    _bodyClassAdds: bodyClassAdds,
    _bodyClassRemoves: bodyClassRemoves
  };
}

describe('createDetailOverlay', () => {
  let deps;
  let overlay;
  let artifactById;

  beforeEach(() => {
    deps = createTestDeps();
    overlay = createDetailOverlay(deps);
    artifactById = new Map([
      ['test-1', { id: 'test-1', name: 'Test', url: '/test' }]
    ]);
  });

  it('starts with no expanded overlay', () => {
    assert.equal(overlay.getExpandedId(), null);
  });

  it('getCardById returns null for falsy id', () => {
    assert.equal(overlay.getCardById(null), null);
    assert.equal(overlay.getCardById(''), null);
  });

  it('open sets the overlay to visible state', () => {
    overlay.open('test-1', null, artifactById);
    assert.equal(overlay.getExpandedId(), 'test-1');
    assert.equal(deps.detailOverlay._classes.has('visible'), true);
    assert.equal(deps.detailOverlay._attrs['aria-hidden'], 'false');
    assert.equal(deps.detailPanel._attrs['aria-describedby'], 'detail-description');
    assert.equal(deps._inertCalls.length, 1);
    assert.equal(deps._inertCalls[0].isInert, true);
  });

  it('open is a no-op for unknown artifact id', () => {
    overlay.open('nonexistent', null, artifactById);
    assert.equal(overlay.getExpandedId(), null);
  });

  it('close resets the overlay state', () => {
    overlay.open('test-1', null, artifactById);
    overlay.close({ immediate: true });
    assert.equal(overlay.getExpandedId(), null);
    assert.equal(deps.detailOverlay._classes.has('open'), false);
    assert.equal(deps.detailOverlay._attrs['aria-hidden'], 'true');
    assert.equal(deps.detailOverlay._classes.has('visible'), false);
    assert.equal(deps.detailPanel._attrs['aria-describedby'], undefined);
  });

  it('close is a no-op when nothing is expanded and not visible', () => {
    overlay.close();
    assert.equal(deps._inertCalls.length, 0);
  });

  it('toggle opens when not expanded', () => {
    overlay.toggle('test-1', null, artifactById);
    assert.equal(overlay.getExpandedId(), 'test-1');
  });

  it('toggle closes when same id is expanded', () => {
    overlay.open('test-1', null, artifactById);
    overlay.toggle('test-1', null, artifactById);
    assert.equal(overlay.getExpandedId(), null);
  });

  it('updateExpandedCardState marks cards as expanded', () => {
    const card = createFakeElement();
    card.dataset.id = 'test-1';
    deps.grid._children.push(card);
    overlay.open('test-1', null, artifactById);
    overlay.updateExpandedCardState();
    assert.equal(card._classes.has('expanded'), true);
    assert.equal(card._attrs['aria-expanded'], 'true');
  });

  it('close with immediate clears detail motion properties', () => {
    overlay.open('test-1', null, artifactById);
    overlay.close({ immediate: true });
    assert.equal(deps.detailPanel.style._props['--detail-from-x'], undefined);
  });

  it('close with reduced motion finishes synchronously', () => {
    overlay.open('test-1', null, artifactById);
    overlay.close({ restoreFocus: false });
    assert.equal(overlay.getExpandedId(), null);
    assert.equal(deps.detailOverlay._classes.has('visible'), false);
  });

  it('close with restoreFocus focuses the trigger card', () => {
    const triggerCard = createFakeElement();
    triggerCard.dataset.id = 'test-1';
    triggerCard.getBoundingClientRect = () => ({ left: 50, top: 50, width: 200, height: 150 });
    deps.grid._children.push(triggerCard);

    overlay.open('test-1', triggerCard, artifactById);
    overlay.close({ restoreFocus: true, immediate: true });
    assert.equal(triggerCard._focusCalled, true);
  });

  it('close with animation uses setTimeout when motion is allowed', () => {
    const animDeps = createTestDeps({ reducedMotion: false });
    const animOverlay = createDetailOverlay(animDeps);
    animOverlay.open('test-1', null, artifactById);

    animOverlay.close({ restoreFocus: false, immediate: false });
    assert.equal(animOverlay.getExpandedId(), null);
    assert.equal(animDeps._timeoutCallbacks.length, 1);
    assert.equal(animDeps._timeoutCallbacks[0].delay, 360);
    assert.equal(animDeps.detailOverlay._classes.has('visible'), true);

    animDeps._timeoutCallbacks[0].cb();
    assert.equal(animDeps.detailOverlay._classes.has('visible'), false);
  });
});

describe('detail overlay applyDetailMotion', () => {
  it('sets CSS custom properties when motion is allowed', () => {
    const deps = createTestDeps({ reducedMotion: false });
    const overlay = createDetailOverlay(deps);
    const artifactById = new Map([
      ['test-1', { id: 'test-1', name: 'Test', url: '/test' }]
    ]);

    const triggerCard = createFakeElement();
    triggerCard.getBoundingClientRect = () => ({ left: 50, top: 50, width: 200, height: 150 });

    overlay.open('test-1', triggerCard, artifactById);

    assert.ok(deps.detailPanel.style._props['--detail-from-x'] !== undefined);
    assert.ok(deps.detailPanel.style._props['--detail-from-y'] !== undefined);
    assert.ok(deps.detailPanel.style._props['--detail-from-scale-x'] !== undefined);
    assert.ok(deps.detailPanel.style._props['--detail-from-scale-y'] !== undefined);
  });

  it('skips CSS properties when reduced motion is preferred', () => {
    const deps = createTestDeps({ reducedMotion: true });
    const overlay = createDetailOverlay(deps);
    const artifactById = new Map([
      ['test-1', { id: 'test-1', name: 'Test', url: '/test' }]
    ]);

    overlay.open('test-1', null, artifactById);

    assert.equal(deps.detailPanel.style._props['--detail-from-x'], undefined);
  });
});

describe('detail overlay trapFocus', () => {
  it('returns false when no overlay is expanded', () => {
    const deps = createTestDeps();
    const overlay = createDetailOverlay(deps);
    const event = { key: 'Tab', shiftKey: false, preventDefault() {} };
    assert.equal(overlay.trapFocus(event), false);
  });

  it('focuses panel when no focusable elements exist', () => {
    const deps = createTestDeps();
    const overlay = createDetailOverlay(deps);
    const artifactById = new Map([['a', { id: 'a', name: 'A', url: '/' }]]);
    overlay.open('a', null, artifactById);

    let prevented = false;
    const event = { shiftKey: false, preventDefault() { prevented = true; } };
    const result = overlay.trapFocus(event);
    assert.equal(result, true);
    assert.equal(prevented, true);
    assert.equal(deps.detailPanel._focusCalled, true);
  });

  it('wraps forward focus from last to first element', () => {
    const deps = createTestDeps();
    const first = createFocusableElement();
    const last = createFocusableElement();
    deps.detailPanel._children.push(first, last);
    deps.detailPanel.contains = (el) => el === first || el === last;
    deps.documentObj.activeElement = last;

    const overlay = createDetailOverlay(deps);
    const artifactById = new Map([['a', { id: 'a', name: 'A', url: '/' }]]);
    overlay.open('a', null, artifactById);

    let prevented = false;
    const result = overlay.trapFocus({ shiftKey: false, preventDefault() { prevented = true; } });
    assert.equal(result, true);
    assert.equal(prevented, true);
    assert.equal(first._focusCalled, true);
  });

  it('wraps backward focus from first to last element', () => {
    const deps = createTestDeps();
    const first = createFocusableElement();
    const last = createFocusableElement();
    deps.detailPanel._children.push(first, last);
    deps.detailPanel.contains = (el) => el === first || el === last;
    deps.documentObj.activeElement = first;

    const overlay = createDetailOverlay(deps);
    const artifactById = new Map([['a', { id: 'a', name: 'A', url: '/' }]]);
    overlay.open('a', null, artifactById);

    let prevented = false;
    const result = overlay.trapFocus({ shiftKey: true, preventDefault() { prevented = true; } });
    assert.equal(result, true);
    assert.equal(prevented, true);
    assert.equal(last._focusCalled, true);
  });

  it('returns false when focus is between first and last (forward)', () => {
    const deps = createTestDeps();
    const first = createFocusableElement();
    const middle = createFocusableElement();
    const last = createFocusableElement();
    deps.detailPanel._children.push(first, middle, last);
    deps.detailPanel.contains = () => true;
    deps.documentObj.activeElement = middle;

    const overlay = createDetailOverlay(deps);
    const artifactById = new Map([['a', { id: 'a', name: 'A', url: '/' }]]);
    overlay.open('a', null, artifactById);

    const result = overlay.trapFocus({ shiftKey: false, preventDefault() {} });
    assert.equal(result, false);
  });

  it('returns false when focus is between first and last (backward)', () => {
    const deps = createTestDeps();
    const first = createFocusableElement();
    const middle = createFocusableElement();
    const last = createFocusableElement();
    deps.detailPanel._children.push(first, middle, last);
    deps.detailPanel.contains = () => true;
    deps.documentObj.activeElement = middle;

    const overlay = createDetailOverlay(deps);
    const artifactById = new Map([['a', { id: 'a', name: 'A', url: '/' }]]);
    overlay.open('a', null, artifactById);

    const result = overlay.trapFocus({ shiftKey: true, preventDefault() {} });
    assert.equal(result, false);
  });

  it('filters out hidden and aria-hidden elements', () => {
    const deps = createTestDeps();
    const hidden = createFocusableElement(true);
    const ariaHidden = createFocusableElement(false, 'true');
    deps.detailPanel._children.push(hidden, ariaHidden);

    const overlay = createDetailOverlay(deps);
    const artifactById = new Map([['a', { id: 'a', name: 'A', url: '/' }]]);
    overlay.open('a', null, artifactById);

    let prevented = false;
    const result = overlay.trapFocus({ shiftKey: false, preventDefault() { prevented = true; } });
    assert.equal(result, true);
    assert.equal(deps.detailPanel._focusCalled, true);
  });

  it('wraps focus when active element is outside the panel', () => {
    const deps = createTestDeps();
    const btn = createFocusableElement();
    deps.detailPanel._children.push(btn);
    deps.detailPanel.contains = () => false;
    deps.documentObj.activeElement = { tagName: 'BODY' };

    const overlay = createDetailOverlay(deps);
    const artifactById = new Map([['a', { id: 'a', name: 'A', url: '/' }]]);
    overlay.open('a', null, artifactById);

    let prevented = false;
    const result = overlay.trapFocus({ shiftKey: false, preventDefault() { prevented = true; } });
    assert.equal(result, true);
    assert.equal(btn._focusCalled, true);
  });

  it('wraps backward focus when active element is outside the panel', () => {
    const deps = createTestDeps();
    const btn = createFocusableElement();
    deps.detailPanel._children.push(btn);
    deps.detailPanel.contains = () => false;
    deps.documentObj.activeElement = { tagName: 'BODY' };

    const overlay = createDetailOverlay(deps);
    const artifactById = new Map([['a', { id: 'a', name: 'A', url: '/' }]]);
    overlay.open('a', null, artifactById);

    let prevented = false;
    const result = overlay.trapFocus({ shiftKey: true, preventDefault() { prevented = true; } });
    assert.equal(result, true);
    assert.equal(btn._focusCalled, true);
  });
});
