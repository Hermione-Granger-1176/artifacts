import assert from 'node:assert/strict';
import test from 'node:test';

import { createHarness, makeEl as harnessMakeEl } from './support.js';
import { EMB_VECS } from '../../../../apps/prompt-caching/js/modules/data.js';
import { byId, makeEl as domMakeEl, clear, prefersReducedMotion, reserveSpace, longestText } from '../../../../apps/prompt-caching/js/modules/dom.js';
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
    assert.equal(byId('nav-fill'), h.el('nav-fill'));
    assert.equal(byId('does-not-exist'), null);
    const node = domMakeEl('span', 'foo', 'hi');
    assert.equal(node.className, 'foo');
    assert.equal(node.textContent, 'hi');
    node.appendChild(domMakeEl('b'));
    clear(node);
    assert.equal(node.children.length, 0);
    // makeEl with no text leaves textContent empty.
    assert.equal(domMakeEl('div').textContent, '');
  });
});

test('prefersReducedMotion follows the media query', () => {
  withHarness((h) => {
    assert.equal(prefersReducedMotion(), false);
    h.state.reducedMotion = true;
    assert.equal(prefersReducedMotion(), true);
  });
});

test('reserveSpace stacks hidden copies beside the live element', () => {
  withHarness(() => {
    const host = harnessMakeEl('div');
    const live = harnessMakeEl('div');
    host.appendChild(live);
    const ghosts = [harnessMakeEl('div'), harnessMakeEl('div')];
    reserveSpace(live, ghosts);
    assert.deepEqual(host.children, [live, ...ghosts]);
    assert.ok(ghosts.every((g) => g.classList.contains('reserve-ghost') && g.getAttribute('aria-hidden') === 'true'));
    assert.ok(!live.classList.contains('reserve-ghost'));
  });
});

test('longestText picks the longest string and tolerates an empty list', () => {
  assert.equal(longestText(['a', 'abc', 'ab']), 'abc');
  assert.equal(longestText([]), '');
});

test('test harness query selectors honor id selectors', () => {
  withHarness((h) => {
    const first = harnessMakeEl('span');
    first.id = 'first-target';
    first.className = 'chip';
    const second = harnessMakeEl('span');
    second.id = 'second-target';
    second.className = 'chip';
    h.el('nav-fill').append(first, second);

    assert.equal(h.el('nav-fill').querySelector('#second-target'), second);
    assert.equal(h.el('nav-fill').querySelector('span#first-target.chip'), first);
    assert.equal(h.el('nav-fill').querySelector('#missing-target'), null);
  });
});

// --- navigation.js ---

test('navigation builds nodes, tracks sections, and renders the timeline', () => {
  withHarness((h) => {
    // Sections 1000px apart on a long page; the scanline sits 280px down.
    h.documentMock.documentElement.scrollHeight = 20000;
    h.sectionIds.forEach((id, index) => { h.el(id).rectTop = index * 1000; });
    initNavigation();
    assert.equal(h.el('nav-nodes').children.length, 9);
    assert.ok(h.el('summaryTimeline').children.length > 0);
    assert.equal(h.el('nav-label').textContent, 'Intro');

    h.el('nav-nodes').children[2].fire('click'); // scrollToSection
    h.el('pipelineDiagram').children[0].fire('click'); // pipeline jump

    globalThis.window.scrollY = 3800;
    h.fireWindow('scroll');
    assert.equal(h.el('nav-label').textContent, 'Attention');
  });
});

test('navigation is a no-op when its anchors are missing', () => {
  withHarness((h) => {
    h.el('nav-nodes').remove();
    delete h.registry['nav-nodes'];
    assert.doesNotThrow(() => initNavigation());
  });
});

// --- tokenizer.js ---

test('tokenizer renders colored tokens and an ID view', () => {
  withHarness((h) => {
    initTokenizer();
    assert.ok(h.el('tokenOutput').children.length > 0);
    assert.notEqual(h.el('tokCount').textContent, '0');

    // Both views stay in the output, stacked; the inactive one is hidden, so the
    // box always fits the taller view.
    const [textLayer, idsLayer] = h.el('tokenOutput').children;
    assert.ok(textLayer.children.length > 0);
    assert.equal(idsLayer.children.length, textLayer.children.filter((c) => c.className.startsWith('pc-tok ')).length);
    assert.ok(!textLayer.classList.contains('is-hidden'));
    assert.ok(idsLayer.classList.contains('is-hidden'));

    h.el('tokenView').children[1].fire('click'); // switch to IDs
    assert.equal(h.el('tokenOutput').children.length, 2);
    assert.ok(textLayer.classList.contains('is-hidden'));
    assert.ok(!idsLayer.classList.contains('is-hidden'));
    assert.ok(idsLayer.children.length > 0);

    h.el('tokenInput').value = '👋';
    h.el('tokenInput').fire('input');
    assert.equal(h.el('charCount').textContent, '1');

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

test('dimension explorer keeps one canvas shape and draws a drag once per frame', () => {
  withHarness((h) => {
    h.state.deferFrames = true;
    h.el('dimCaption').textContent = '1D: long caption.';
    initEmbeddings();
    const canvas = h.el('dimCanvas');
    const shape = [canvas.width, canvas.height];
    const draws = () => canvas.getContext('2d').clears;

    // The 1D, 2D, and 3D views all draw into the bitmap from the markup.
    for (const tab of h.el('dimToggle').children) {
      tab.fire('click');
      assert.deepEqual([canvas.width, canvas.height], shape);
    }

    // Reserved caption room: one hidden copy per mode next to the live caption.
    const caption = h.el('dimCaption');
    assert.equal(caption.parentNode.children.length, 4);
    assert.ok(caption.parentNode.children.slice(1).every((c) => c.classList.contains('reserve-ghost')));
    assert.equal(caption.parentNode.children[1].textContent, '1D: long caption.');

    // A burst of pointermoves in 3D schedules a single draw for the next frame.
    const before = draws();
    canvas.fire('pointerdown', { clientX: 0, clientY: 0 });
    for (let i = 1; i <= 20; i += 1) {
      canvas.fire('pointermove', { clientX: i * 2, clientY: i });
    }
    assert.equal(draws(), before);
    h.flushFrames();
    assert.equal(draws(), before + 1);
    assert.deepEqual([canvas.width, canvas.height], shape);
  });
});

test('selection chips reserve the width of the longest word', () => {
  withHarness((h) => {
    initEmbeddings();
    const longest = Math.max(...Object.keys(EMB_VECS).map((word) => word.length));
    assert.equal(h.el('embSelA').style['--emb-word-ch'], String(longest));
    assert.equal(h.el('embSelB').style['--emb-word-ch'], String(longest));
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

test('inference reserves the final stream and status room before Generate', () => {
  withHarness((h) => {
    initInference();
    // One hidden stream per prompt beside the live one, each already holding its
    // final chips; four hidden status lines (idle, started, step, done).
    const streams = h.el('infTokens').parentNode.children;
    const prompts = h.el('infPrompts').children;
    assert.equal(streams.length, 1 + prompts.length);
    assert.ok(streams.slice(1).every((g) => g.classList.contains('reserve-ghost') && g.children.length > 5));
    assert.equal(h.el('infTokens').children.length, 0);

    const statuses = h.el('infStatus').parentNode.children;
    assert.deepEqual(statuses.slice(1).map((g) => g.textContent), [
      'Hit Generate to start.',
      'Prompt processed (3 tokens cached). Generating...',
      'Step 10: generated "centuries". Only 1 new KV row computed, 12 reused from cache.',
      'Done. 13 total tokens. KV cache has 13 rows.'
    ]);

    // Generating changes only the live elements.
    h.el('infGoBtn').fire('click');
    h.flushIntervals();
    assert.equal(h.el('infTokens').parentNode.children.length, streams.length);
    assert.equal(h.el('infStatus').parentNode.children.length, statuses.length);
  });
});

test('inference jumps to the finished run under reduced motion', () => {
  withHarness((h) => {
    h.state.reducedMotion = true;
    initInference();
    h.el('infGoBtn').fire('click');
    assert.equal(h.intervals.size, 0);
    assert.match(h.el('infStatus').textContent, /^Done\. 13 total tokens/);
    assert.equal(h.el('infCacheCount').textContent, '13');
    assert.equal(h.el('infGoBtn').disabled, false);
    const chips = h.el('infTokens').children;
    assert.equal(chips.length, 13);
    assert.ok(chips.slice(3).every((c) => c.classList.contains('is-amber')));
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
    // Bars keep their width and scale from the left edge.
    const bar = h.el('smxBars').children[0].querySelector('.smx-bar');
    assert.equal(bar.style.width, undefined);
    assert.match(bar.style.transform, /^scaleX\(0\.\d+\)$/);
  });
});

test('attention card reserves its tallest state and re-measures on a width change', () => {
  withHarness((h) => {
    const card = h.el('attnStepCard');
    // The harness has no layout: report a taller card while a calculation is open.
    Object.defineProperty(card, 'offsetHeight', {
      get() {
        const open = h.el('dotProduct').querySelectorAll('.pc-dotcalc').length > 0;
        const scrambled = h.el('attnStepVisual').querySelectorAll('.pc-attn-status').length > 0;
        return 300 + (open ? 50 : 0) + (scrambled ? 40 : 0);
      }
    });
    card.clientWidth = 900;
    const fontsReady = [];
    h.documentMock.fonts = { status: 'loading', ready: { then: (fn) => fontsReady.push(fn) } };
    initAttention();
    // Nothing is measured until the card nears the viewport.
    assert.ok(!card.style.minHeight);
    fontsReady[0]();
    assert.ok(!card.style.minHeight);
    h.fireObservers(0);
    assert.equal(card.style.minHeight, '390px');
    assert.equal(h.el('attnStepTitle').textContent, '1. Compute Q and K');
    assert.equal(h.el('attnStepVisual').querySelectorAll('.pc-attn-status').length, 0);
    assert.equal(fontsReady.length, 1);

    // The user is on step 3 with the mask off when the width changes: both stay.
    h.el('attnStepper').children[2].fire('click');
    const checkbox = h.el('attnStepVisual').querySelector('input');
    checkbox.checked = false;
    checkbox.fire('change');
    h.state.deferFrames = true;
    card.clientWidth = 900; // same width: no re-measure
    h.fireWindow('resize');
    h.flushFrames();
    assert.equal(h.el('attnStepVisual').querySelector('input').checked, false);
    card.style.minHeight = '1px';
    card.clientWidth = 500;
    h.fireWindow('resize');
    h.flushFrames();
    assert.equal(card.style.minHeight, '390px');
    assert.equal(h.el('attnStepTitle').textContent, '3. Mask future tokens');
    assert.equal(h.el('attnStepVisual').querySelector('input').checked, false);

    // Late web fonts trigger one more measurement.
    card.style.minHeight = '1px';
    fontsReady[0]();
    assert.equal(card.style.minHeight, '390px');
  });
});

test('attention card skips the reservation when the fonts are already loaded', () => {
  withHarness((h) => {
    h.documentMock.fonts = { status: 'loaded', ready: { then() { throw new Error('unexpected'); } } };
    initAttention();
    h.fireObservers(0);
    // Without layout the measured height is 0, so no min-height is written.
    assert.equal(h.el('attnStepCard').style.minHeight, '');
  });
});

test('attention card measures at once without IntersectionObserver', () => {
  withHarness((h) => {
    const card = h.el('attnStepCard');
    Object.defineProperty(card, 'offsetHeight', { get: () => 320 });
    delete globalThis.IntersectionObserver;
    initAttention();
    assert.equal(card.style.minHeight, '320px');
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

test('kv cache keeps every row in place and reserves its narration', () => {
  withHarness((h) => {
    initKvCache();
    const rows = (id) => h.el(id).children.filter((c) => c.classList.contains('cache-row'));
    // Before Play every row is already in the layout, hidden, under the empty note.
    assert.equal(rows('kCacheVis').length, 6);
    assert.ok(rows('kCacheVis').every((r) => r.classList.contains('is-pending')));
    assert.equal(h.el('kCacheVis').children[0].className, 'pc-empty');

    h.el('cachePlayBtn').fire('click');
    [...h.intervals.values()][0]();
    [...h.intervals.values()][0]();
    const states = rows('kCacheVis').map((r) => (r.classList.contains('is-pending') ? 'pending' : r.classList.contains('is-new') ? 'new' : 'cached'));
    assert.deepEqual(states, ['cached', 'new', 'pending', 'pending', 'pending', 'pending']);
    assert.equal(rows('kCacheVis').length, rows('vCacheVis').length);

    // A hidden narration per state (idle, four steps, done) beside the live one.
    const narrations = h.el('cacheNarration').parentNode.children;
    assert.equal(narrations.length, 1 + 6);
    assert.ok(narrations.slice(1).every((n) => n.classList.contains('reserve-ghost')));
  });
});

test('kv cache animation shows the full cache under reduced motion', () => {
  withHarness((h) => {
    h.state.reducedMotion = true;
    initKvCache();
    h.el('cachePlayBtn').fire('click');
    assert.equal(h.intervals.size, 0);
    assert.equal(h.el('cachePlayBtn').disabled, false);
    const rows = h.el('kCacheVis').children;
    assert.equal(rows.filter((r) => r.classList.contains('is-pending')).length, 0);
    assert.equal(rows[rows.length - 1].className, 'cache-row is-new');
    assert.match(h.el('cacheNarration').children[0].textContent, /^Done\./);
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

test('kv cache animation preserves vectors for rows already cached', () => {
  withHarness((h) => {
    initKvCache();
    h.el('cachePlayBtn').fire('click');
    const tick = [...h.intervals.values()][0];
    tick();
    const firstKey = h.el('kCacheVis').children[0].children[1].textContent;
    const firstValue = h.el('vCacheVis').children[0].children[1].textContent;

    tick();

    assert.equal(h.el('kCacheVis').children[0].children[1].textContent, firstKey);
    assert.equal(h.el('vCacheVis').children[0].children[1].textContent, firstValue);
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

test('cache hit visualiser scrolls only its own list', () => {
  withHarness((h) => {
    initCacheHits();
    const reqs = h.el('chvReqs');
    reqs.scrollHeight = 900;
    h.el('chvSendBtn').fire('click');
    assert.deepEqual(reqs.scrollCalls, [{ top: 900, behavior: 'smooth' }]);
    h.state.reducedMotion = true;
    h.el('chvSendBtn').fire('click');
    assert.deepEqual(reqs.scrollCalls[1], { top: 900, behavior: 'auto' });
  });
});

test('cache hit visualiser colors blocks at once under reduced motion', () => {
  withHarness((h) => {
    h.state.reducedMotion = true;
    initCacheHits();
    h.el('chvSendBtn').fire('click');
    const req = h.el('chvReqs').children[0];
    const blocks = req.querySelectorAll('.chv-block');
    assert.ok(blocks.length > 8);
    assert.ok(blocks.every((b) => !b.classList.contains('waiting')));
    // Only the TTL countdown is left running.
    assert.equal(h.intervals.size, 1);
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
    assert.equal(h.el('calcBarWith').style.transform, 'scaleX(1)');
    assert.equal(h.el('calcBarWithout').style.transform, 'scaleX(1)');

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
