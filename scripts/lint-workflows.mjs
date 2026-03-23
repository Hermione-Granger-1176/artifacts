import { createLinter } from 'actionlint';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..');

async function listWorkflowFiles() {
  const workflowDir = path.join(REPO_ROOT, '.github', 'workflows');
  const entries = await readdir(workflowDir, { withFileTypes: true });

  return entries
    .filter((entry) => entry.isFile() && /\.ya?ml$/u.test(entry.name))
    .map((entry) => path.posix.join('.github/workflows', entry.name))
    .sort();
}

async function main() {
  const lint = await createLinter();
  const workflowFiles = await listWorkflowFiles();
  let hasErrors = false;

  for (const relativePath of workflowFiles) {
    const filePath = path.join(REPO_ROOT, relativePath);
    const content = await readFile(filePath, 'utf-8');
    const results = lint(content, relativePath);
    const actionableResults = results.filter(
      (result) => !result.message.includes('undefined variable "vars"')
    );

    if (actionableResults.length > 0) {
      hasErrors = true;
    }

    for (const result of actionableResults) {
      process.stderr.write(
        `${result.file}:${result.line}:${result.column}: ${result.message} [${result.kind}]\n`
      );
    }
  }

  if (hasErrors) {
    process.exitCode = 1;
    return;
  }

  process.stdout.write(`Workflow lint passed for ${workflowFiles.length} file(s)\n`);
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.stack || error.message : String(error)}\n`);
  process.exitCode = 1;
});
