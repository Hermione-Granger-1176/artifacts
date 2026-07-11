import test from 'node:test';
import assert from 'node:assert/strict';

import { runOverrideCheck, makeTestWithout } from '../../../scripts/check-overrides.mjs';

const silent = { log() {}, error() {} };

/** Build the injectable dependency bag for runOverrideCheck with capture buffers. */
function harness({ pkg, argv = ['node', 'check-overrides.mjs'], testWithoutImpl }) {
  const writes = [];
  const execCalls = [];
  const deps = {
    argv,
    pkgPath: '/repo/package.json',
    rootDir: '/repo',
    readFileSyncImpl: () => JSON.stringify(pkg),
    writeFileSyncImpl: (filePath, data) => writes.push({ filePath, data }),
    execSyncImpl: (cmd) => execCalls.push(cmd),
    consoleObj: silent,
    testWithoutImpl
  };
  return { deps, writes, execCalls };
}

test('runOverrideCheck returns 0 when there are no overrides', () => {
  const { deps } = harness({ pkg: { name: 'x' } });
  assert.equal(runOverrideCheck(deps), 0);
});

test('runOverrideCheck returns 1 when all overrides are stale without --fix', () => {
  const { deps, writes, execCalls } = harness({
    pkg: { overrides: { foo: '1.0.0' } },
    testWithoutImpl: () => ({ ok: true })
  });
  assert.equal(runOverrideCheck(deps), 1);
  assert.equal(writes.length, 0, 'must not write package.json without --fix');
  assert.equal(execCalls.length, 0, 'must not touch the lockfile without --fix');
});

test('runOverrideCheck removes all stale overrides and updates the lockfile with --fix', () => {
  const { deps, writes, execCalls } = harness({
    pkg: { name: 'x', overrides: { foo: '1.0.0', bar: '2.0.0' } },
    argv: ['node', 'check-overrides.mjs', '--fix'],
    testWithoutImpl: () => ({ ok: true })
  });
  assert.equal(runOverrideCheck(deps), 0);
  assert.equal(writes.length, 1);
  const written = JSON.parse(writes[0].data);
  assert.equal(written.overrides, undefined, 'all overrides removed');
  assert.equal(execCalls.length, 1, 'lockfile refreshed once');
  assert.match(execCalls[0], /npm install/);
});

test('runOverrideCheck keeps needed overrides and reports removable ones without --fix', () => {
  const { deps, writes } = harness({
    pkg: { overrides: { keep: '1', drop: '2' } },
    testWithoutImpl: (names) => {
      if (names.length > 1) {
        return { ok: false, phase: 'install' };
      }
      return names[0] === 'drop' ? { ok: true } : { ok: false, phase: 'audit' };
    }
  });
  assert.equal(runOverrideCheck(deps), 1);
  assert.equal(writes.length, 0);
});

test('runOverrideCheck returns 0 when every override is individually still needed', () => {
  const { deps } = harness({
    pkg: { overrides: { keep: '1', also: '2' } },
    testWithoutImpl: () => ({ ok: false, phase: 'install' })
  });
  assert.equal(runOverrideCheck(deps), 0);
});

test('runOverrideCheck removes only the individually removable overrides with --fix', () => {
  const { deps, writes, execCalls } = harness({
    pkg: { overrides: { keep: '1', drop: '2' } },
    argv: ['node', 'check-overrides.mjs', '--fix'],
    testWithoutImpl: (names) => {
      if (names.length > 1) {
        return { ok: false, phase: 'audit' };
      }
      return names[0] === 'drop' ? { ok: true } : { ok: false, phase: 'install' };
    }
  });
  assert.equal(runOverrideCheck(deps), 0);
  const written = JSON.parse(writes[0].data);
  assert.deepEqual(written.overrides, { keep: '1' }, 'only the stale override is removed');
  assert.equal(execCalls.length, 1);
});

test('makeTestWithout reports ok when install and audit both succeed', () => {
  const commands = [];
  const tester = makeTestWithout({
    pkg: { overrides: { foo: '1' } },
    execSyncImpl: (cmd) => commands.push(cmd),
    writeFileSyncImpl: () => {}
  });
  assert.deepEqual(tester(['foo']), { ok: true });
  assert.equal(commands.length, 2, 'runs install then audit');
});

test('makeTestWithout reports an install-phase failure', () => {
  const tester = makeTestWithout({
    pkg: { overrides: { foo: '1' } },
    execSyncImpl: (cmd) => {
      if (cmd.includes('install')) {
        throw new Error('peer conflict');
      }
    },
    writeFileSyncImpl: () => {}
  });
  const result = tester(['foo']);
  assert.equal(result.ok, false);
  assert.equal(result.phase, 'install');
});

test('makeTestWithout reports an audit-phase failure', () => {
  const tester = makeTestWithout({
    pkg: { overrides: { foo: '1' } },
    execSyncImpl: (cmd) => {
      if (cmd.includes('audit')) {
        throw new Error('vuln');
      }
    },
    writeFileSyncImpl: () => {}
  });
  const result = tester(['foo']);
  assert.equal(result.ok, false);
  assert.equal(result.phase, 'audit');
});
