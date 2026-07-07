#!/usr/bin/env node

/**
 * Checks whether configured npm overrides are still necessary.
 *
 * The check copies package.json into a temporary directory with selected
 * overrides removed, then runs npm install and npm audit there. If everything
 * passes without an override, the override is stale and can be removed.
 *
 * Flags:
 *   --fix   Remove stale overrides from package.json and update the lockfile.
 *
 * Exit codes:
 *   0: overrides are still needed, none exist, or --fix succeeded
 *   1: overrides are stale and --fix was not requested
 */

import { execSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const fix = process.argv.includes('--fix');
const scriptDir = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(scriptDir, '..');
const pkgPath = join(rootDir, 'package.json');
const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'));
const overrides = pkg.overrides ?? {};
const names = Object.keys(overrides);

if (names.length === 0) {
  console.log('No overrides in package.json. Nothing to check.');
  process.exit(0);
}

console.log(`Found ${names.length} override(s):\n`);
for (const [name, value] of Object.entries(overrides)) {
  const display = typeof value === 'string' ? value : JSON.stringify(value);
  console.log(`  ${name}: ${display}`);
}
console.log('\nTesting whether they are still needed...\n');

const testWithout = (overridesToRemove) => {
  const tmp = mkdtempSync(join(tmpdir(), 'override-check-'));
  const cleanup = () => rmSync(tmp, { recursive: true, force: true });
  const run = (cmd) => execSync(cmd, { cwd: tmp, stdio: 'pipe', timeout: 120_000 });

  const testPkg = structuredClone(pkg);
  for (const name of overridesToRemove) {
    delete testPkg.overrides[name];
  }
  if (Object.keys(testPkg.overrides).length === 0) {
    delete testPkg.overrides;
  }
  writeFileSync(join(tmp, 'package.json'), `${JSON.stringify(testPkg, null, 2)}\n`);

  try {
    run('npm install --package-lock-only --ignore-scripts');
  } catch (err) {
    cleanup();
    return { ok: false, phase: 'install', err };
  }

  try {
    run('npm audit --audit-level=high');
  } catch (err) {
    cleanup();
    return { ok: false, phase: 'audit', err };
  }

  cleanup();
  return { ok: true };
};

const allResult = testWithout(names);

if (allResult.ok) {
  console.log('npm install succeeds without any overrides');
  console.log('npm audit passes without any overrides');
  console.log('\nAll overrides are stale and can be removed.');

  if (fix) {
    delete pkg.overrides;
    writeFileSync(pkgPath, `${JSON.stringify(pkg, null, 2)}\n`);
    console.log('\nRemoved all overrides from package.json.');
    console.log('Updating lockfile...');
    execSync('npm install --ignore-scripts', { cwd: rootDir, stdio: 'inherit' });
    console.log('Done.');
    process.exit(0);
  }

  console.log('Run with --fix to remove them automatically.');
  process.exit(1);
}

console.log('Cannot remove all overrides at once. Testing individually...\n');

const removable = [];
const needed = [];

for (const name of names) {
  const result = testWithout([name]);
  if (result.ok) {
    console.log(`  ${name}: no longer needed`);
    removable.push(name);
  } else {
    const reason = result.phase === 'install' ? 'peer dependency conflict' : 'audit failure';
    console.log(`  ${name}: still needed (${reason})`);
    needed.push(name);
  }
}

console.log('');

if (removable.length === 0) {
  console.log('All overrides are still needed.');
  process.exit(0);
}

console.log(`${removable.length} override(s) can be removed: ${removable.join(', ')}`);
console.log(`${needed.length} override(s) still needed: ${needed.join(', ')}`);

if (fix) {
  for (const name of removable) {
    delete pkg.overrides[name];
  }
  if (Object.keys(pkg.overrides).length === 0) {
    delete pkg.overrides;
  }
  writeFileSync(pkgPath, `${JSON.stringify(pkg, null, 2)}\n`);
  console.log(`\nRemoved ${removable.length} override(s) from package.json.`);
  console.log('Updating lockfile...');
    execSync('npm install --ignore-scripts', { cwd: rootDir, stdio: 'inherit' });
  console.log('Done.');
  process.exit(0);
}

console.log('\nRun with --fix to remove them automatically.');
process.exit(1);
