import assert from 'node:assert/strict';
import test from 'node:test';

import { buildCandidateRows } from '../../../../apps/tokenizer-explorer/js/modules/candidates.js';
import { initAccordion } from '../../../../apps/tokenizer-explorer/js/modules/accordion.js';
import {
  renderDistribution,
  renderScenario,
  renderScenarioOptions,
  renderTokenExamples
} from '../../../../apps/tokenizer-explorer/js/modules/render.js';
import { scenarios } from '../../../../apps/tokenizer-explorer/js/modules/scenarios.js';
import {
  characterCount,
  formatTokenForDisplay,
  getTokenExampleStats,
  splitPromptTokens,
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
    hidden: false,
    value: '',
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
    replaceChildren(...nodes) { this.children = [...nodes]; },
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

test('splitPromptTokens keeps each leading space and rejoins to the prompt', () => {
  assert.deepEqual(splitPromptTokens('The cat sat'), ['The', ' cat', ' sat']);
  assert.deepEqual(splitPromptTokens('function getUser() { return'), [
    'function',
    ' getUser()',
    ' {',
    ' return'
  ]);
  for (const scenario of scenarios) {
    assert.equal(splitPromptTokens(scenario.prefix).join(''), scenario.prefix);
  }
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

test('renderScenario renders the prompt as toned token chips and a temporary completion', () => {
  const mocks = setupDocumentMock();
  try {
    const completion = makeElement('span');
    const elements = {
      scenarioType: makeElement(),
      sentencePrefix: makeElement(),
      sentenceCompletion: completion
    };

    renderScenario(elements, { type: 'Code completion', prefix: 'function add(' }, 'value');
    assert.equal(elements.scenarioType.textContent, 'Code completion');
    assert.deepEqual(
      elements.sentencePrefix.children.map((chip) => chip.textContent),
      ['function', ' add(']
    );
    assert.match(elements.sentencePrefix.children[0].className, /chip is-mono token-chip prompt-chip is-blue/);
    assert.match(elements.sentencePrefix.children[1].className, /is-green/);
    assert.equal(completion.textContent, 'value');
    assert.equal(completion.classList.contains('has-choice'), true);

    renderScenario(elements, { type: 'Code completion', prefix: 'function add(' });
    assert.equal(completion.textContent, '');
    assert.equal(completion.classList.contains('has-choice'), false);

    renderScenario(elements, { type: 'Code completion', prefix: 'function add(' }, null, true);
    assert.equal(elements.sentencePrefix.children[1].textContent, '·add(');

    // The completion blank is optional, so a bare prompt still renders.
    renderScenario(
      { scenarioType: makeElement(), sentencePrefix: makeElement() },
      { type: 'Sentence', prefix: 'Hello world' }
    );
  } finally {
    restoreDocument(mocks);
  }
});

test('renderScenarioOptions lists scenario labels only and selects the active one', () => {
  const mocks = setupDocumentMock();
  try {
    const select = makeElement('select');
    renderScenarioOptions(select, scenarios, 2);
    assert.equal(select.children.length, scenarios.length);
    assert.deepEqual(
      select.children.map((option) => option.textContent),
      scenarios.map((scenario) => scenario.label)
    );
    assert.equal(select.children[2].value, '2');
    assert.equal(select.value, '2');
    for (const option of select.children) {
      assert.ok(!scenarios.some((scenario) => option.textContent.includes(scenario.prefix)));
    }
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

const SORTED = [
  { adjustedProb: 0.75, idx: 0, prob: 0.6, word: 'hello' },
  { adjustedProb: 0.25, idx: 1, prob: 0.2, word: 'world' },
  { adjustedProb: 0, idx: 2, prob: 0.15, word: 'cut' },
  { adjustedProb: 0, idx: 3, prob: 0.05, word: 'cut2' }
];

function makeDistributionState(overrides = {}) {
  return {
    inTopP: new Set([0, 1]),
    sampleCounts: null,
    selectedTokenIndex: null,
    sorted: SORTED,
    temperature: 1,
    topP: 0.8,
    topTokens: SORTED.slice(0, 2),
    ...overrides
  };
}

function makeDistributionElements() {
  return {
    candidateList: makeElement('ul'),
    insightBox: makeElement(),
    sampleStatus: makeElement()
  };
}

test('renderDistribution renders the candidate rows, insight, and sample status', () => {
  const mocks = setupDocumentMock();
  try {
    const elements = makeDistributionElements();
    renderDistribution(
      elements,
      makeDistributionState({ selectedTokenIndex: 1, sampleCounts: new Map([[0, 70], [1, 30]]) })
    );

    const [head, ...rows] = elements.candidateList.children;
    assert.match(head.className, /tk-list-head/);
    assert.deepEqual(
      head.children.map((cell) => cell.textContent),
      ['Token', 'After temperature', 'Odds', 'Draw', 'Seen']
    );
    assert.equal(rows.length, 4);

    const [first, second, thirdCut, fourthCut] = rows.map((row) => {
      const [cutLabel, token, track, odds, draw, seen] = row.children;
      return { row, cutLabel, token, track, odds, draw, seen };
    });
    assert.equal(first.token.textContent, 'hello');
    assert.equal(first.odds.textContent, '60.0%');
    assert.equal(first.draw.textContent, '75.0%');
    assert.equal(first.seen.textContent, '70');
    assert.equal(first.track.children[0].style.width, '60%');
    assert.equal(first.track.children[1].style.width, '70%');
    assert.equal(first.row.classList.contains('is-picked'), false);
    assert.equal(second.row.classList.contains('is-picked'), true);
    assert.equal(first.cutLabel.hidden, true);

    assert.equal(thirdCut.row.classList.contains('is-cut'), true);
    assert.equal(thirdCut.draw.textContent, 'cut');
    assert.equal(thirdCut.cutLabel.hidden, false);
    assert.equal(thirdCut.cutLabel.textContent, 'top P cut');
    assert.equal(thirdCut.seen.textContent, '0');
    assert.equal(fourthCut.cutLabel.hidden, true);
    assert.equal(elements.candidateList.classList.contains('has-samples'), true);

    assert.match(elements.insightBox.textContent, /temperature/i);
    assert.match(elements.sampleStatus.textContent, /tally from 100 draws/);
  } finally {
    restoreDocument(mocks);
  }
});

test('renderDistribution reuses rows so bar widths can transition', () => {
  const mocks = setupDocumentMock();
  try {
    const elements = makeDistributionElements();
    renderDistribution(elements, makeDistributionState());
    const firstRow = elements.candidateList.children[1];
    const childrenBefore = elements.candidateList.children;

    renderDistribution(
      elements,
      makeDistributionState({
        inTopP: new Set([0, 1, 2, 3]),
        sorted: SORTED.map((token) => ({ ...token, prob: token.prob / 2 }))
      })
    );
    assert.equal(elements.candidateList.children, childrenBefore);
    assert.equal(elements.candidateList.children[1], firstRow);
    assert.equal(firstRow.children[2].children[0].style.width, '30%');
    assert.equal(firstRow.children[5].textContent, '');
    assert.equal(elements.candidateList.classList.contains('has-samples'), false);
    assert.equal(elements.candidateList.children[3].classList.contains('is-cut'), false);
    assert.match(elements.sampleStatus.textContent, /Run 100 draws/);

    // A new scenario reorders the candidates, which re-inserts the rows.
    renderDistribution(
      elements,
      makeDistributionState({ sorted: [SORTED[1], SORTED[0], SORTED[2], SORTED[3]] })
    );
    assert.notEqual(elements.candidateList.children, childrenBefore);
    assert.equal(elements.candidateList.children[1].children[1].textContent, 'world');
  } finally {
    restoreDocument(mocks);
  }
});

test('renderDistribution keeps a tiny probability visible and handles an empty tally', () => {
  const mocks = setupDocumentMock();
  try {
    const elements = makeDistributionElements();
    renderDistribution(
      elements,
      makeDistributionState({
        sampleCounts: new Map(),
        sorted: [{ adjustedProb: 1, idx: 0, prob: 0, word: 'only' }],
        inTopP: new Set([0]),
        topTokens: [{ adjustedProb: 1, idx: 0, word: 'only' }]
      })
    );
    const row = elements.candidateList.children[1];
    assert.equal(row.children[2].children[0].style.width, '0.5%');
    assert.equal(row.children[2].children[1].style.width, '0%');
    assert.equal(row.children[5].textContent, '0');
  } finally {
    restoreDocument(mocks);
  }
});

test('buildCandidateRows tags the first cut token and normalizes the tally', () => {
  const rows = buildCandidateRows(
    makeDistributionState({ sampleCounts: new Map([[0, 3], [1, 1]]) })
  );
  assert.deepEqual(rows.map((row) => row.startsCut), [false, false, true, false]);
  assert.deepEqual(rows.map((row) => row.kept), [true, true, false, false]);
  assert.deepEqual(rows.map((row) => row.seenPercent), [75, 25, 0, 0]);
  assert.equal(rows[2].drawPercent, null);
  assert.equal(rows[0].drawPercent, 75);
});

test('renderDistribution explains greedy and high-temperature extremes', () => {
  const mocks = setupDocumentMock();
  try {
    const elements = { candidateList: makeElement('ul'), insightBox: makeElement() };
    const state = makeDistributionState({
      topP: 1,
      sorted: [SORTED[0]],
      inTopP: new Set([0]),
      topTokens: [{ adjustedProb: 1, idx: 0, word: 'top' }]
    });
    renderDistribution(elements, { ...state, temperature: 0 });
    assert.match(elements.insightBox.textContent, /greedy decoding/);
    renderDistribution(elements, { ...state, temperature: 2.5 });
    assert.match(elements.insightBox.textContent, /spreads out widely/);
    renderDistribution(elements, { ...state, temperature: 0.2 });
    assert.match(elements.insightBox.textContent, /almost deterministic/);
  } finally {
    restoreDocument(mocks);
  }
});

test('renderDistribution describes each top-p regime', () => {
  const mocks = setupDocumentMock();
  try {
    const elements = { candidateList: makeElement('ul'), insightBox: makeElement() };
    const state = makeDistributionState();
    renderDistribution(elements, { ...state, topP: 0.05 });
    assert.match(elements.insightBox.textContent, /very tight/);
    renderDistribution(elements, { ...state, topP: 0.4 });
    assert.match(elements.insightBox.textContent, /small, high-confidence pool/);
    renderDistribution(elements, { ...state, topP: 1 });
    assert.match(elements.insightBox.textContent, /nearly every token/);
    renderDistribution(elements, { ...state, topP: 0.8 });
    assert.match(elements.insightBox.textContent, /keeps 2 tokens/);
    renderDistribution(elements, { ...state, topP: 0.8, topTokens: [state.topTokens[0]] });
    assert.match(elements.insightBox.textContent, /keeps 1 token whose/);
  } finally {
    restoreDocument(mocks);
  }
});
