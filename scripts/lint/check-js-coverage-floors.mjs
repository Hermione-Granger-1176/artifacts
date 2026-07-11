#!/usr/bin/env node

/**
 * Enforces per-file JS coverage floors.
 *
 * The aggregate coverage gate (test:coverage) lets a weakly tested module hide
 * behind well-tested neighbors. This consumes the lcov report that
 * `make coverage-js` already emits (so the suite runs with coverage only once
 * in the CI gate), then fails if any non-excluded source file drops below the
 * per-file line or branch floor. When the report is absent (standalone runs),
 * it falls back to running the suite itself with the same coverage excludes
 * the aggregate gate uses. The file set is auto-discovered from the lcov
 * report, so newly added modules are covered without editing a list here.
 *
 * Exit codes:
 *   0: every checked file meets the floors
 *   1: at least one file is below a floor, or the test run failed
 */

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = resolve(scriptDir, "..", "..");

export const LINE_FLOOR = 80;
export const BRANCH_FLOOR = 70;

// Repo-relative location where the aggregate coverage run (npm run
// test:coverage via make coverage-js) writes its lcov report.
export const DEFAULT_LCOV_PATH = ".artifacts/js-coverage.lcov";

// Keep the fallback run's instrumentation scope identical to package.json's
// test:coverage, so the floors never see files the aggregate gate excludes.
const COVERAGE_EXCLUDES = ["node_modules/**", "tests/**"];

/**
 * Split raw lcov text into per-record blocks (one per `SF:`/`end_of_record`
 * pair). Branch rows are grouped per line and kept in report order because
 * V8 block ids are process-local and cannot be compared across blocks.
 * @param {string} text - Raw lcov report.
 * @returns {{
 *   file: string,
 *   lines: Map<string, number>,
 *   branchRows: Map<string, number[]>,
 *   summary: { lf: number, lh: number, brf: number, brh: number }
 * }[]} One entry per SF block, in report order.
 */
function splitLcovBlocks(text) {
  const blocks = [];
  let current = null;

  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();

    if (line.startsWith("SF:")) {
      current = {
        file: line.slice(3),
        lines: new Map(),
        branchRows: new Map(),
        summary: { lf: 0, lh: 0, brf: 0, brh: 0 },
      };
      blocks.push(current);
      continue;
    }
    if (!current) {
      continue;
    }

    if (line.startsWith("DA:")) {
      const [lineNo, hits] = line.slice(3).split(",");
      const prev = current.lines.get(lineNo) ?? 0;
      current.lines.set(lineNo, Math.max(prev, Number(hits) || 0));
    } else if (line.startsWith("BRDA:")) {
      const [lineNo, , , taken] = line.slice(5).split(",");
      const value = taken === "-" ? 0 : Number(taken) || 0;
      const rows = current.branchRows.get(lineNo) ?? [];
      rows.push(value);
      current.branchRows.set(lineNo, rows);
    } else if (line.startsWith("LF:")) {
      current.summary.lf = Number(line.slice(3)) || 0;
    } else if (line.startsWith("LH:")) {
      current.summary.lh = Number(line.slice(3)) || 0;
    } else if (line.startsWith("BRF:")) {
      current.summary.brf = Number(line.slice(4)) || 0;
    } else if (line.startsWith("BRH:")) {
      current.summary.brh = Number(line.slice(4)) || 0;
    } else if (line === "end_of_record") {
      current = null;
    }
  }

  return blocks;
}

/**
 * Merge one file's SF blocks into a single coverage record.
 *
 * Lines are keyed by line number (stable across processes), so `DA` records
 * union cleanly with max hits. Branches need care: V8 emits a `BRDA` row only
 * for a branch arm whose execution count differs from its enclosing function,
 * and its block ids are process-local. So arms are keyed by (line, position
 * within that line), and an arm also counts as covered when any block executed
 * the line (`DA` > 0) without reporting branch rows for it, which is how V8
 * reports a fully taken branch.
 * @param {ReturnType<typeof splitLcovBlocks>} blocks - All SF blocks for one file.
 * @returns {{ file: string, linesFound: number, linesHit: number, branchesFound: number, branchesHit: number }}
 *   Merged coverage record.
 */
function mergeFileBlocks(blocks) {
  const { file } = blocks[0];
  const detailBlocks = blocks.filter((block) => block.lines.size > 0 || block.branchRows.size > 0);

  if (detailBlocks.length === 0) {
    // Summary-only reports: take the best block per counter pair, independently
    // for lines and branches, so one block's weak branch numbers cannot ride in
    // on its strong line numbers.
    const bestLines = blocks.reduce((left, right) =>
      right.summary.lh > left.summary.lh ? right : left,
    );
    const bestBranches = blocks.reduce((left, right) =>
      right.summary.brh > left.summary.brh ? right : left,
    );
    return {
      file,
      linesFound: bestLines.summary.lf,
      linesHit: bestLines.summary.lh,
      branchesFound: bestBranches.summary.brf,
      branchesHit: bestBranches.summary.brh,
    };
  }

  const mergedLines = new Map();
  const mergedBranches = new Map();
  const fullyCoveredLines = new Set();

  for (const block of detailBlocks) {
    for (const [lineNo, hits] of block.lines) {
      mergedLines.set(lineNo, Math.max(mergedLines.get(lineNo) ?? 0, hits));
    }
    for (const [lineNo, rows] of block.branchRows) {
      rows.forEach((taken, position) => {
        const key = `${lineNo}:${position}`;
        mergedBranches.set(key, Math.max(mergedBranches.get(key) ?? 0, taken));
      });
    }
  }

  for (const key of mergedBranches.keys()) {
    const lineNo = key.slice(0, key.indexOf(":"));
    const covered = detailBlocks.some(
      (block) => (block.lines.get(lineNo) ?? 0) > 0 && !block.branchRows.has(lineNo),
    );
    if (covered) {
      fullyCoveredLines.add(lineNo);
    }
  }

  let branchesHit = 0;
  for (const [key, taken] of mergedBranches) {
    const lineNo = key.slice(0, key.indexOf(":"));
    if (taken > 0 || fullyCoveredLines.has(lineNo)) {
      branchesHit += 1;
    }
  }

  return {
    file,
    linesFound: mergedLines.size,
    linesHit: [...mergedLines.values()].filter((hits) => hits > 0).length,
    branchesFound: mergedBranches.size,
    branchesHit,
  };
}

/**
 * Parse lcov text into merged per-file coverage records.
 *
 * The Node test runner isolates each test file in its own process, so a source
 * module loaded by several test files appears as several `SF` blocks in one
 * report. Those blocks are merged per file (see mergeFileBlocks for the exact
 * line and branch semantics). Reports that only carry summary counters
 * (`LF`/`LH`/`BRF`/`BRH`) without line detail fall back to those summary numbers.
 * @param {string} text - Raw lcov report.
 * @returns {{ file: string, linesFound: number, linesHit: number, branchesFound: number, branchesHit: number }[]}
 *   One merged record per source file.
 */
export function parseLcov(text) {
  const byFile = new Map();
  for (const block of splitLcovBlocks(text)) {
    const blocks = byFile.get(block.file) ?? [];
    blocks.push(block);
    byFile.set(block.file, blocks);
  }
  return [...byFile.values()].map(mergeFileBlocks);
}

/**
 * Normalize an lcov `SF` path to a repo-relative posix path.
 * @param {string} sourceFile - Raw `SF` value (may be absolute).
 * @param {string} [rootDir=''] - Repo root to strip from absolute paths.
 * @returns {string} Repo-relative posix path.
 */
export function normalizePath(sourceFile, rootDir = "") {
  let value = sourceFile;
  if (rootDir && value.startsWith(rootDir)) {
    value = value.slice(rootDir.length);
  }
  return value.replace(/\\/g, "/").replace(/^\.\//, "").replace(/^\/+/, "");
}

/**
 * Decide whether a repo-relative path is exempt from per-file floors.
 * Tests, dependencies, vendored code, and generated gallery data never carry
 * their own unit coverage, so they are skipped.
 * @param {string} relPath - Repo-relative posix path.
 * @returns {boolean} Whether the path should be excluded from enforcement.
 */
export function isExcludedPath(relPath) {
  if (relPath.startsWith("tests/") || relPath.includes("/tests/")) {
    return true;
  }
  if (relPath.includes("node_modules/")) {
    return true;
  }
  if (relPath.startsWith("vendor/") || relPath.includes("/vendor/")) {
    return true;
  }
  return relPath === "js/data.js" || relPath === "js/gallery-config.js";
}

/**
 * Evaluate parsed lcov records against per-file coverage floors.
 * Files with zero measurable lines or branches count as fully covered for
 * that dimension (there is nothing to miss).
 * @param {ReturnType<typeof parseLcov>} records - Parsed lcov records.
 * @param {{
 *   lineFloor: number,
 *   branchFloor: number,
 *   rootDir?: string,
 *   isExcluded?: (relPath: string) => boolean
 * }} options - Floors, repo root, and exclusion predicate.
 * @returns {{
 *   checked: number,
 *   failures: { file: string, linePct: number, branchPct: number }[]
 * }} Number of enforced files and any below-floor failures.
 */
export function evaluateCoverageFloors(
  records,
  { lineFloor, branchFloor, rootDir = "", isExcluded = isExcludedPath },
) {
  const failures = [];
  let checked = 0;

  for (const record of records) {
    const file = normalizePath(record.file, rootDir);
    if (isExcluded(file)) {
      continue;
    }

    const linePct = record.linesFound > 0 ? (record.linesHit / record.linesFound) * 100 : 100;
    const branchPct =
      record.branchesFound > 0 ? (record.branchesHit / record.branchesFound) * 100 : 100;

    checked += 1;

    if (linePct < lineFloor || branchPct < branchFloor) {
      failures.push({ file, linePct, branchPct });
    }
  }

  return { checked, failures };
}

/**
 * Format a floor-check outcome into a human-readable report string.
 * @param {ReturnType<typeof evaluateCoverageFloors>} outcome - Evaluation result.
 * @param {{ lineFloor: number, branchFloor: number }} floors - Enforced floors.
 * @returns {string} Report text (without a trailing newline).
 */
export function formatReport(outcome, { lineFloor, branchFloor }) {
  const floors = `lines >= ${lineFloor}%, branches >= ${branchFloor}%`;

  if (outcome.failures.length === 0) {
    return `Per-file coverage floors met for ${outcome.checked} file(s) (${floors})`;
  }

  const lines = outcome.failures.map((failure) => {
    const linePct = failure.linePct.toFixed(1);
    const branchPct = failure.branchPct.toFixed(1);
    return `  ${failure.file}: lines ${linePct}%, branches ${branchPct}%`;
  });
  return [`Per-file coverage floors not met (${floors}):`, ...lines].join("\n");
}

/**
 * Enforce per-file floors from the aggregate run's lcov report, or rerun the
 * suite with coverage (using the same excludes) when the report is absent.
 * @param {{
 *   execFileSyncImpl?: typeof execFileSync,
 *   existsSyncImpl?: typeof existsSync,
 *   readFileSyncImpl?: typeof readFileSync,
 *   rmSyncImpl?: typeof rmSync,
 *   consoleObj?: Console,
 *   rootDir?: string
 * }} [deps={}] - Injectable exec, fs, and console overrides.
 * @returns {number} Process exit code.
 */
export function runCoverageFloors({
  execFileSyncImpl = execFileSync,
  existsSyncImpl = existsSync,
  readFileSyncImpl = readFileSync,
  rmSyncImpl = rmSync,
  consoleObj = console,
  rootDir = ROOT_DIR,
} = {}) {
  const sharedReport = join(rootDir, DEFAULT_LCOV_PATH);
  let lcov;

  if (existsSyncImpl(sharedReport)) {
    // The aggregate coverage gate already produced the report; consume it
    // instead of running the whole suite under coverage a second time.
    lcov = readFileSyncImpl(sharedReport, "utf-8");
  } else {
    const dest = join(tmpdir(), `js-coverage-floors-${process.pid}.lcov`);
    // The finally block guarantees the temp report never leaks, whether the
    // suite run fails, the read throws, or everything succeeds.
    try {
      try {
        execFileSyncImpl(
          "node",
          [
            "--experimental-test-coverage",
            ...COVERAGE_EXCLUDES.map((pattern) => `--test-coverage-exclude=${pattern}`),
            "--test-reporter=lcov",
            `--test-reporter-destination=${dest}`,
            "--test",
            "tests/js/**/*.test.js",
          ],
          { cwd: rootDir, stdio: ["ignore", "ignore", "inherit"] },
        );
      } catch {
        consoleObj.error("JS test run failed; cannot evaluate per-file coverage floors.");
        return 1;
      }
      lcov = readFileSyncImpl(dest, "utf-8");
    } finally {
      rmSyncImpl(dest, { force: true });
    }
  }

  const outcome = evaluateCoverageFloors(parseLcov(lcov), {
    lineFloor: LINE_FLOOR,
    branchFloor: BRANCH_FLOOR,
    rootDir,
  });

  const report = formatReport(outcome, { lineFloor: LINE_FLOOR, branchFloor: BRANCH_FLOOR });
  if (outcome.failures.length > 0) {
    consoleObj.error(report);
    return 1;
  }

  consoleObj.log(report);
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exit(runCoverageFloors());
}
