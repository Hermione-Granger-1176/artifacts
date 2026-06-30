import assert from 'node:assert/strict';
import test from 'node:test';

import { createHarness } from './support.js';
import { byId, cssVar, makeEl as domMakeEl, clear } from '../../../../apps/prompt-caching/js/modules/dom.js';
import { initNavigation } from '../../../../apps/prompt-caching/js/modules/navigation.js';
import { initTokenizer } from '../../../../apps/prompt-caching/js/modules/tokenizer.js';
import { initEmbeddings } from '../../../../apps/prompt-caching/js/modules/embeddings.js';
import { initInference } from '../../../../apps/prompt-caching/js/modules/inference.js';
import { initAttention } from '../../../../apps/prompt-caching/js/modules/attention.js';
import { initKvCache } from '../../../../apps/prompt-caching/js/modules/kv-cache.js';
import { initCacheHits } from '../../../../apps/prompt-caching/js/modules/cache-hits.js';
import { initCalculator } from '../../../../apps/prompt-caching/js/modules/calculator.js';

function withHarness(run) {
  const harness = createHarness();
  harness.install();
  try {
    run(harness);
  } finally {
    harness.teardown();
  }
}

// --- dom.js ---

test('dom helpers read, build, and clear nodes', () => {
  withHarness((h) => {
    assert.equal(byId('navFill'), h.el('navFill'));
    assert.equal(byId('does-not-exist'), null);
    const node = domMakeEl('span', 'foo', 'hi');
    assert.equal(node.className, 'foo');
    assert.equal(node.textContent, 'hi');
    node.appendChild(domMakeEl('b'));
    clear(node);
    assert.equal(node.children.length, 0);
    assert.equal(typeof cssVar('--color-amber'), 'string');
    // makeEl with no text leaves textContent empty.
    assert.equal(domMakeEl('div').textContent, '');
  });
});

// --- navigation.js ---

test('navigation builds nodes, tracks sections, and renders the timeline', () => {
  withHarness((h) => {
    initNavigation();
    assert.equal(h.el('navNodes').children.length, 9);
    assert.ok(h.el('summaryTimeline').children.length > 0);

    h.el('navNodes').children[2].fire('click'); // scrollToSection
    h.el('pipelineDiagram').children[0].fire('click'); // pipeline jump

    h.fireObservers(0);
    assert.equal(h.el('navLabel').textContent, 'Intro');
    h.fireObservers(4);
    assert.equal(h.el('navLabel').textContent, 'Attention');
  });
});

test('navigation is a no-op when its anchors are missing', () => {
  withHarness((h) => {
    h.el('navNodes').remove();
    delete h.registry.navNodes;
    assert.doesNotThrow(() => initNavigation());
  });
});

// --- tokenizer.js ---

test('tokenizer renders coloured tokens and an ID view', () => {
  withHarness((h) => {
    initTokenizer();
    assert.ok(h.el('tokenOutput').children.length > 0);
    assert.notEqual(h.el('tokCount').textContent, '0');

    h.el('tokenView').children[1].fire('click'); // switch to IDs
    assert.ok(h.el('tokenOutput').children.length > 0);

    h.el('tokenInput').value = '';
    h.el('tokenInput').fire('input');
    assert.equal(h.el('tokCount').textContent, '0');
  });
});

// --- embeddings.js ---

test('embeddings drives the dimension explorer and similarity playground', () => {
  withHarness((h) => {
    const api = initEmbeddings();
    assert.ok(h.el('embCloud').children.length > 0);

    h.el('dimToggle').children[1].fire('click'); // 2D
    h.el('dimToggle').children[2].fire('click'); // 3D
    h.el('dimToggle').children[0].fire('click'); // back to 1D

    const words = h.el('embCloud').children;
    words[0].fire('click'); // pick A
    words[1].fire('click'); // pick B
    words[2].fire('keydown', { key: 'Enter', preventDefault() {} }); // keyboard pick A
    assert.equal(h.el('embSelA').textContent, words[2].dataset.word);
    words[3].fire('keydown', { key: ' ', preventDefault() {} }); // keyboard pick B
    assert.equal(h.el('embSelB').textContent, words[3].dataset.word);
    h.el('embSuggestions').children[0].fire('click'); // quick pair
    h.el('embSuggestions').children[1].fire('keydown', { key: 'Enter', preventDefault() {} }); // keyboard quick pair
    assert.equal(h.el('embSelA').textContent, 'happy');
    assert.equal(h.el('embSelB').textContent, 'sad');
    h.el('embSwapBtn').fire('click');

    api.redraw();
    assert.ok(h.el('embSimilarity').textContent.length > 0);
  });
});

// --- inference.js ---

test('inference streams tokens to completion and resets', () => {
  withHarness((h) => {
    initInference();
    h.el('infGoBtn').fire('click');
    h.flushIntervals();
    assert.match(h.el('infStatus').textContent, /Done\./);
    assert.notEqual(h.el('infCacheCount').textContent, '0');

    h.el('infResetBtn').fire('click');
    assert.equal(h.el('infCacheCount').textContent, '0');

    h.el('infInput').value = '   ';
    h.el('infGoBtn').fire('click'); // empty -> early return
    assert.equal(h.el('infTokens').children.length, 0);
  });
});

// --- attention.js ---

test('attention steps, grid hover, and softmax sliders all respond', () => {
  withHarness((h) => {
    initAttention();
    const visual = h.el('attnStepVisual');

    // Step 1: Q = emb * WQ
    visual.querySelectorAll('[data-mx="Q1"].clickable')[0].fire('click');

    // Step 2: scores
    h.el('attnStepper').children[1].fire('click');
    visual.querySelectorAll('[data-mx="scores2"].clickable')[0].fire('click');

    // Step 3: mask toggle off then back on
    h.el('attnStepper').children[2].fire('click');
    const checkbox = visual.querySelector('input');
    checkbox.checked = false;
    checkbox.fire('change');

    // Step 4: softmax weights — masked (c>r) and real (c<=r) cells
    h.el('attnStepper').children[3].fire('click');
    const weightCells = visual.querySelectorAll('[data-mx="wt4"].clickable');
    weightCells.find((c) => c.dataset.r === '0' && c.dataset.c === '1').fire('click'); // masked
    weightCells.find((c) => c.dataset.r === '1' && c.dataset.c === '0').fire('click'); // real

    // Step 5: output
    h.el('attnStepper').children[4].fire('click');
    visual.querySelectorAll('[data-mx="out5"].clickable')[0].fire('click');

    // Attention grid hover: first row (zeros + a "next" word) and last row ("...").
    const rows = h.el('attnGrid').querySelectorAll('tr[data-row]');
    rows[0].fire('mouseenter');
    rows[rows.length - 1].fire('mouseenter');
    assert.ok(h.el('attnCaption').children.length > 0);

    // Softmax slider.
    const slider = h.el('smxSliders').querySelectorAll('input')[0];
    slider.value = '4';
    slider.fire('input');
    assert.ok(h.el('smxBars').children.length === 4);
  });
});

// --- kv-cache.js ---

test('kv cache animation plays and the compare toggle switches modes', () => {
  withHarness((h) => {
    initKvCache();
    h.el('cachePlayBtn').fire('click');
    h.flushIntervals();
    assert.ok(h.el('cacheNarration').textContent.length > 0 || h.el('cacheNarration').children.length > 0);
    h.el('cacheResetBtn').fire('click');

    h.el('cacheCompareToggle').children[1].fire('click'); // with cache
    h.el('cacheCompareToggle').children[0].fire('click'); // no cache
    assert.ok(h.el('cacheCompareVis').children.length > 0);
  });
});

// --- cache-hits.js ---

test('cache hit visualiser handles cold start, hits, eviction, TTL, and clear', () => {
  withHarness((h) => {
    initCacheHits();
    for (let i = 0; i < 7; i += 1) {
      h.el('chvSendBtn').fire('click');
    }
    h.flushTimeouts();
    h.flushIntervals(); // drives block animations + TTL to expiry
    assert.equal(h.el('chvTTL').textContent, 'expired');

    h.el('chvClearBtn').fire('click');
    assert.equal(h.el('chvTTL').textContent, '5:00');
  });
});

// --- calculator.js ---

test('calculator updates spend figures from the sliders', () => {
  withHarness((h) => {
    initCalculator();
    assert.match(h.el('calcWithout').textContent, /^\$/);

    h.el('calcHit').value = '0';
    h.el('calcHit').fire('input');
    assert.equal(h.el('calcHitVal').textContent, '0%');
  });
});

// --- app.js entry wiring ---

test('app.js initialises every demo and re-draws on theme change', async () => {
  const harness = createHarness();
  harness.install();
  try {
    await import('../../../../apps/prompt-caching/js/app.js');
    assert.equal(globalThis.window.__ARTIFACT_READY__, true);
    // Theme toggle triggers the embeddings redraw callback without throwing.
    harness.el('theme-toggle').fire('click');
  } finally {
    harness.teardown();
  }
});
