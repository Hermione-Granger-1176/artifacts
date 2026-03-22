import fs from 'node:fs';
import path from 'node:path';
import { fetchJson, createApiClients } from '../verified-commit/verified-commit.mjs';

/**
 * Recursively walk a directory and return all file paths relative to root.
 * @param {string} dir - Directory to walk.
 * @param {string} [root=dir] - Root directory for relative path computation.
 * @param {{ readdirSync: typeof fs.readdirSync }} [deps] - Injectable fs helpers.
 * @returns {string[]} Relative file paths.
 */
export function walkDir(dir, root = dir, deps = { readdirSync: fs.readdirSync }) {
  const results = [];
  for (const entry of deps.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...walkDir(full, root, deps));
    } else {
      results.push(path.relative(root, full));
    }
  }
  return results;
}

/**
 * Compute file additions and deletions for a full-tree deploy.
 * Preserves files under the preview root directory on the remote branch.
 * @param {string[]} localFiles - Files in the deploy directory.
 * @param {Map<string, string>} remoteFiles - Current remote files (path to SHA).
 * @param {string} previewRoot - Directory prefix to preserve (e.g. "pr-preview").
 * @param {string} deployDir - Local directory containing the site.
 * @param {{ readFileSync: typeof fs.readFileSync }} [deps] - Injectable fs helpers.
 * @returns {{ additions: { path: string, contents: string }[], deletions: { path: string }[] }}
 *   GraphQL file payloads.
 */
export function computeChanges(localFiles, remoteFiles, previewRoot, deployDir, deps = {}) {
  const { readFileSync = fs.readFileSync } = deps;
  const additions = [];
  const deletions = [];
  const localSet = new Set(localFiles);

  for (const filePath of localFiles) {
    const contents = readFileSync(path.join(deployDir, filePath)).toString('base64');
    additions.push({ path: filePath, contents });
  }

  for (const [remotePath] of remoteFiles) {
    if (remotePath.startsWith(`${previewRoot}/`)) {
      continue;
    }
    if (!localSet.has(remotePath)) {
      deletions.push({ path: remotePath });
    }
  }

  return { additions, deletions };
}

/**
 * Deploy a local directory to a GitHub Pages branch with a verified commit.
 * @param {{
 *   env?: NodeJS.ProcessEnv,
 *   consoleObj?: Console,
 *   fetchDependencies?: object,
 *   readFileSyncImpl?: typeof fs.readFileSync,
 *   walkDirImpl?: (dir: string) => string[]
 * }} [deps={}] - Injectable environment, fs, and fetch overrides.
 * @returns {Promise<{ deployed: boolean, commitUrl: string }>} Deploy result metadata.
 */
export async function runVerifiedDeploy({
  env = process.env,
  consoleObj = console,
  fetchDependencies = {},
  readFileSyncImpl = fs.readFileSync,
  walkDirImpl = (dir) => walkDir(dir)
} = {}) {
  const token = env.GH_TOKEN;
  const pagesBranch = env.PAGES_BRANCH || 'gh-pages';
  const previewRoot = env.PREVIEW_ROOT || 'pr-preview';
  const commitMessage = env.COMMIT_MESSAGE || 'Deploy site';
  const deployDir = env.DEPLOY_DIR || '_site';
  const [owner, repo] = (env.GITHUB_REPOSITORY || '').split('/');

  if (!token || !owner || !repo) {
    throw new Error('Missing required GitHub environment for deploy action');
  }

  const clients = createApiClients({ owner, repo, token, fetchDependencies });

  // Fetch current branch HEAD SHA.
  const ref = await clients.fetchJson(
    `https://api.github.com/repos/${owner}/${repo}/git/ref/heads/${pagesBranch}`
  );
  const headSha = ref.object.sha;
  consoleObj.log(`Current ${pagesBranch} HEAD: ${headSha}`);

  // Fetch current branch tree.
  const tree = await clients.fetchJson(
    `https://api.github.com/repos/${owner}/${repo}/git/trees/${headSha}?recursive=1`
  );
  const remoteFiles = new Map();
  for (const item of tree.tree) {
    if (item.type === 'blob') {
      remoteFiles.set(item.path, item.sha);
    }
  }
  consoleObj.log(`Remote tree: ${remoteFiles.size} files`);

  // Walk local deploy directory.
  const localFiles = walkDirImpl(deployDir);
  consoleObj.log(`Local deploy: ${localFiles.length} files`);

  // Compute additions and deletions.
  const { additions, deletions } = computeChanges(
    localFiles, remoteFiles, previewRoot, deployDir,
    { readFileSync: readFileSyncImpl }
  );

  if (additions.length === 0 && deletions.length === 0) {
    consoleObj.log('No changes to deploy');
    return { deployed: false, commitUrl: '' };
  }

  consoleObj.log(`Deploying: ${additions.length} additions, ${deletions.length} deletions`);

  // Create verified commit via GraphQL.
  const mutation = `
    mutation ($input: CreateCommitOnBranchInput!) {
      createCommitOnBranch(input: $input) {
        commit { oid url }
      }
    }
  `;

  const data = await clients.graphql(mutation, {
    input: {
      branch: {
        repositoryNameWithOwner: `${owner}/${repo}`,
        branchName: pagesBranch
      },
      expectedHeadOid: headSha,
      message: { headline: commitMessage },
      fileChanges: { additions, deletions }
    }
  });

  const commit = data.createCommitOnBranch.commit;
  consoleObj.log(`Created verified deploy commit: ${commit.url}`);
  return { deployed: true, commitUrl: commit.url };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runVerifiedDeploy().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
