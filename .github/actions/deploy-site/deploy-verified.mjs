import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { createApiClients } from '../verified-commit/verified-commit.mjs';

/**
 * Compute the Git blob SHA for a buffer (matches how Git hashes blobs).
 * @param {Buffer} content - Raw file content.
 * @returns {string} Hex-encoded SHA-1 blob hash.
 */
export function gitBlobSha(content) {
  const header = `blob ${content.length}\0`;
  return createHash('sha1').update(header).update(content).digest('hex');
}

/**
 * Recursively walk a directory and return all file paths relative to root.
 * @param {string} dir - Directory to walk.
 * @param {string} [root=dir] - Root directory for relative path computation.
 * @param {{ readdirSync: typeof fs.readdirSync }} [deps] - Injectable fs helpers.
 * @returns {string[]} Relative file paths.
 */
export function walkDir(dir, root = dir, deps = { readdirSync: fs.readdirSync }) {
  return deps.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    return entry.isDirectory() ? walkDir(full, root, deps) : [path.relative(root, full)];
  });
}

/**
 * Compute file additions and deletions for a deploy.
 * Compares Git blob SHAs to skip unchanged files (true idempotency).
 * Preserves files under the preview root directory on the remote branch.
 * @param {string[]} localFiles - Files in the deploy directory.
 * @param {Map<string, string>} remoteFiles - Current remote files (path to blob SHA).
 * @param {string} previewRoot - Directory prefix to preserve (e.g. "pr-preview").
 * @param {string} deployDir - Local directory containing the site.
 * @param {string} [targetPrefix=''] - Subdirectory prefix for preview deploys.
 * @param {{ readFileSync: typeof fs.readFileSync }} [deps] - Injectable fs helpers.
 * @returns {{ additions: { path: string, contents: string }[], deletions: { path: string }[] }}
 *   GraphQL file payloads.
 */
export function computeChanges(
  localFiles, remoteFiles, previewRoot, deployDir,
  targetPrefix = '', deps = {}
) {
  const { readFileSync = fs.readFileSync } = deps;
  const additions = [];
  const deletions = [];
  const localSet = new Set();

  for (const filePath of localFiles) {
    const targetPath = targetPrefix ? `${targetPrefix}/${filePath}` : filePath;
    localSet.add(targetPath);

    const content = readFileSync(path.join(deployDir, filePath));
    const localSha = gitBlobSha(content);
    const remoteSha = remoteFiles.get(targetPath);

    if (remoteSha === localSha) {
      continue;
    }

    additions.push({ path: targetPath, contents: content.toString('base64') });
  }

  for (const [remotePath] of remoteFiles) {
    const skip = targetPrefix
      ? !remotePath.startsWith(`${targetPrefix}/`)
      : remotePath.startsWith(`${previewRoot}/`);
    if (skip || localSet.has(remotePath)) {
      continue;
    }
    deletions.push({ path: remotePath });
  }

  return { additions, deletions };
}

/**
 * Compute deletions for removing a subdirectory from the remote branch.
 * @param {Map<string, string>} remoteFiles - Current remote files (path to blob SHA).
 * @param {string} subdirPrefix - Subdirectory to remove (e.g. "pr-preview/pr-42").
 * @returns {{ additions: { path: string, contents: string }[], deletions: { path: string }[] }}
 *   GraphQL file payloads (additions is always empty).
 */
export function computeRemoval(remoteFiles, subdirPrefix) {
  const deletions = [...remoteFiles.keys()]
    .filter((remotePath) => remotePath.startsWith(`${subdirPrefix}/`))
    .map((remotePath) => ({ path: remotePath }));
  return { additions: [], deletions };
}

/**
 * Fetch the current HEAD SHA and tree for a branch.
 * @param {{ fetchJson: (url: string, options?: RequestInit) => Promise<object|null>, owner: string, repo: string }} clients - API clients.
 * @param {string} branch - Branch name.
 * @param {Console} consoleObj - Logger.
 * @returns {Promise<{ headSha: string, remoteFiles: Map<string, string> }>}
 */
async function fetchBranchState(clients, branch, consoleObj) {
  const ref = await clients.fetchJson(
    `https://api.github.com/repos/${clients.owner}/${clients.repo}/git/ref/heads/${branch}`
  );
  const headSha = ref.object.sha;
  consoleObj.log(`Current ${branch} HEAD: ${headSha}`);

  // Fetch commit to get tree SHA (the trees API needs a tree SHA, not a commit SHA).
  const commit = await clients.fetchJson(
    `https://api.github.com/repos/${clients.owner}/${clients.repo}/git/commits/${headSha}`
  );
  const treeSha = commit.tree.sha;

  const tree = await clients.fetchJson(
    `https://api.github.com/repos/${clients.owner}/${clients.repo}/git/trees/${treeSha}?recursive=1`
  );
  const remoteFiles = new Map(
    tree.tree
      .filter((item) => item.type === 'blob')
      .map((item) => [item.path, item.sha])
  );
  consoleObj.log(`Remote tree: ${remoteFiles.size} files`);

  return { headSha, remoteFiles };
}

/**
 * Create a verified commit on a branch via the GraphQL API.
 * @param {{ graphql: (query: string, variables: object) => Promise<object>, owner: string, repo: string }} clients - API clients.
 * @param {string} branch - Target branch name.
 * @param {string} headSha - Expected HEAD OID.
 * @param {string} headline - Commit message headline.
 * @param {{ additions: object[], deletions: object[] }} fileChanges - File payloads.
 * @returns {Promise<{ oid: string, url: string }>} Created commit metadata.
 */
async function createVerifiedCommit(clients, branch, headSha, headline, fileChanges) {
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
        repositoryNameWithOwner: `${clients.owner}/${clients.repo}`,
        branchName: branch
      },
      expectedHeadOid: headSha,
      message: { headline },
      fileChanges
    }
  });

  return data.createCommitOnBranch.commit;
}

/**
 * Deploy a local directory to a GitHub Pages branch with a verified commit.
 *
 * Modes (controlled by environment variables):
 * - **Full deploy**: `DEPLOY_DIR` set, no `DEPLOY_SUBDIR` or `REMOVE_SUBDIR`.
 *   Replaces the entire branch tree (except preview root).
 * - **Preview deploy**: `DEPLOY_DIR` and `DEPLOY_SUBDIR` set.
 *   Deploys to a subdirectory (e.g. `pr-preview/pr-42/`).
 * - **Preview remove**: `REMOVE_SUBDIR` set.
 *   Deletes all files under a subdirectory.
 *
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
  const deployDir = env.DEPLOY_DIR || '';
  const deploySubdir = env.DEPLOY_SUBDIR || '';
  const removeSubdir = env.REMOVE_SUBDIR || '';
  const [owner, repo] = (env.GITHUB_REPOSITORY || '').split('/');

  if (!token || !owner || !repo) {
    throw new Error('Missing required GitHub environment for deploy action');
  }

  const clients = createApiClients({ owner, repo, token, fetchDependencies });
  const { headSha, remoteFiles } = await fetchBranchState(clients, pagesBranch, consoleObj);

  let fileChanges;

  if (removeSubdir) {
    consoleObj.log(`Removing subdirectory: ${removeSubdir}`);
    fileChanges = computeRemoval(remoteFiles, removeSubdir);
  } else {
    if (!deployDir) {
      throw new Error(`DEPLOY_DIR is required for ${deploySubdir ? 'preview' : 'full'} deploys`);
    }
    const localFiles = walkDirImpl(deployDir);
    const suffix = deploySubdir ? ` → ${deploySubdir}/` : '';
    consoleObj.log(`Local deploy: ${localFiles.length} files${suffix}`);
    fileChanges = computeChanges(
      localFiles, remoteFiles, previewRoot, deployDir, deploySubdir,
      { readFileSync: readFileSyncImpl }
    );
  }

  const { additions, deletions } = fileChanges;

  if (additions.length === 0 && deletions.length === 0) {
    consoleObj.log('No changes to deploy');
    return { deployed: false, commitUrl: '' };
  }

  consoleObj.log(`Deploying: ${additions.length} additions, ${deletions.length} deletions`);

  const commit = await createVerifiedCommit(clients, pagesBranch, headSha, commitMessage, fileChanges);
  consoleObj.log(`Created verified deploy commit: ${commit.url}`);
  return { deployed: true, commitUrl: commit.url };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runVerifiedDeploy().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
