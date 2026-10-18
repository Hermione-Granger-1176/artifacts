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

const INSTALL_COMMAND = "npm install --package-lock-only --ignore-scripts";

/** Probe phases in run order, each with the npm command that exercises it. */
const PROBE_PHASES = [
  ["install", INSTALL_COMMAND],
  ["audit", "npm audit --audit-level=high"],
];

/**
 * Delete the named overrides from a package object in place, dropping the
 * `overrides` key itself once none remain.
 * @param {{ overrides: Record<string, unknown> }} pkg - Package object to mutate.
 * @param {string[]} names - Override names to delete.
 */
function removeOverrides(pkg, names) {
  for (const name of names) {
    delete pkg.overrides[name];
  }
  if (Object.keys(pkg.overrides).length === 0) {
    delete pkg.overrides;
  }
}

/**
 * Serialize a package object the way package.json is written on disk.
 * @param {object} pkg - Package object.
 * @returns {string} Two-space JSON with a trailing newline.
 */
function serializePackage(pkg) {
  return `${JSON.stringify(pkg, null, 2)}\n`;
}

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
    const run = (cmd) => execSyncImpl(cmd, { cwd: tmp, stdio: "pipe", timeout: 120_000 });

    try {
      const testPkg = structuredClone(pkg);
      removeOverrides(testPkg, overridesToRemove);
      writeFileSyncImpl(join(tmp, "package.json"), serializePackage(testPkg));

      for (const [phase, command] of PROBE_PHASES) {
        try {
          run(command);
        } catch (err) {
          return { ok: false, phase, err };
        }
      }

      return { ok: true };
    } finally {
      rmSync(tmp, { recursive: true, force: true });
    }
  };
}

/**
 * Test each override on its own and sort the names by whether the install and
 * audit still pass without that override. Logs one line per override.
 * @param {string[]} names - Override names to probe.
 * @param {(overridesToRemove: string[]) => { ok: boolean, phase?: string }} testWithout - Probe.
 * @param {Console} consoleObj - Logger.
 * @returns {{ removable: string[], needed: string[] }} Names that can go and names that must stay.
 */
function classifyOverrides(names, testWithout, consoleObj) {
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

  return { removable, needed };
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

  const applyFix = (namesToRemove, summary) => {
    removeOverrides(pkg, namesToRemove);
    writeFileSyncImpl(pkgPath, serializePackage(pkg));
    consoleObj.log(`\n${summary}`);
    consoleObj.log("Updating lockfile...");
    execSyncImpl(INSTALL_COMMAND, { cwd: rootDir, stdio: "inherit" });
    consoleObj.log("Done.");
    return 0;
  };

  const allResult = testWithout(names);

  if (allResult.ok) {
    consoleObj.log("npm install succeeds without any overrides");
    consoleObj.log("npm audit passes without any overrides");
    consoleObj.log("\nAll overrides are stale and can be removed.");

    if (fix) {
      return applyFix(names, "Removed all overrides from package.json.");
    }

    consoleObj.log("Run with --fix to remove them automatically.");
    return 1;
  }

  consoleObj.log("Cannot remove all overrides at once. Testing individually...\n");

  const { removable, needed } = classifyOverrides(names, testWithout, consoleObj);

  consoleObj.log("");

  if (removable.length === 0) {
    consoleObj.log("All overrides are still needed.");
    return 0;
  }

  consoleObj.log(`${removable.length} override(s) can be removed: ${removable.join(", ")}`);
  consoleObj.log(`${needed.length} override(s) still needed: ${needed.join(", ")}`);

  if (fix) {
    return applyFix(removable, `Removed ${removable.length} override(s) from package.json.`);
  }

  consoleObj.log("\nRun with --fix to remove them automatically.");
  return 1;
}

if (
  typeof process.argv[1] === "string" &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  process.exit(runOverrideCheck());
}
