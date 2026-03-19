import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import { setTimeout as sleep } from 'node:timers/promises';

export const DEFAULT_REQUEST_TIMEOUT_MS = 15000;
export const DEFAULT_MAX_ATTEMPTS = 3;

export function splitPathspec(input) {
  return (input || '')
    .split(/\r?\n/)
    .map((entry) => entry.trim())
    .filter(Boolean);
}

export function parseDiffOutput(diffOutput, { existsSync, readFileSync }) {
  const additions = [];
  const deletions = [];

  if (!diffOutput.trim()) {
    return { additions, deletions };
  }

  for (const line of diffOutput.trim().split('\n')) {
    const parts = line.split('\t');
    const status = parts[0] || '';

    switch (status.charAt(0)) {
      case 'R': {
        if (parts.length >= 3) {
          deletions.push({ path: parts[1] });
          additions.push({
            path: parts[2],
            contents: readFileSync(parts[2]).toString('base64')
          });
        }
        break;
      }

      case 'D': {
        if (parts[1]) {
          deletions.push({ path: parts[1] });
        }
        break;
      }

      default: {
        const filePath = parts[1];
        if (filePath && existsSync(filePath)) {
          additions.push({
            path: filePath,
            contents: readFileSync(filePath).toString('base64')
          });
        }
      }
    }
  }

  return { additions, deletions };
}

export async function fetchJson(url, options, dependencies = {}) {
  const {
    fetchImpl = fetch,
    maxAttempts = DEFAULT_MAX_ATTEMPTS,
    requestTimeoutMs = DEFAULT_REQUEST_TIMEOUT_MS,
    sleepImpl = sleep
  } = dependencies;

  let lastError = null;

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
      lastError = error;
      const shouldRetry = attempt < maxAttempts && isRetryableError(error);
      if (!shouldRetry) {
        throw error;
      }

      await sleepImpl(attempt * 250);
    } finally {
      clearTimeout(timeout);
    }
  }

  throw lastError;
}

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

export function createGitArgs(pathspec) {
  const gitArgs = ['diff', '--staged', '--name-status'];
  if (pathspec.length > 0) {
    gitArgs.push('--', ...pathspec);
  }
  return gitArgs;
}

export function createBranchName(prefix, date = new Date()) {
  const value = date.toISOString().slice(0, 10).replace(/-/g, '');
  return `${prefix}-${value}`;
}

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

  const gitArgs = createGitArgs(pathspec);
  const diffOutput = execFileSyncImpl('git', gitArgs, { encoding: 'utf8' }).trim();

  if (!diffOutput) {
    consoleObj.log('No staged changes to commit');
    setOutput('changed', 'false');
    setOutput('result-url', '');
    return { changed: false, resultUrl: '' };
  }

  const { additions, deletions } = parseDiffOutput(diffOutput, {
    existsSync: existsSyncImpl,
    readFileSync: readFileSyncImpl
  });

  if (additions.length === 0 && deletions.length === 0) {
    consoleObj.log('No staged file payloads were produced');
    setOutput('changed', 'false');
    setOutput('result-url', '');
    return { changed: false, resultUrl: '' };
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
