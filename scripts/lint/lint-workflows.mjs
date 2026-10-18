import { createLinter } from "actionlint";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "..", "..");

/**
 * Drop actionlint results that are known false positives for this repo.
 * Only the `undefined variable "vars"` diagnostic is suppressed; every other
 * message (including real errors) must survive so regressions stay visible.
 * @param {{ message: string }[]} results - Raw actionlint results.
 * @returns {{ message: string }[]} Results worth reporting.
 */
export function filterActionableResults(results) {
  return results.filter((result) => !result.message.includes('undefined variable "vars"'));
}

/**
 * List workflow YAML files relative to the repo root, sorted.
 * @param {string} [repoRoot=REPO_ROOT] - Repository root directory.
 * @param {typeof readdir} [readdirImpl=readdir] - Injectable directory reader.
 * @returns {Promise<string[]>} Sorted repo-relative workflow file paths.
 */
export async function listWorkflowFiles(repoRoot = REPO_ROOT, readdirImpl = readdir) {
  const workflowDir = path.join(repoRoot, ".github", "workflows");
  const entries = await readdirImpl(workflowDir, { withFileTypes: true });

  return entries
    .filter((entry) => entry.isFile() && /\.ya?ml$/u.test(entry.name))
    .map((entry) => path.posix.join(".github/workflows", entry.name))
    .sort();
}

/**
 * Format one actionlint result as a `file:line:column: message [kind]` line.
 * @param {{ file: string, line: number, column: number, message: string, kind: string }} result - Actionlint result.
 * @returns {string} Report line ending in a newline.
 */
function formatResult(result) {
  return `${result.file}:${result.line}:${result.column}: ${result.message} [${result.kind}]\n`;
}

/**
 * Lint one workflow file with a fresh actionlint instance.
 *
 * The actionlint WebAssembly module accumulates linear memory across calls on
 * one instance and eventually panics with "RuntimeError: unreachable" on a
 * large workflow such as update.yml. A per-file instance keeps each lint
 * within its own heap.
 * @param {string} relativePath - Repo-relative workflow path.
 * @param {{
 *   createLinterImpl: typeof createLinter,
 *   readFileImpl: typeof readFile,
 *   repoRoot: string
 * }} deps - Linter factory, file reader, and repository root.
 * @returns {Promise<{ message: string }[]>} Results worth reporting.
 */
async function lintWorkflowFile(relativePath, { createLinterImpl, readFileImpl, repoRoot }) {
  const lint = await createLinterImpl();
  const content = await readFileImpl(path.join(repoRoot, relativePath), "utf-8");
  return filterActionableResults(lint(content, relativePath));
}

/**
 * Lint every workflow file with actionlint and report actionable results.
 * @param {{
 *   createLinterImpl?: typeof createLinter,
 *   readFileImpl?: typeof readFile,
 *   readdirImpl?: typeof readdir,
 *   repoRoot?: string,
 *   stdout?: { write: (chunk: string) => void },
 *   stderr?: { write: (chunk: string) => void }
 * }} [deps={}] - Injectable linter, fs, root, and output streams.
 * @returns {Promise<number>} Exit code (0 clean, 1 on lint findings).
 */
export async function runWorkflowLint({
  createLinterImpl = createLinter,
  readFileImpl = readFile,
  readdirImpl = readdir,
  repoRoot = REPO_ROOT,
  stdout = process.stdout,
  stderr = process.stderr,
} = {}) {
  const workflowFiles = await listWorkflowFiles(repoRoot, readdirImpl);
  let hasErrors = false;

  for (const relativePath of workflowFiles) {
    const actionableResults = await lintWorkflowFile(relativePath, {
      createLinterImpl,
      readFileImpl,
      repoRoot,
    });

    if (actionableResults.length > 0) {
      hasErrors = true;
      stderr.write(actionableResults.map(formatResult).join(""));
    }
  }

  if (hasErrors) {
    return 1;
  }

  stdout.write(`Workflow lint passed for ${workflowFiles.length} file(s)\n`);
  return 0;
}

if (
  typeof process.argv[1] === "string" &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  runWorkflowLint()
    .then((code) => {
      process.exitCode = code;
    })
    .catch((error) => {
      process.stderr.write(
        `${error instanceof Error ? error.stack || error.message : String(error)}\n`,
      );
      process.exitCode = 1;
    });
}
