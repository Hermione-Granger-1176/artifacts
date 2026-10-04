import assert from 'node:assert/strict';
import test from 'node:test';

import { cleanupMocks, setupFullMocks } from '../../common/app-entry-test-support.js';
import { scenarios } from '../../../../apps/tokenizer-explorer/js/modules/scenarios.js';

function makePresetButton(temperature, topP) {
  const button = globalThis.document.createElement('button');
  button.setAttribute('data-temperature', temperature);
  button.setAttribute('data-topp', topP);
  return button;
}

function promptText(elementMap) {
  return elementMap['sentence-prefix'].children.map((chip) => chip.textContent).join('');
}

function pickedRows(elementMap) {
  return elementMap['candidate-list'].children.filter((row) => row.classList.contains('is-picked'));
}

test('tokenizer explorer app.js loads and initializes without error', async () => {
  const { elementMap } = setupFullMocks();
  const presetButtons = [
    makePresetButton('0.2', '0.9'),
    makePresetButton('0.7', '0.9'),
    makePresetButton('1.2', '0.95')
  ];
  elementMap['sampling-presets'].querySelectorAll = () => presetButtons;
  const originalSetTimeout = globalThis.setTimeout;
  const originalClearTimeout = globalThis.clearTimeout;
  let timeoutCallback = null;
  let clearedTimeouts = 0;
  globalThis.setTimeout = (callback) => {
    timeoutCallback = callback;
    return 1;
  };
  globalThis.clearTimeout = () => {
    clearedTimeouts += 1;
  };
  try {
    await import(`../../../../apps/tokenizer-explorer/js/app.js?t=${Date.now()}-${Math.random()}`);

    assert.ok(
      globalThis.document.documentElement.dataset.runtimeStatus !== undefined,
      'runtime status should be set'
    );

    // First render: the scenario dropdown lists labels, the prompt is chips,
    // and the candidate list holds a head row plus one row per token.
    const select = elementMap['scenario-select'];
    assert.deepEqual(
      select.children.map((option) => option.textContent),
      scenarios.map((scenario) => scenario.label)
    );
    assert.equal(promptText(elementMap), scenarios[0].prefix);
    assert.equal(elementMap['candidate-list'].children.length, scenarios[0].tokens.length + 1);
    assert.match(elementMap['topp-note'].textContent, /^Keeps \d+ of 8 tokens, \d+% of the odds\.$/);
    assert.ok(presetButtons.every((button) => !button.classList.contains('active')));

    const tempInput = elementMap['temp-slider']._listeners.input[0];
    for (const value of ['0', '2', '15', '20']) {
      elementMap['temp-slider'].value = value;
      tempInput();
    }

    elementMap['topp-slider'].value = '50';
    elementMap['topp-slider']._listeners.input[0]();

    const presetClick = elementMap['sampling-presets']._listeners.click[0];
    presetClick({ target: { closest: () => null } });
    presetClick({
      target: {
        closest: () => ({ getAttribute: () => null })
      }
    });
    presetClick({
      target: {
        closest: () => ({
          getAttribute: (name) => name === 'data-temperature' ? '0.3' : '0.5'
        })
      }
    });
    assert.ok(presetButtons.every((button) => !button.classList.contains('active')));

    presetClick({
      target: {
        closest: () => ({
          getAttribute: (name) => name === 'data-temperature' ? '0.7' : '0.9'
        })
      }
    });
    assert.deepEqual(
      presetButtons.map((button) => button.classList.contains('active')),
      [false, true, false]
    );
    assert.deepEqual(
      presetButtons.map((button) => button.getAttribute('aria-pressed')),
      ['false', 'true', 'false']
    );

    select.value = '1';
    select._listeners.change[0]();
    assert.equal(promptText(elementMap), scenarios[1].prefix);
    assert.equal(elementMap['scenario-type'].textContent, scenarios[1].type);

    const pickToken = elementMap['pick-token']._listeners.click[0];
    pickToken();
    assert.equal(pickedRows(elementMap).length, 1);
    assert.notEqual(elementMap['sentence-completion'].textContent, '');
    pickToken();
    assert.equal(clearedTimeouts, 1);
    timeoutCallback();
    assert.equal(pickedRows(elementMap).length, 0);
    assert.equal(elementMap['sentence-completion'].textContent, '');

    pickToken();
    elementMap['sample-hundred']._listeners.click[0]();
    assert.equal(clearedTimeouts, 2);
    assert.equal(elementMap['candidate-list'].classList.contains('has-samples'), true);
    assert.match(elementMap['sample-status'].textContent, /tally from 100 draws/);
    elementMap['reset-samples']._listeners.click[0]();
    assert.equal(elementMap['candidate-list'].classList.contains('has-samples'), false);
    assert.match(elementMap['sample-status'].textContent, /Run 100 draws/);

    const whitespaceClick = elementMap['whitespace-toggle']._listeners.click[0];
    whitespaceClick();
    assert.equal(elementMap['whitespace-toggle'].textContent, 'Hide whitespace');
    assert.equal(elementMap['whitespace-toggle'].getAttribute('aria-pressed'), 'true');
    assert.ok(elementMap['sentence-prefix'].children.some((chip) => chip.textContent.startsWith('·')));
    whitespaceClick();
    assert.equal(elementMap['whitespace-toggle'].textContent, 'Show whitespace');
    assert.ok(elementMap['sentence-prefix'].children.every((chip) => !chip.textContent.startsWith('·')));

    // Moving a slider mid-pick clears the highlight and its pending timer.
    pickToken();
    assert.equal(pickedRows(elementMap).length, 1);
    tempInput();
    assert.equal(pickedRows(elementMap).length, 0);
    assert.equal(clearedTimeouts, 3);

    elementMap['theme-toggle']._listeners.click[0]();
  } finally {
    globalThis.setTimeout = originalSetTimeout;
    globalThis.clearTimeout = originalClearTimeout;
    cleanupMocks();
  }
});
