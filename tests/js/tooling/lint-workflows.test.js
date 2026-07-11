import test from 'node:test';
import assert from 'node:assert/strict';

import {
  filterActionableResults,
  listWorkflowFiles,
  runWorkflowLint
} from '../../../scripts/lint/lint-workflows.mjs';

test('filterActionableResults drops the known vars false positive', () => {
  const results = [
    { message: 'undefined variable "vars"', kind: 'expression' }
  ];
  assert.deepEqual(filterActionableResults(results), []);
});

test('filterActionableResults keeps unrelated undefined-variable diagnostics', () => {
  const results = [
    { message: 'undefined variable "matrix"', kind: 'expression' }
  ];
  assert.equal(filterActionableResults(results).length, 1);
});

test('filterActionableResults keeps a representative real error so a swallow regression is caught', () => {
  const realError = {
    message: 'property "foo" is not defined in object type',
    kind: 'expression',
    file: '.github/workflows/ci.yml',
    line: 12,
    column: 5
  };
  const results = [
    { message: 'undefined variable "vars"' },
    realError,
    { message: 'shellcheck reported issue in run' }
  ];

  const actionable = filterActionableResults(results);
  assert.equal(actionable.length, 2, 'real errors survive while the vars noise is dropped');
  assert.ok(
    actionable.some((result) => result === realError),
    'a genuine error shape must pass through the filter'
  );
});

test('filterActionableResults returns everything when there is no noise to drop', () => {
  const results = [{ message: 'a' }, { message: 'b' }];
  assert.equal(filterActionableResults(results).length, 2);
});

test('listWorkflowFiles returns only sorted yaml files relative to the repo root', async () => {
  const readdirImpl = async () => [
    { name: 'release.yml', isFile: () => true },
    { name: 'ci.yaml', isFile: () => true },
    { name: 'notes.md', isFile: () => true },
    { name: 'nested', isFile: () => false }
  ];
  const files = await listWorkflowFiles('/repo', readdirImpl);
  assert.deepEqual(files, ['.github/workflows/ci.yaml', '.github/workflows/release.yml']);
});

test('runWorkflowLint returns 0 and reports a pass when nothing is actionable', async () => {
  const out = [];
  const code = await runWorkflowLint({
    createLinterImpl: async () => () => [{ message: 'undefined variable "vars"' }],
    readFileImpl: async () => 'on: push',
    readdirImpl: async () => [{ name: 'ci.yml', isFile: () => true }],
    repoRoot: '/repo',
    stdout: { write: (chunk) => out.push(chunk) },
    stderr: { write: () => {} }
  });
  assert.equal(code, 0);
  assert.match(out.join(''), /passed for 1 file/);
});

test('runWorkflowLint returns 1 and writes actionable diagnostics to stderr', async () => {
  const err = [];
  const code = await runWorkflowLint({
    createLinterImpl: async () => () => [
      { message: 'undefined variable "vars"' },
      { file: 'w.yml', line: 3, column: 5, message: 'bad thing', kind: 'syntax' }
    ],
    readFileImpl: async () => 'x',
    readdirImpl: async () => [{ name: 'w.yml', isFile: () => true }],
    repoRoot: '/repo',
    stdout: { write: () => {} },
    stderr: { write: (chunk) => err.push(chunk) }
  });
  assert.equal(code, 1);
  assert.match(err.join(''), /w\.yml:3:5: bad thing \[syntax\]/);
  assert.doesNotMatch(err.join(''), /vars/);
});
