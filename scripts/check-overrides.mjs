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

import { execSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const DEFAULT_ROOT_DIR = resolve(scriptDir, "..");
const DEFAULT_PKG_PATH = join(DEFAULT_ROOT_DIR, "package.json");

/**
 * Build the default npm-probing tester that installs and audits a package.json
 * with selected overrides removed. Kept separate so the decision logic can be
 * unit tested with the npm calls stubbed.
 * @param {{
 *   pkg: object,
 *   execSyncImpl: typeof execSync,
 *   writeFileSyncImpl: typeof writeFileSync
 * }} deps - Base package and injectable exec/write helpers.
 * @returns {(overridesToRemove: string[]) => { ok: boolean, phase?: string, err?: unknown }}
 *   Tester that reports whether the install and audit pass without the overrides.
 */
export function makeTestWithout({ pkg, execSyncImpl, writeFileSyncImpl }) {
  return (overridesToRemove) => {
    const tmp = mkdtempSync(join(tmpdir(), "override-check-"));
    const cleanup = () => rmSync(tmp, { recursive: true, force: true });
    const run = (cmd) => execSyncImpl(cmd, { cwd: tmp, stdio: "pipe", timeout: 120_000 });

    const testPkg = structuredClone(pkg);
    for (const name of overridesToRemove) {
      delete testPkg.overrides[name];
    }
    if (Object.keys(testPkg.overrides).length === 0) {
      delete testPkg.overrides;
    }
    writeFileSyncImpl(join(tmp, "package.json"), `${JSON.stringify(testPkg, null, 2)}\n`);

    try {
      run("npm install --package-lock-only --ignore-scripts");
    } catch (err) {
      cleanup();
      return { ok: false, phase: "install", err };
    }

    try {
      run("npm audit --audit-level=high");
    } catch (err) {
      cleanup();
      return { ok: false, phase: "audit", err };
    }

    cleanup();
    return { ok: true };
  };
}

/**
 * Run the override staleness check and return a process exit code.
 * The npm probing is delegated to `testWithoutImpl` so the decision and
 * reporting logic can be exercised without touching the network or disk.
 * @param {{
 *   argv?: string[],
 *   pkgPath?: string,
 *   rootDir?: string,
 *   readFileSyncImpl?: typeof readFileSync,
 *   writeFileSyncImpl?: typeof writeFileSync,
 *   execSyncImpl?: typeof execSync,
 *   consoleObj?: Console,
 *   testWithoutImpl?: (overridesToRemove: string[]) => { ok: boolean, phase?: string }
 * }} [deps={}] - Injectable argv, fs, exec, console, and npm-probe overrides.
 * @returns {number} Process exit code (0 success, 1 stale without --fix).
 */
export function runOverrideCheck({
  argv = process.argv,
  pkgPath = DEFAULT_PKG_PATH,
  rootDir = DEFAULT_ROOT_DIR,
  readFileSyncImpl = readFileSync,
  writeFileSyncImpl = writeFileSync,
  execSyncImpl = execSync,
  consoleObj = console,
  testWithoutImpl,
} = {}) {
  const fix = argv.includes("--fix");
  const pkg = JSON.parse(readFileSyncImpl(pkgPath, "utf-8"));
  const overrides = pkg.overrides ?? {};
  const names = Object.keys(overrides);

  if (names.length === 0) {
    consoleObj.log("No overrides in package.json. Nothing to check.");
    return 0;
  }

  const testWithout = testWithoutImpl ?? makeTestWithout({ pkg, execSyncImpl, writeFileSyncImpl });

  consoleObj.log(`Found ${names.length} override(s):\n`);
  for (const [name, value] of Object.entries(overrides)) {
    const display = typeof value === "string" ? value : JSON.stringify(value);
    consoleObj.log(`  ${name}: ${display}`);
  }
  consoleObj.log("\nTesting whether they are still needed...\n");

  const writeLockfile = () => {
    consoleObj.log("Updating lockfile...");
    execSyncImpl("npm install --package-lock-only --ignore-scripts", {
      cwd: rootDir,
      stdio: "inherit",
    });
    consoleObj.log("Done.");
  };

  const allResult = testWithout(names);

  if (allResult.ok) {
    consoleObj.log("npm install succeeds without any overrides");
    consoleObj.log("npm audit passes without any overrides");
    consoleObj.log("\nAll overrides are stale and can be removed.");

    if (fix) {
      delete pkg.overrides;
      writeFileSyncImpl(pkgPath, `${JSON.stringify(pkg, null, 2)}\n`);
      consoleObj.log("\nRemoved all overrides from package.json.");
      writeLockfile();
      return 0;
    }

    consoleObj.log("Run with --fix to remove them automatically.");
    return 1;
  }

  consoleObj.log("Cannot remove all overrides at once. Testing individually...\n");

  const removable = [];
  const needed = [];

  for (const name of names) {
    const result = testWithout([name]);
    if (result.ok) {
      consoleObj.log(`  ${name}: no longer needed`);
      removable.push(name);
    } else {
      const reason = result.phase === "install" ? "peer dependency conflict" : "audit failure";
      consoleObj.log(`  ${name}: still needed (${reason})`);
      needed.push(name);
    }
  }

  consoleObj.log("");

  if (removable.length === 0) {
    consoleObj.log("All overrides are still needed.");
    return 0;
  }

  consoleObj.log(`${removable.length} override(s) can be removed: ${removable.join(", ")}`);
  consoleObj.log(`${needed.length} override(s) still needed: ${needed.join(", ")}`);

  if (fix) {
    for (const name of removable) {
      delete pkg.overrides[name];
    }
    if (Object.keys(pkg.overrides).length === 0) {
      delete pkg.overrides;
    }
    writeFileSyncImpl(pkgPath, `${JSON.stringify(pkg, null, 2)}\n`);
    consoleObj.log(`\nRemoved ${removable.length} override(s) from package.json.`);
    writeLockfile();
    return 0;
  }

  consoleObj.log("\nRun with --fix to remove them automatically.");
  return 1;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exit(runOverrideCheck());
}
