import assert from 'node:assert/strict';
import test from 'node:test';

import { createHarness, makeEl as harnessMakeEl } from './support.js';
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

test('test harness query selectors honor id selectors', () => {
  withHarness((h) => {
    const first = harnessMakeEl('span');
    first.id = 'first-target';
    first.className = 'chip';
    const second = harnessMakeEl('span');
    second.id = 'second-target';
    second.className = 'chip';
    h.el('navFill').append(first, second);

    assert.equal(h.el('navFill').querySelector('#second-target'), second);
    assert.equal(h.el('navFill').querySelector('span#first-target.chip'), first);
    assert.equal(h.el('navFill').querySelector('#missing-target'), null);
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

test('tokenizer renders colored tokens and an ID view', () => {
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

    const dimCanvas = h.el('dimCanvas');
    dimCanvas.fire('pointerdown', { clientX: 10, clientY: 10 }); // ignored in 1D
    h.el('dimToggle').children[1].fire('click'); // 2D
    assert.ok(!dimCanvas.classList.contains('is-rotatable'));
    h.el('dimToggle').children[2].fire('click'); // 3D
    assert.ok(dimCanvas.classList.contains('is-rotatable'));
    dimCanvas.fire('pointermove', { clientX: 20, clientY: 20 }); // no drag yet
    dimCanvas.fire('pointerdown', { clientX: 10, clientY: 10 });
    dimCanvas.fire('pointermove', { clientX: 40, clientY: 25 }); // rotates
    dimCanvas.fire('pointerup', {});
    dimCanvas.fire('pointerleave', {});
    h.el('dimToggle').children[0].fire('click'); // back to 1D
    assert.ok(!dimCanvas.classList.contains('is-rotatable'));

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

    // Category tabs swap which words the cloud shows.
    const catTabs = h.el('embCats').children;
    assert.ok(catTabs.length >= 2);
    assert.ok(catTabs[0].classList.contains('active'));
    catTabs[1].fire('click');
    assert.ok(catTabs[1].classList.contains('active'));
    assert.notEqual(h.el('embCloud').children[0].dataset.word, words[0].dataset.word);

    // Hovering the map highlights the nearest background word; clicking selects it.
    const embCanvas = h.el('embCanvas');
    let hit = false;
    for (let x = 0; x < 400 && !hit; x += 10) {
      for (let y = 0; y < 300 && !hit; y += 10) {
        embCanvas.fire('pointermove', { offsetX: x, offsetY: y });
        hit = embCanvas.style.cursor === 'pointer';
      }
    }
    assert.ok(hit, 'expected some pointer position to hover a background dot');
    const before = h.el('embSelA').textContent;
    embCanvas.fire('click', {});
    assert.notEqual(h.el('embSelA').textContent, before);
    embCanvas.fire('pointermove', { offsetX: 0, offsetY: 0 }); // move off the dot
    embCanvas.fire('pointerleave', {});
    assert.equal(embCanvas.style.cursor, '');

    api.redraw();
    assert.ok(h.el('embSimilarity').textContent.length > 0);
  });
});

// --- inference.js ---

test('inference streams tokens to completion and resets', () => {
  withHarness((h) => {
    initInference();
    const chips = h.el('infPrompts').children;
    assert.ok(chips.length >= 3);
    assert.ok(chips[0].classList.contains('active'));

    h.el('infGoBtn').fire('click');
    chips[1].fire('click'); // ignored while generating
    assert.ok(chips[0].classList.contains('active'));
    h.flushIntervals();
    assert.match(h.el('infStatus').textContent, /Done\./);
    assert.notEqual(h.el('infCacheCount').textContent, '0');

    chips[1].fire('click'); // switching prompts clears the finished run
    assert.ok(chips[1].classList.contains('active'));
    assert.equal(h.el('infCacheCount').textContent, '0');
    chips[1].fire('click'); // re-clicking the selected prompt is a no-op
    assert.ok(chips[1].classList.contains('active'));

    h.el('infGoBtn').fire('click');
    h.flushIntervals();
    h.el('infResetBtn').fire('click');
    assert.equal(h.el('infCacheCount').textContent, '0');
    assert.equal(h.el('infTokens').children.length, 0);
  });
});

// --- attention.js ---

test('attention steps, grid hover, and softmax sliders all respond', () => {
  withHarness((h) => {
    initAttention();
    const visual = h.el('attnStepVisual');

    // Step 1: output = emb * W with a Q/K toggle and a weight scrambler.
    const cellText = () => visual.querySelectorAll('[data-mx="out1"]')[0].textContent;
    assert.equal(cellText(), '0.15');
    visual.querySelectorAll('[data-mx="out1"].clickable')[0].fire('click');

    const findButton = (label) =>
      visual.querySelectorAll('button').find((b) => b.textContent === label);
    findButton('WK → K').fire('click');
    assert.equal(cellText(), '-0.21');
    visual.querySelectorAll('[data-mx="out1"].clickable')[0].fire('click');

    // Scramble with a stubbed RNG: every weight becomes 0.50.
    const realRandom = Math.random;
    Math.random = () => 0.75;
    try {
      findButton('Scramble weights').fire('click');
    } finally {
      Math.random = realRandom;
    }
    // Row 1 of emb sums to -0.23, so every scrambled cell is -0.23 * 0.5.
    assert.equal(cellText(), '-0.11');
    assert.ok(visual.querySelectorAll('.pc-attn-status').length === 1);
    visual.querySelectorAll('[data-mx="out1"].clickable')[0].fire('click');

    // Picking a projection restores the trained weights.
    findButton('WQ → Q').fire('click');
    assert.equal(cellText(), '0.15');
    assert.ok(visual.querySelectorAll('.pc-attn-status').length === 0);

    // Step 2: scores
    h.el('attnStepper').children[1].fire('click');
    visual.querySelectorAll('[data-mx="scores2"].clickable')[0].fire('click');

    // Step 3: mask toggle off then back on
    h.el('attnStepper').children[2].fire('click');
    const checkbox = visual.querySelector('input');
    checkbox.checked = false;
    checkbox.fire('change');

    // Step 4: softmax weights with masked (c>r) and real (c<=r) cells
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
    assert.ok(h.el('smxBars').children.length === 6);
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

test('kv cache animation clears stale rows before replaying', () => {
  withHarness((h) => {
    initKvCache();
    h.el('cachePlayBtn').fire('click');
    [...h.intervals.values()][0]();
    assert.equal(h.el('kCacheVis').children[0].className, 'cache-row is-new');

    h.el('cachePlayBtn').fire('click');

    assert.equal(h.el('kCacheVis').children[0].className, 'pc-empty');
    assert.equal(h.el('vCacheVis').children[0].className, 'pc-empty');
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
    assert.match(h.el('calcPct').textContent, /cheaper/);
    assert.match(h.el('calcTokens').textContent, /M$/);

    // Defaults match the Startup preset, so its chip starts active.
    const chips = h.el('calcPresets').querySelectorAll('button');
    assert.ok(chips.find((b) => b.textContent === 'Startup').classList.contains('active'));

    h.el('calcHit').value = '0';
    h.el('calcHit').fire('input');
    assert.equal(h.el('calcHitVal').textContent, '0%');
    // Manual slider moves deactivate every preset chip.
    assert.ok(chips.every((b) => !b.classList.contains('active')));
    assert.equal(h.el('calcBarWith').style.width, '100%');

    // Preset click drives all four sliders and re-activates its chip.
    chips.find((b) => b.textContent === 'Scale').fire('click');
    assert.equal(h.el('calcSys').value, '8000');
    assert.equal(h.el('calcReq').value, '5000');
    assert.ok(chips.find((b) => b.textContent === 'Scale').classList.contains('active'));
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
