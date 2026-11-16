#!/usr/bin/env node

/**
 * Enforces per-file JS coverage floors.
 *
 * Reads the lcov report that `make coverage-js` writes. If the report is absent,
 * runs the suite with coverage using the same excludes as the aggregate gate.
 * Fails when any non-excluded source file is below the per-file line or branch
 * floor. The file set comes from the lcov report.
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

// Repo-relative path of the lcov report that `make coverage-js` writes.
export const DEFAULT_LCOV_PATH = ".artifacts/js-coverage.lcov";

// Matches the exclusions in package.json's test:coverage script.
const COVERAGE_EXCLUDES = ["node_modules/**", "tests/**"];

/** Summary counter records and the block field each one fills. */
const SUMMARY_COUNTERS = { "LF:": "lf", "LH:": "lh", "BRF:": "brf", "BRH:": "brh" };

/**
 * Split raw lcov text into per-record blocks (one per `SF:`/`end_of_record`
 * pair). Branch rows are grouped per line, in report order. Branch block ids
 * are not matched across blocks.
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
    } else if (line === "end_of_record") {
      current = null;
    } else {
      const separator = line.indexOf(":");
      const counter = SUMMARY_COUNTERS[line.slice(0, separator + 1)];
      if (counter) {
        current.summary[counter] = Number(line.slice(separator + 1)) || 0;
      }
    }
  }

  return blocks;
}

/**
 * Pick the block with the most lines hit and, independently, the block with the
 * most branches hit. Used for summary-only reports.
 * @param {string} file - Source file path shared by the blocks.
 * @param {ReturnType<typeof splitLcovBlocks>} blocks - All SF blocks for the file.
 * @returns {ReturnType<typeof mergeFileBlocks>} Merged coverage record.
 */
function mergeSummaryBlocks(file, blocks) {
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

/**
 * Read the line number out of a `${lineNo}:${position}` branch key.
 * @param {string} key - Branch key built by mergeDetailBlocks.
 * @returns {string} The line number part.
 */
function lineOfBranchKey(key) {
  return key.slice(0, key.indexOf(":"));
}

/**
 * Merge blocks that carry `DA` or `BRDA` detail (see mergeFileBlocks for the
 * line and branch semantics).
 * @param {string} file - Source file path shared by the blocks.
 * @param {ReturnType<typeof splitLcovBlocks>} detailBlocks - Blocks with line or branch rows.
 * @returns {ReturnType<typeof mergeFileBlocks>} Merged coverage record.
 */
function mergeDetailBlocks(file, detailBlocks) {
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
    const lineNo = lineOfBranchKey(key);
    const covered = detailBlocks.some(
      (block) => (block.lines.get(lineNo) ?? 0) > 0 && !block.branchRows.has(lineNo),
    );
    if (covered) {
      fullyCoveredLines.add(lineNo);
    }
  }

  let branchesHit = 0;
  for (const [key, taken] of mergedBranches) {
    if (taken > 0 || fullyCoveredLines.has(lineOfBranchKey(key))) {
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
 * Merge one file's SF blocks into a single coverage record.
 *
 * Lines are keyed by line number, and `DA` records merge with the maximum hit
 * count. Arms are keyed by line and position within that line. V8 omits `BRDA`
 * rows for fully taken branches, so an arm also counts as covered when any block
 * executes its line (`DA` > 0) without reporting branch rows for that line.
 * @param {ReturnType<typeof splitLcovBlocks>} blocks - All SF blocks for one file.
 * @returns {{ file: string, linesFound: number, linesHit: number, branchesFound: number, branchesHit: number }}
 *   Merged coverage record.
 */
function mergeFileBlocks(blocks) {
  const { file } = blocks[0];
  const detailBlocks = blocks.filter((block) => block.lines.size > 0 || block.branchRows.size > 0);

  return detailBlocks.length === 0
    ? mergeSummaryBlocks(file, blocks)
    : mergeDetailBlocks(file, detailBlocks);
}

/**
 * Parse lcov text into merged per-file coverage records.
 *
 * Each test file runs in its own process, so a source module loaded by several
 * test files appears as several `SF` blocks. These are merged per file (see
 * mergeFileBlocks for the line and branch rules). Reports with only summary
 * counters (`LF`/`LH`/`BRF`/`BRH`) use those numbers.
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
 * Excludes tests, dependencies, vendored code, and generated gallery data.
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
 * Compute a coverage percentage, treating nothing measurable as fully covered.
 * @param {number} hit - Covered count.
 * @param {number} found - Measurable count.
 * @returns {number} Percentage from 0 to 100.
 */
function percentCovered(hit, found) {
  return found > 0 ? (hit / found) * 100 : 100;
}

/**
 * Evaluate parsed lcov records against per-file coverage floors.
 * Files with zero measurable lines or branches count as fully covered for
 * that dimension.
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

    const linePct = percentCovered(record.linesHit, record.linesFound);
    const branchPct = percentCovered(record.branchesHit, record.branchesFound);

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
 * Run the suite under coverage and return its lcov report, or null when the
 * run fails. The temp report is removed in every case.
 * @param {{
 *   execFileSyncImpl: typeof execFileSync,
 *   readFileSyncImpl: typeof readFileSync,
 *   rmSyncImpl: typeof rmSync,
 *   consoleObj: Console,
 *   rootDir: string
 * }} deps - Exec, fs, console, and repo root.
 * @returns {string | null} Raw lcov text, or null after a failed test run.
 */
function collectFallbackLcov({
  execFileSyncImpl,
  readFileSyncImpl,
  rmSyncImpl,
  consoleObj,
  rootDir,
}) {
  const dest = join(tmpdir(), `js-coverage-floors-${process.pid}.lcov`);
  // The finally block removes the temp report on every path.
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
      return null;
    }
    return readFileSyncImpl(dest, "utf-8");
  } finally {
    rmSyncImpl(dest, { force: true });
  }
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

  // Reuse the report from make coverage-js when it exists. Otherwise run the
  // suite under coverage.
  const lcov = existsSyncImpl(sharedReport)
    ? readFileSyncImpl(sharedReport, "utf-8")
    : collectFallbackLcov({ execFileSyncImpl, readFileSyncImpl, rmSyncImpl, consoleObj, rootDir });
  if (lcov === null) {
    return 1;
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

if (
  typeof process.argv[1] === "string" &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  process.exit(runCoverageFloors());
}
