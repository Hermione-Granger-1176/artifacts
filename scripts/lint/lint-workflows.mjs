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
  const lint = await createLinterImpl();
  const workflowFiles = await listWorkflowFiles(repoRoot, readdirImpl);
  let hasErrors = false;

  for (const relativePath of workflowFiles) {
    const filePath = path.join(repoRoot, relativePath);
    const content = await readFileImpl(filePath, "utf-8");
    const results = lint(content, relativePath);
    const actionableResults = filterActionableResults(results);

    if (actionableResults.length > 0) {
      hasErrors = true;
      stderr.write(
        actionableResults
          .map(
            (result) =>
              `${result.file}:${result.line}:${result.column}: ${result.message} [${result.kind}]\n`,
          )
          .join(""),
      );
    }
  }

  if (hasErrors) {
    return 1;
  }

  stdout.write(`Workflow lint passed for ${workflowFiles.length} file(s)\n`);
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
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
