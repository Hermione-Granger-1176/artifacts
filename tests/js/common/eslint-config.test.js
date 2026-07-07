import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Linter } from 'eslint';

import config from '../../../config/eslint.config.js';

const jsConfig = config.find((entry) => entry.files?.includes('js/**/*.js'));

assert.ok(jsConfig, 'expected a config entry covering js/**/*.js');

function lintSource(source) {
  const linter = new Linter();
  return linter.verify(source, jsConfig, { filename: 'js/example.js' });
}

test('ESLint blocks template literal assignments to computed innerHTML and outerHTML', () => {
  const messages = lintSource(`
    const el = {};
    const name = 'Ada';
    el['innerHTML'] = \`<p>\${name}</p>\`;
    el["outerHTML"] = \`<section>\${name}</section>\`;
  `);

  assert.equal(messages.length, 2);
  assert.ok(messages.every((message) => message.ruleId === 'no-restricted-syntax'));
});
