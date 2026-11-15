import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import { escapeHtml } from '../../../js/modules/html-escape.js';

describe('escapeHtml', () => {
  test('escapes all reserved HTML characters', () => {
    assert.equal(
      escapeHtml('<script src="x">&"\''),
      '&lt;script src=&quot;x&quot;&gt;&amp;&quot;&#039;'
    );
  });

  test('returns empty string for null and undefined', () => {
    assert.equal(escapeHtml(null), '');
    assert.equal(escapeHtml(undefined), '');
  });

  test('returns empty string for empty input', () => {
    assert.equal(escapeHtml(''), '');
  });

  test('passes through safe text unchanged', () => {
    assert.equal(escapeHtml('hello world'), 'hello world');
  });
});
