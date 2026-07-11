import test from 'node:test';
import assert from 'node:assert/strict';
import { sep } from 'node:path';

import {
  parseLcov,
  normalizePath,
  isExcludedPath,
  evaluateCoverageFloors,
  formatReport,
  runCoverageFloors,
  LINE_FLOOR,
  BRANCH_FLOOR,
  DEFAULT_LCOV_PATH
} from '../../../scripts/lint/check-js-coverage-floors.mjs';

const FIXTURE = [
  'TN:',
  'SF:/repo/js/app-theme.js',
  'LF:10',
  'LH:9',
  'BRF:4',
  'BRH:3',
  'end_of_record',
  'SF:/repo/js/weak.js',
  'LF:10',
  'LH:5',
  'BRF:0',
  'BRH:0',
  'end_of_record',
  'SF:/repo/tests/js/foo.test.js',
  'LF:10',
  'LH:1',
  'BRF:2',
  'BRH:0',
  'end_of_record',
  'SF:/repo/js/data.js',
  'LF:100',
  'LH:1',
  'BRF:0',
  'BRH:0',
  'end_of_record',
  'SF:/repo/vendor/lib.js',
  'LF:10',
  'LH:1',
  'BRF:0',
  'BRH:0',
  'end_of_record',
  ''
].join('\n');

test('parseLcov extracts one record per SF block with line and branch counters', () => {
  const records = parseLcov(FIXTURE);
  assert.equal(records.length, 5);
  const appTheme = records.find((record) => record.file.endsWith('app-theme.js'));
  assert.deepEqual(appTheme, {
    file: '/repo/js/app-theme.js',
    linesFound: 10,
    linesHit: 9,
    branchesFound: 4,
    branchesHit: 3
  });
});

test('parseLcov returns nothing for empty input', () => {
  assert.deepEqual(parseLcov(''), []);
});

test('parseLcov merges duplicate SF blocks by unioning line and branch hits', () => {
  const duplicated = [
    'SF:js/app.js',
    'DA:1,1',
    'DA:2,0',
    'DA:3,0',
    'BRDA:1,0,0,1',
    'BRDA:1,0,1,-',
    'end_of_record',
    'SF:js/app.js',
    'DA:1,0',
    'DA:2,5',
    'DA:3,0',
    'BRDA:1,0,0,-',
    'BRDA:1,0,1,2',
    'end_of_record',
    ''
  ].join('\n');

  const records = parseLcov(duplicated);
  assert.equal(records.length, 1, 'duplicate blocks collapse to one file record');
  const record = records[0];
  // Line 1 is hit only in block A, line 2 only in block B, line 3 never: union is 2 of 3.
  assert.equal(record.linesFound, 3);
  assert.equal(record.linesHit, 2);
  // Branch (1,0,0) is taken only in block A, branch (1,0,1) only in block B: union covers both.
  assert.equal(record.branchesFound, 2);
  assert.equal(record.branchesHit, 2);
});

test('parseLcov keys branch arms by line position, not process-local block ids', () => {
  // The same source branch shows up with block id 2 in one process and 6 in
  // another (V8 block ids are process-local). It must merge as one arm.
  const misaligned = [
    'SF:js/app.js',
    'DA:31,1',
    'BRDA:31,2,0,1',
    'end_of_record',
    'SF:js/app.js',
    'DA:31,1',
    'BRDA:31,6,0,1',
    'end_of_record',
    ''
  ].join('\n');

  const record = parseLcov(misaligned)[0];
  assert.equal(record.branchesFound, 1, 'the arm is not double counted across block ids');
  assert.equal(record.branchesHit, 1);
});

test('parseLcov credits a branch that another block covered without reporting it', () => {
  // V8 emits a BRDA row only when an arm count differs from its enclosing
  // function, so a block that fully took the branch reports plain DA hits and
  // no BRDA rows for that line. The unhit row from the other block must not
  // mask that coverage.
  const complementary = [
    'SF:js/app.js',
    'DA:24,1',
    'BRDA:24,3,0,0',
    'end_of_record',
    'SF:js/app.js',
    'DA:24,1',
    'end_of_record',
    ''
  ].join('\n');

  const record = parseLcov(complementary)[0];
  assert.equal(record.branchesFound, 1);
  assert.equal(record.branchesHit, 1, 'coverage from the row-free block wins');
});

test('parseLcov does not credit an unhit branch from a block that never ran the line', () => {
  const untouched = [
    'SF:js/app.js',
    'DA:24,1',
    'BRDA:24,3,0,0',
    'end_of_record',
    'SF:js/app.js',
    'DA:24,0',
    'end_of_record',
    ''
  ].join('\n');

  const record = parseLcov(untouched)[0];
  assert.equal(record.branchesFound, 1);
  assert.equal(record.branchesHit, 0, 'a block that never executed the line proves nothing');
});

test('normalizePath strips the repo root and normalizes separators', () => {
  assert.equal(normalizePath('/repo/js/app.js', '/repo'), 'js/app.js');
  assert.equal(normalizePath('js\\app.js'), 'js/app.js');
  assert.equal(normalizePath('./js/app.js'), 'js/app.js');
});

test('isExcludedPath excludes tests, deps, vendor, and generated gallery data', () => {
  assert.equal(isExcludedPath('tests/js/foo.test.js'), true);
  assert.equal(isExcludedPath('node_modules/pkg/index.js'), true);
  assert.equal(isExcludedPath('vendor/lib.js'), true);
  assert.equal(isExcludedPath('apps/x/vendor/lib.js'), true);
  assert.equal(isExcludedPath('js/data.js'), true);
  assert.equal(isExcludedPath('js/gallery-config.js'), true);
  assert.equal(isExcludedPath('js/app-theme.js'), false);
});

test('evaluateCoverageFloors flags below-floor files and skips excluded ones', () => {
  const outcome = evaluateCoverageFloors(parseLcov(FIXTURE), {
    lineFloor: 80,
    branchFloor: 70,
    rootDir: '/repo'
  });
  assert.equal(outcome.checked, 2, 'only js/app-theme.js and js/weak.js are enforced');
  assert.equal(outcome.failures.length, 1);
  assert.equal(outcome.failures[0].file, 'js/weak.js');
  assert.equal(outcome.failures[0].linePct, 50);
});

test('evaluateCoverageFloors treats zero-branch files as fully branch-covered', () => {
  const records = [
    { file: 'js/pure.js', linesFound: 10, linesHit: 10, branchesFound: 0, branchesHit: 0 }
  ];
  const outcome = evaluateCoverageFloors(records, { lineFloor: 80, branchFloor: 70 });
  assert.equal(outcome.checked, 1);
  assert.equal(outcome.failures.length, 0);
});

test('evaluateCoverageFloors flags a file that fails only on branches', () => {
  const records = [
    { file: 'js/branchy.js', linesFound: 10, linesHit: 10, branchesFound: 10, branchesHit: 5 }
  ];
  const outcome = evaluateCoverageFloors(records, { lineFloor: 80, branchFloor: 70 });
  assert.equal(outcome.failures.length, 1);
  assert.equal(outcome.failures[0].branchPct, 50);
});

test('formatReport summarizes both the passing and failing cases', () => {
  const pass = formatReport({ checked: 3, failures: [] }, { lineFloor: 80, branchFloor: 70 });
  assert.match(pass, /floors met for 3 file/);

  const fail = formatReport(
    { checked: 3, failures: [{ file: 'js/weak.js', linePct: 50, branchPct: 100 }] },
    { lineFloor: 80, branchFloor: 70 }
  );
  assert.match(fail, /not met/);
  assert.match(fail, /js\/weak\.js: lines 50\.0%/);
});

test('exported floors are the documented defaults', () => {
  assert.equal(LINE_FLOOR, 80);
  assert.equal(BRANCH_FLOOR, 70);
});

test('the shared lcov path matches what make coverage-js emits', () => {
  assert.equal(DEFAULT_LCOV_PATH, '.artifacts/js-coverage.lcov');
});

test('runCoverageFloors returns 0 when every file meets the floors', () => {
  const passing = [
    'SF:/repo/js/good.js',
    'LF:10',
    'LH:10',
    'BRF:2',
    'BRH:2',
    'end_of_record',
    ''
  ].join('\n');

  let removed = null;
  const code = runCoverageFloors({
    execFileSyncImpl: () => '',
    existsSyncImpl: () => false,
    readFileSyncImpl: () => passing,
    rmSyncImpl: (dest) => {
      removed = dest;
    },
    consoleObj: silentLogger(),
    rootDir: '/repo'
  });
  assert.equal(code, 0);
  assert.ok(removed, 'the temporary lcov file is cleaned up');
});

test('runCoverageFloors consumes an existing coverage-js lcov without rerunning the suite', () => {
  const passing = ['SF:/repo/js/good.js', 'LF:10', 'LH:10', 'BRF:2', 'BRH:2', 'end_of_record', ''].join(
    '\n'
  );

  let readPath = null;
  let removed = false;
  const code = runCoverageFloors({
    execFileSyncImpl: () => {
      throw new Error('the suite must not rerun when the shared report exists');
    },
    existsSyncImpl: (path) => path.endsWith(DEFAULT_LCOV_PATH.replace(/\//g, sep)),
    readFileSyncImpl: (path) => {
      readPath = path;
      return passing;
    },
    rmSyncImpl: () => {
      removed = true;
    },
    consoleObj: silentLogger(),
    rootDir: '/repo'
  });
  assert.equal(code, 0);
  assert.ok(
    String(readPath).endsWith(DEFAULT_LCOV_PATH.replace(/\//g, sep)),
    'the shared report under the repo root is what gets read'
  );
  assert.equal(removed, false, 'the shared report is left in place for other consumers');
});

test('runCoverageFloors falls back to a suite run with the aggregate coverage excludes', () => {
  const passing = ['SF:/repo/js/good.js', 'LF:10', 'LH:10', 'end_of_record', ''].join('\n');

  let args = null;
  const code = runCoverageFloors({
    execFileSyncImpl: (_command, commandArgs) => {
      args = commandArgs;
      return '';
    },
    existsSyncImpl: () => false,
    readFileSyncImpl: () => passing,
    rmSyncImpl: () => {},
    consoleObj: silentLogger(),
    rootDir: '/repo'
  });
  assert.equal(code, 0);
  assert.ok(
    args.includes('--test-coverage-exclude=node_modules/**'),
    'dependencies stay outside the instrumented set'
  );
  assert.ok(args.includes('--test-coverage-exclude=tests/**'), 'tests stay outside the instrumented set');
});

test('runCoverageFloors returns 1 when a file is below a floor', () => {
  const failing = [
    'SF:/repo/js/bad.js',
    'LF:10',
    'LH:1',
    'BRF:0',
    'BRH:0',
    'end_of_record',
    ''
  ].join('\n');

  const code = runCoverageFloors({
    execFileSyncImpl: () => '',
    existsSyncImpl: () => false,
    readFileSyncImpl: () => failing,
    rmSyncImpl: () => {},
    consoleObj: silentLogger(),
    rootDir: '/repo'
  });
  assert.equal(code, 1);
});

test('runCoverageFloors returns 1 and cleans up when the test run fails', () => {
  let removed = false;
  const code = runCoverageFloors({
    execFileSyncImpl: () => {
      throw new Error('tests failed');
    },
    existsSyncImpl: () => false,
    readFileSyncImpl: () => {
      throw new Error('should not read after a failed run');
    },
    rmSyncImpl: () => {
      removed = true;
    },
    consoleObj: silentLogger(),
    rootDir: '/repo'
  });
  assert.equal(code, 1);
  assert.equal(removed, true);
});

test('runCoverageFloors cleans up the temp report when the fallback read throws', () => {
  let removed = false;
  assert.throws(
    () =>
      runCoverageFloors({
        execFileSyncImpl: () => '',
        existsSyncImpl: () => false,
        readFileSyncImpl: () => {
          throw new Error('read failed');
        },
        rmSyncImpl: () => {
          removed = true;
        },
        consoleObj: silentLogger(),
        rootDir: '/repo'
      }),
    /read failed/
  );
  assert.equal(removed, true, 'the temp lcov file is removed even when the read throws');
});

/** Minimal console stub that ignores log and error output. */
function silentLogger() {
  return { log() {}, error() {} };
}
