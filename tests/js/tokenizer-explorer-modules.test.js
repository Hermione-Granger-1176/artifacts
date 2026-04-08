import assert from 'node:assert/strict';
import test from 'node:test';

import { scenarios } from '../../apps/tokenizer-explorer/js/modules/scenarios.js';

// --- scenarios.js ---

test('scenarios exports a non-empty array of valid scenario objects', () => {
  assert.ok(Array.isArray(scenarios));
  assert.ok(scenarios.length > 0);

  for (const scenario of scenarios) {
    assert.ok(typeof scenario.label === 'string' && scenario.label.length > 0);
    assert.ok(typeof scenario.type === 'string');
    assert.ok(typeof scenario.prefix === 'string');
    assert.ok(Array.isArray(scenario.tokens) && scenario.tokens.length > 0);

    for (const token of scenario.tokens) {
      assert.ok(typeof token.word === 'string' && token.word.length > 0);
      assert.ok(typeof token.baseLogit === 'number');
      assert.ok(Number.isFinite(token.baseLogit));
    }
  }
});

test('scenario tokens are ordered by descending baseLogit', () => {
  for (const scenario of scenarios) {
    for (let i = 1; i < scenario.tokens.length; i++) {
      assert.ok(
        scenario.tokens[i - 1].baseLogit >= scenario.tokens[i].baseLogit,
        `${scenario.label}: token "${scenario.tokens[i].word}" has higher logit than "${scenario.tokens[i - 1].word}"`
      );
    }
  }
});

// --- accordion.js ---

import { initAccordion } from '../../apps/tokenizer-explorer/js/modules/accordion.js';

test('initAccordion toggles card open class on trigger click', () => {
  let clickHandler;
  const container = {
    addEventListener(type, handler) {
      if (type === 'click') clickHandler = handler;
    }
  };

  initAccordion(container);
  assert.ok(typeof clickHandler === 'function');

  // Simulate click on trigger inside card
  let cardOpen = false;
  const card = {
    classList: {
      toggle(cls) {
        if (cls === 'open') {
          cardOpen = !cardOpen;
          return cardOpen;
        }
      }
    }
  };
  const trigger = {
    closest(selector) {
      if (selector === '.card') return card;
      return null;
    },
    setAttribute() {}
  };

  const ariaValues = [];
  trigger.setAttribute = (attr, value) => {
    if (attr === 'aria-expanded') ariaValues.push(value);
  };

  clickHandler({
    target: {
      closest(selector) {
        if (selector === '.card-trigger') return trigger;
        return null;
      }
    }
  });

  assert.equal(cardOpen, true);
  assert.equal(ariaValues[0], 'true');
});

test('initAccordion ignores clicks on trigger without card parent', () => {
  let clickHandler;
  const container = {
    addEventListener(type, handler) {
      if (type === 'click') clickHandler = handler;
    }
  };

  initAccordion(container);

  // Trigger exists but has no card parent
  const trigger = {
    closest(selector) {
      if (selector === '.card') return null;
      return null;
    }
  };

  clickHandler({
    target: {
      closest(selector) {
        if (selector === '.card-trigger') return trigger;
        return null;
      }
    }
  });
  // Should not throw
});

test('initAccordion ignores clicks outside trigger', () => {
  let clickHandler;
  const container = {
    addEventListener(type, handler) {
      if (type === 'click') clickHandler = handler;
    }
  };

  initAccordion(container);

  // Click on something that isn't a trigger — should not throw
  clickHandler({
    target: {
      closest() { return null; }
    }
  });
});

// --- render.js ---

// render.js uses document.documentElement and getComputedStyle at call time,
// so we mock them before import and for each test that calls exported functions.

const origDoc = globalThis.document;
const origGetCS = globalThis.getComputedStyle;
globalThis.document = {
  documentElement: {
    getAttribute() { return 'light'; }
  },
  createElement(tag) {
    const el = {
      tagName: tag,
      className: '',
      textContent: '',
      title: '',
      type: '',
      style: {},
      children: [],
      addEventListener() {},
      append(...nodes) { this.children.push(...nodes); },
      appendChild(child) { this.children.push(child); return child; }
    };
    return el;
  }
};
globalThis.getComputedStyle = () => ({
  getPropertyValue() { return 'rgb(100, 150, 200)'; }
});

const { renderTabs, renderScenario, renderDistribution } = await import(
  '../../apps/tokenizer-explorer/js/modules/render.js'
);

function setupRenderMocks() {
  globalThis.document = {
    documentElement: { getAttribute() { return 'light'; } },
    createElement(tag) {
      return {
        tagName: tag, className: '', textContent: '', title: '', type: '',
        style: {}, children: [],
        addEventListener() {},
        append(...nodes) { this.children.push(...nodes); },
        appendChild(child) { this.children.push(child); return child; }
      };
    }
  };
  globalThis.getComputedStyle = () => ({
    getPropertyValue() { return 'rgb(100, 150, 200)'; }
  });
}

function teardownRenderMocks() {
  if (origDoc) { globalThis.document = origDoc; } else { delete globalThis.document; }
  if (origGetCS) { globalThis.getComputedStyle = origGetCS; } else { delete globalThis.getComputedStyle; }
}

test('renderScenario sets type and prefix text on elements', () => {
  const elements = {
    scenarioType: { textContent: '' },
    sentencePrefix: { textContent: '' }
  };

  renderScenario(elements, { type: 'Code completion', prefix: 'function add(' });

  assert.equal(elements.scenarioType.textContent, 'Code completion');
  assert.equal(elements.sentencePrefix.textContent, 'function add(');
});

test('renderTabs creates buttons for each scenario', () => {
  setupRenderMocks();
  try {
    const container = {
      innerHTML: '',
      children: [],
      appendChild(child) { this.children.push(child); }
    };

    const mockScenarios = [
      { label: 'Tab A' },
      { label: 'Tab B' },
      { label: 'Tab C' }
    ];

    const selected = [];
    renderTabs(container, mockScenarios, 1, (index) => selected.push(index));

    assert.equal(container.children.length, 3);
    assert.equal(container.children[0].textContent, 'Tab A');
    assert.equal(container.children[1].className, 'tab active');
    assert.equal(container.children[2].className, 'tab');
  } finally {
    teardownRenderMocks();
  }
});

test('renderDistribution renders bars and pills', () => {
  setupRenderMocks();
  try {
    const bars = {
      innerHTML: '', children: [],
      appendChild(child) { this.children.push(child); }
    };
    const tokenPills = {
      innerHTML: '', children: [],
      appendChild(child) { this.children.push(child); }
    };
    const insightBox = { textContent: '' };

    const state = {
      sorted: [
        { word: 'hello', prob: 0.6, idx: 0 },
        { word: 'world', prob: 0.3, idx: 1 },
        { word: 'test', prob: 0.1, idx: 2 }
      ],
      inTopP: new Set([0, 1]),
      topTokens: [
        { word: 'hello', prob: 0.6 },
        { word: 'world', prob: 0.3 }
      ],
      topTokenProbability: 0.9,
      temperature: 1.0,
      topP: 0.9
    };

    renderDistribution({ bars, tokenPills, insightBox }, state);

    assert.equal(bars.children.length, 3);
    assert.equal(tokenPills.children.length, 2);
    assert.ok(insightBox.textContent.length > 0);
    assert.match(insightBox.textContent, /temperature/i);
  } finally {
    teardownRenderMocks();
  }
});

test('renderDistribution marks excluded tokens', () => {
  setupRenderMocks();
  try {
    const bars = {
      innerHTML: '', children: [],
      appendChild(child) { this.children.push(child); }
    };
    const tokenPills = {
      innerHTML: '', children: [],
      appendChild(child) { this.children.push(child); }
    };
    const insightBox = { textContent: '' };

    const state = {
      sorted: [
        { word: 'yes', prob: 0.9, idx: 0 },
        { word: 'no', prob: 0.1, idx: 1 }
      ],
      inTopP: new Set([0]),
      topTokens: [{ word: 'yes', prob: 0.9 }],
      topTokenProbability: 0.9,
      temperature: 0.1,
      topP: 0.05
    };

    renderDistribution({ bars, tokenPills, insightBox }, state);

    assert.match(bars.children[1].className, /excluded/);
    assert.match(insightBox.textContent, /deterministic/);
  } finally {
    teardownRenderMocks();
  }
});

test('renderDistribution high temperature insight', () => {
  setupRenderMocks();
  try {
    const bars = {
      innerHTML: '', children: [],
      appendChild(child) { this.children.push(child); }
    };
    const tokenPills = {
      innerHTML: '', children: [],
      appendChild(child) { this.children.push(child); }
    };
    const insightBox = { textContent: '' };

    const state = {
      sorted: [{ word: 'x', prob: 0.5, idx: 0 }],
      inTopP: new Set([0]),
      topTokens: [{ word: 'x', prob: 0.5 }],
      topTokenProbability: 0.5,
      temperature: 2.5,
      topP: 0.99
    };

    renderDistribution({ bars, tokenPills, insightBox }, state);

    assert.match(insightBox.textContent, /spreads out widely/);
    assert.match(insightBox.textContent, /nearly every token/);
  } finally {
    teardownRenderMocks();
  }
});

