import assert from 'node:assert/strict';
import test from 'node:test';

import { initAccordion } from '../../../../apps/tokenizer-explorer/js/modules/accordion.js';
import {
  renderDistribution,
  renderScenario,
  renderTabs,
  renderTokenExamples
} from '../../../../apps/tokenizer-explorer/js/modules/render.js';
import { scenarios } from '../../../../apps/tokenizer-explorer/js/modules/scenarios.js';
import {
  characterCount,
  formatTokenForDisplay,
  getTokenExampleStats,
  tokenExamples
} from '../../../../apps/tokenizer-explorer/js/modules/token-examples.js';

function makeElement(tagName = 'div') {
  const classes = new Set();
  const attrs = {};
  return {
    tagName,
    className: '',
    children: [],
    innerHTML: '',
    style: {},
    textContent: '',
    title: '',
    type: '',
    classList: {
      contains(className) { return classes.has(className); },
      toggle(className, force) {
        const next = force ?? !classes.has(className);
        next ? classes.add(className) : classes.delete(className);
        return next;
      }
    },
    addEventListener() {},
    append(...nodes) { this.children.push(...nodes); },
    appendChild(child) { this.children.push(child); return child; },
    getAttribute(name) { return attrs[name] ?? null; },
    setAttribute(name, value) { attrs[name] = value; }
  };
}

function setupDocumentMock() {
  const originalDocument = globalThis.document;
  const originalGetComputedStyle = globalThis.getComputedStyle;
  globalThis.document = {
    body: {},
    documentElement: { getAttribute() { return 'light'; } },
    createElement(tagName) { return makeElement(tagName); }
  };
  globalThis.getComputedStyle = () => ({
    getPropertyValue() { return 'rgb(100, 150, 200)'; }
  });
  return { originalDocument, originalGetComputedStyle };
}

function restoreDocument({ originalDocument, originalGetComputedStyle }) {
  if (originalDocument) globalThis.document = originalDocument; else delete globalThis.document;
  if (originalGetComputedStyle) globalThis.getComputedStyle = originalGetComputedStyle;
  else delete globalThis.getComputedStyle;
}

// --- scenarios.js ---

test('scenarios exports valid sorted next-token data', () => {
  assert.ok(Array.isArray(scenarios));
  assert.ok(scenarios.length > 0);

  for (const scenario of scenarios) {
    assert.ok(typeof scenario.label === 'string' && scenario.label.length > 0);
    assert.ok(typeof scenario.type === 'string');
    assert.ok(typeof scenario.prefix === 'string');
    assert.ok(Array.isArray(scenario.tokens) && scenario.tokens.length > 0);

    for (let index = 0; index < scenario.tokens.length; index += 1) {
      const token = scenario.tokens[index];
      assert.ok(typeof token.word === 'string' && token.word.length > 0);
      assert.ok(Number.isFinite(token.baseLogit));
      if (index > 0) {
        assert.ok(scenario.tokens[index - 1].baseLogit >= token.baseLogit);
      }
    }
  }
});

// --- token-examples.js ---

test('token examples reconstruct their source text and report matching counts', () => {
  assert.equal(tokenExamples.length, 4);
  for (const example of tokenExamples) {
    assert.equal(example.tokens.join(''), example.text);
    const stats = getTokenExampleStats(example);
    assert.equal(stats.tokenCount, example.tokens.length);
    assert.equal(stats.characterCount, characterCount(example.text));
  }
});

test('token example helpers preserve text and expose leading whitespace', () => {
  assert.equal(formatTokenForDisplay(' hello', false), ' hello');
  assert.equal(formatTokenForDisplay(' hello', true), '·hello');
  assert.equal(formatTokenForDisplay('  ', true), '··');
  assert.equal(characterCount('👋🏽'), 2);
});

// --- accordion.js ---

test('initAccordion toggles a card open and updates aria state', () => {
  let clickHandler;
  const container = {
    addEventListener(type, handler) {
      if (type === 'click') clickHandler = handler;
    }
  };
  initAccordion(container);

  let cardOpen = false;
  const card = { classList: { toggle() { cardOpen = !cardOpen; return cardOpen; } } };
  const ariaValues = [];
  const trigger = {
    closest(selector) { return selector === '.card' ? card : null; },
    setAttribute(name, value) { if (name === 'aria-expanded') ariaValues.push(value); }
  };

  clickHandler({
    target: { closest(selector) { return selector === '.card-trigger' ? trigger : null; } }
  });

  assert.equal(cardOpen, true);
  assert.deepEqual(ariaValues, ['true']);
});

test('initAccordion ignores a click without a usable trigger and card', () => {
  let clickHandler;
  initAccordion({ addEventListener(_type, handler) { clickHandler = handler; } });
  clickHandler({ target: { closest() { return null; } } });
  clickHandler({
    target: {
      closest(selector) {
        return selector === '.card-trigger' ? { closest() { return null; } } : null;
      }
    }
  });
});

// --- render.js ---

test('renderScenario writes a temporary sampled completion when provided', () => {
  const completion = makeElement('span');
  const elements = {
    scenarioType: makeElement(),
    sentencePrefix: makeElement(),
    sentenceCompletion: completion
  };

  renderScenario(elements, { type: 'Code completion', prefix: 'function add(' }, 'value');
  assert.equal(elements.scenarioType.textContent, 'Code completion');
  assert.equal(elements.sentencePrefix.textContent, 'function add(');
  assert.equal(completion.textContent, 'value');
  assert.equal(completion.classList.contains('has-choice'), true);

  renderScenario(elements, { type: 'Code completion', prefix: 'function add(' });
  assert.equal(completion.textContent, '');
  assert.equal(completion.classList.contains('has-choice'), false);
});

test('renderTabs creates an active button for the selected scenario', () => {
  const mocks = setupDocumentMock();
  try {
    const container = makeElement();
    const buttons = renderTabs(container, [{ label: 'A' }, { label: 'B' }, { label: 'C' }], 1);
    assert.equal(container.children.length, 3);
    assert.equal(container.children[0].textContent, 'A');
    assert.equal(container.children[0].className, '');
    assert.equal(container.children[1].className, 'active');
    assert.equal(buttons.length, 3);
    assert.equal(buttons[1], container.children[1]);
  } finally {
    restoreDocument(mocks);
  }
});

test('renderTokenExamples creates rows, chips, and count copy', () => {
  const mocks = setupDocumentMock();
  try {
    const container = makeElement();
    renderTokenExamples(container, true);
    assert.equal(container.children.length, tokenExamples.length);
    const emojiRow = container.children[2];
    assert.match(emojiRow.children[0].children[1].textContent, /12 tokens/);
    assert.equal(emojiRow.children[2].children[1].textContent, '·');
    assert.match(emojiRow.children[2].children[0].className, /chip is-mono token-chip/);
  } finally {
    restoreDocument(mocks);
  }
});

test('renderDistribution renders renormalized pills, insights, and sample status', () => {
  const mocks = setupDocumentMock();
  try {
    const elements = {
      insightBox: makeElement(),
      sampleStatus: makeElement(),
      tokenPills: makeElement()
    };
    renderDistribution(elements, {
      selectedTokenIndex: 1,
      temperature: 1,
      topP: 0.9,
      topTokens: [
        { adjustedProb: 0.7, idx: 0, word: 'hello' },
        { adjustedProb: 0.3, idx: 1, word: 'world' }
      ],
      sampleCounts: new Map([[0, 70], [1, 30]])
    });

    assert.equal(elements.tokenPills.children.length, 2);
    assert.match(elements.tokenPills.children[0].textContent, /70.0%/);
    assert.match(elements.tokenPills.children[0].className, /chip is-mono pill/);
    assert.match(elements.tokenPills.children[1].className, /winner/);
    assert.match(elements.tokenPills.children[1].className, /is-green/);
    assert.match(elements.insightBox.textContent, /temperature/i);
    assert.match(elements.sampleStatus.textContent, /100 draws/);
  } finally {
    restoreDocument(mocks);
  }
});

test('renderDistribution explains greedy and high-temperature extremes', () => {
  const mocks = setupDocumentMock();
  try {
    const elements = { insightBox: makeElement(), tokenPills: makeElement() };
    const state = {
      selectedTokenIndex: null,
      topP: 1,
      topTokens: [{ adjustedProb: 1, idx: 0, word: 'top' }],
      sampleCounts: null
    };
    renderDistribution(elements, { ...state, temperature: 0 });
    assert.match(elements.insightBox.textContent, /greedy decoding/);
    renderDistribution(elements, { ...state, temperature: 2.5 });
    assert.match(elements.insightBox.textContent, /spreads out widely/);
  } finally {
    restoreDocument(mocks);
  }
});
