import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import { setTimeout as sleep } from 'node:timers/promises';

export const DEFAULT_REQUEST_TIMEOUT_MS = 15000;
export const DEFAULT_MAX_ATTEMPTS = 3;

/**
 * Split newline-delimited pathspec input into trimmed entries.
 * @param {string} input - Newline-separated pathspec entries.
 * @returns {string[]} Trimmed, non-empty pathspec entries.
 */
export function splitPathspec(input) {
  return (input || '')
    .split(/\r?\n/)
    .map((entry) => entry.trim())
    .filter(Boolean);
}

/**
 * Parse `git diff --name-status` output into additions and deletions for the GraphQL API.
 * @param {string} diffOutput - Raw output from `git diff --name-status`.
 * @param {{
 *   existsSync: (path: string) => boolean,
 *   readFileSync: (path: string) => Buffer
 * }} deps - File-system helpers.
 * @returns {{ additions: { path: string, contents: string }[], deletions: { path: string }[] }}
 *   GraphQL file payloads.
 */
export function parseDiffOutput(diffOutput, { existsSync, readFileSync }) {
  const additions = [];
  const deletions = [];

  if (!diffOutput.trim()) {
    return { additions, deletions };
  }

  for (const line of diffOutput.trim().split('\n')) {
    const [status = '', path1, path2] = line.split('\t');
    const code = status.charAt(0);

    switch (code) {
      case 'R':
        if (path1 && path2) {
          deletions.push({ path: path1 });
          additions.push({ path: path2, contents: readFileSync(path2).toString('base64') });
        }
        continue;

      case 'D':
        if (path1) {
          deletions.push({ path: path1 });
        }
        continue;

      default:
        if (!path1 || !existsSync(path1)) {
          continue;
        }

        additions.push({ path: path1, contents: readFileSync(path1).toString('base64') });
    }
  }

  return { additions, deletions };
}

/**
 * Fetch JSON from a URL with retries and a per-request timeout.
 * @param {string} url - Request URL.
 * @param {RequestInit} options - Fetch options.
 * @param {{
 *   fetchImpl?: typeof fetch,
 *   maxAttempts?: number,
 *   requestTimeoutMs?: number,
 *   sleepImpl?: (delayMs: number) => Promise<void>
 * }} [dependencies] - Injectable overrides for fetch, retry limits, and timeout.
 * @returns {Promise<object | null>} Parsed JSON body, or null on 204.
 */
export async function fetchJson(url, options, dependencies = {}) {
  const {
    fetchImpl = fetch,
    maxAttempts = DEFAULT_MAX_ATTEMPTS,
    requestTimeoutMs = DEFAULT_REQUEST_TIMEOUT_MS,
    sleepImpl = sleep
  } = dependencies;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), requestTimeoutMs);

    try {
      const response = await fetchImpl(url, {
        ...options,
        signal: controller.signal
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(`${response.status} ${response.statusText}: ${message}`);
      }

      if (response.status === 204) {
        return null;
      }

      return await response.json();
    } catch (error) {
      if (attempt < maxAttempts && isRetryableError(error)) {
        await sleepImpl(attempt * 250);
        continue;
      }

      if (error instanceof Error) {
        throw error;
      }

      throw new Error(String(error));
    } finally {
      clearTimeout(timeout);
    }
  }
}

/**
 * Check whether an error looks transient enough to retry.
 * @param {Error | null} error - Error to classify.
 * @returns {boolean} Whether the error is transient and worth retrying.
 */
export function isRetryableError(error) {
  if (!error) {
    return false;
  }

  if (error.name === 'AbortError') {
    return true;
  }

  const message = String(error.message || error);
  return /429|502|503|504|timed out|ECONNRESET|network/i.test(message);
}

/**
 * Build `git diff --staged --name-status` arguments for an optional pathspec.
 * @param {string[]} pathspec - Paths to restrict the diff.
 * @returns {string[]} Argument array for execFileSync.
 */
export function createGitArgs(pathspec) {
  const gitArgs = ['diff', '--staged', '--name-status'];
  if (pathspec.length > 0) {
    gitArgs.push('--', ...pathspec);
  }
  return gitArgs;
}

/**
 * Generate a date-stamped branch name (for example `prefix-20260319`).
 * @param {string} prefix - Branch name prefix.
 * @param {Date} [date=new Date()] - Date used for the stamp.
 * @returns {string} Date-stamped branch name.
 */
export function createBranchName(prefix, date = new Date()) {
  const value = date.toISOString().slice(0, 10).replace(/-/g, '');
  return `${prefix}-${value}`;
}

/**
 * Create authenticated GitHub REST and GraphQL helpers.
 * @param {{
 *   owner: string,
 *   repo: string,
 *   token: string,
 *   fetchDependencies: object
 * }} config - Repository identity, token, and injectable fetch helpers.
 * @returns {{
 *   fetchJson: (url: string, options?: RequestInit) => Promise<object | null>,
 *   graphql: (query: string, variables: object) => Promise<object>,
 *   owner: string,
 *   repo: string
 * }} Authenticated API helpers.
 */
export function createApiClients({ owner, repo, token, fetchDependencies }) {
  const fetchWithHeaders = (url, options = {}) =>
    fetchJson(
      url,
      {
        ...options,
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/vnd.github+json',
          'Content-Type': 'application/json',
          ...(options.headers || {})
        }
      },
      fetchDependencies
    );

  return {
    async fetchJson(url, options = {}) {
      return fetchWithHeaders(url, options);
    },

    async graphql(query, variables) {
      const response = await fetchWithHeaders('https://api.github.com/graphql', {
        method: 'POST',
        body: JSON.stringify({ query, variables })
      });

      if (response.errors && response.errors.length > 0) {
        throw new Error(response.errors.map((item) => item.message).join('; '));
      }

      return response.data;
    },

    owner,
    repo
  };
}

/**
 * Commit staged changes via the GitHub GraphQL API (verified/signed), falling back to a PR.
 * @param {{
 *   env?: NodeJS.ProcessEnv,
 *   execFileSyncImpl?: typeof execFileSync,
 *   existsSyncImpl?: typeof fs.existsSync,
 *   readFileSyncImpl?: typeof fs.readFileSync,
 *   appendFileSyncImpl?: typeof fs.appendFileSync,
 *   consoleObj?: Console,
 *   fetchDependencies?: object,
 *   now?: Date
 * }} [deps={}] - Injectable environment, fs, exec, and fetch overrides.
 * @returns {Promise<{ changed: boolean, resultUrl: string }>} Commit or PR result metadata.
 */
export async function runVerifiedCommit({
  env = process.env,
  execFileSyncImpl = execFileSync,
  existsSyncImpl = fs.existsSync,
  readFileSyncImpl = fs.readFileSync,
  appendFileSyncImpl = fs.appendFileSync,
  consoleObj = console,
  fetchDependencies = {},
  now = new Date()
} = {}) {
  const outputFile = env.GITHUB_OUTPUT;
  const token = env.GH_TOKEN_INPUT;
  const baseBranch = env.BASE_BRANCH;
  const expectedHeadSha = env.EXPECTED_HEAD_SHA;
  const commitHeadline = env.COMMIT_HEADLINE;
  const fallbackBranchPrefix = env.FALLBACK_BRANCH_PREFIX;
  const prTitle = env.PR_TITLE;
  const prBody = env.PR_BODY;
  const pathspec = splitPathspec(env.PATHSPEC_INPUT || '');
  const [owner, repo] = (env.GITHUB_REPOSITORY || '').split('/');

  if (!outputFile || !token || !owner || !repo) {
    throw new Error('Missing required GitHub environment for verified commit action');
  }

  const setOutput = (name, value) => {
    appendFileSyncImpl(outputFile, `${name}=${value}\n`);
  };

  const noChange = (message) => {
    consoleObj.log(message);
    setOutput('changed', 'false');
    setOutput('result-url', '');
    return { changed: false, resultUrl: '' };
  };

  const gitArgs = createGitArgs(pathspec);
  const diffOutput = execFileSyncImpl('git', gitArgs, { encoding: 'utf8' }).trim();

  if (!diffOutput) {
    return noChange('No staged changes to commit');
  }

  const { additions, deletions } = parseDiffOutput(diffOutput, {
    existsSync: existsSyncImpl,
    readFileSync: readFileSyncImpl
  });

  if (additions.length === 0 && deletions.length === 0) {
    return noChange('No staged file payloads were produced');
  }

  setOutput('changed', 'true');

  const clients = createApiClients({ owner, repo, token, fetchDependencies });

  const mutation = `
    mutation ($input: CreateCommitOnBranchInput!) {
      createCommitOnBranch(input: $input) {
        commit { oid url }
      }
    }
  `;

  const createCommit = async (branchName, headSha, headline) => {
    const data = await clients.graphql(mutation, {
      input: {
        branch: {
          repositoryNameWithOwner: `${owner}/${repo}`,
          branchName
        },
        expectedHeadOid: headSha,
        message: { headline },
        fileChanges: { additions, deletions }
      }
    });

    return data.createCommitOnBranch.commit;
  };

  try {
    const commit = await createCommit(baseBranch, expectedHeadSha, commitHeadline);
    consoleObj.log(`Created verified commit: ${commit.url}`);
    setOutput('result-url', commit.url);
    return { changed: true, resultUrl: commit.url };
  } catch (error) {
    consoleObj.log(`Direct commit failed (${error.message}), creating branch and PR`);
  }

  const fallbackBranch = createBranchName(fallbackBranchPrefix, now);
  let fallbackHeadSha = expectedHeadSha;

  try {
    await clients.fetchJson(`https://api.github.com/repos/${owner}/${repo}/git/refs`, {
      method: 'POST',
      body: JSON.stringify({
        ref: `refs/heads/${fallbackBranch}`,
        sha: expectedHeadSha
      })
    });
  } catch (_error) {
    const existingRef = await clients.fetchJson(
      `https://api.github.com/repos/${owner}/${repo}/git/ref/heads/${fallbackBranch}`
    );
    fallbackHeadSha = existingRef.object.sha;
  }

  const fallbackCommit = await createCommit(
    fallbackBranch,
    fallbackHeadSha,
    commitHeadline.replace(' [skip ci]', '')
  );
  consoleObj.log(`Created verified fallback commit: ${fallbackCommit.url}`);

  const pullsUrl = new URL(`https://api.github.com/repos/${owner}/${repo}/pulls`);
  pullsUrl.search = new URLSearchParams({
    state: 'open',
    head: `${owner}:${fallbackBranch}`
  }).toString();
  const existingPulls = await clients.fetchJson(pullsUrl.toString());

  if (existingPulls.length > 0) {
    consoleObj.log(`Updated existing PR: ${existingPulls[0].html_url}`);
    setOutput('result-url', existingPulls[0].html_url);
    return { changed: true, resultUrl: existingPulls[0].html_url };
  }

  const pullRequest = await clients.fetchJson(
    `https://api.github.com/repos/${owner}/${repo}/pulls`,
    {
      method: 'POST',
      body: JSON.stringify({
        title: prTitle,
        body: prBody,
        head: fallbackBranch,
        base: baseBranch
      })
    }
  );

  consoleObj.log(`Created PR: ${pullRequest.html_url}`);
  setOutput('result-url', pullRequest.html_url);
  return { changed: true, resultUrl: pullRequest.html_url };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runVerifiedCommit().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
