import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createBranchName,
  createGitArgs,
  fetchJson,
  parseDiffOutput,
  runVerifiedCommit,
  splitPathspec
} from '../../.github/actions/verified-commit/verified-commit.mjs';

test('splitPathspec and createGitArgs preserve pathspec ordering', () => {
  const pathspec = splitPathspec('js/data.js\nREADME.md\n');
  assert.deepEqual(pathspec, ['js/data.js', 'README.md']);
  assert.deepEqual(createGitArgs(pathspec), ['diff', '--staged', '--name-status', '--', 'js/data.js', 'README.md']);
});

test('parseDiffOutput handles additions, deletions, and renames', () => {
  const fileContents = new Map([
    ['new.txt', Buffer.from('new')],
    ['renamed.txt', Buffer.from('renamed')]
  ]);

  const result = parseDiffOutput('A\tnew.txt\nD\told.txt\nR100\tbefore.txt\trenamed.txt', {
    existsSync(filePath) {
      return fileContents.has(filePath);
    },
    readFileSync(filePath) {
      return fileContents.get(filePath);
    }
  });

  assert.deepEqual(result.deletions, [{ path: 'old.txt' }, { path: 'before.txt' }]);
  assert.deepEqual(result.additions.map((item) => item.path), ['new.txt', 'renamed.txt']);
});

test('fetchJson retries transient failures and returns parsed json', async () => {
  let attempts = 0;
  const result = await fetchJson(
    'https://example.com/api',
    { method: 'GET' },
    {
      fetchImpl: async () => {
        attempts += 1;
        if (attempts < 2) {
          const error = new Error('503 Service Unavailable');
          throw error;
        }

        return {
          ok: true,
          status: 200,
          json: async () => ({ ok: true })
        };
      },
      sleepImpl: async () => {}
    }
  );

  assert.equal(attempts, 2);
  assert.deepEqual(result, { ok: true });
});

test('createBranchName is deterministic for a given date', () => {
  assert.equal(createBranchName('auto/update', new Date('2026-03-19T12:00:00Z')), 'auto/update-20260319');
});

test('runVerifiedCommit exits early when there are no staged changes', async () => {
  const outputs = [];
  const result = await runVerifiedCommit({
    env: {
      GH_TOKEN_INPUT: 'token',
      GITHUB_OUTPUT: '/tmp/output',
      GITHUB_REPOSITORY: 'octo/repo',
      PATHSPEC_INPUT: ''
    },
    execFileSyncImpl() {
      return '';
    },
    appendFileSyncImpl(_path, value) {
      outputs.push(value.trim());
    },
    consoleObj: { log() {}, error() {} }
  });

  assert.deepEqual(result, { changed: false, resultUrl: '' });
  assert.deepEqual(outputs, ['changed=false', 'result-url=']);
});

test('runVerifiedCommit falls back to a pull request after direct commit failure', async () => {
  const outputs = [];
  const requests = [];
  const result = await runVerifiedCommit({
    env: {
      GH_TOKEN_INPUT: 'token',
      GITHUB_OUTPUT: '/tmp/output',
      GITHUB_REPOSITORY: 'octo/repo',
      BASE_BRANCH: 'main',
      EXPECTED_HEAD_SHA: 'abc123',
      COMMIT_HEADLINE: 'Update generated artifacts [skip ci]',
      FALLBACK_BRANCH_PREFIX: 'auto/update-artifacts',
      PR_TITLE: 'Update generated artifacts',
      PR_BODY: 'Body',
      PATHSPEC_INPUT: 'js/data.js'
    },
    execFileSyncImpl() {
      return 'A\tjs/data.js';
    },
    existsSyncImpl() {
      return true;
    },
    readFileSyncImpl() {
      return Buffer.from('payload');
    },
    appendFileSyncImpl(_path, value) {
      outputs.push(value.trim());
    },
    consoleObj: { log() {}, error() {} },
    fetchDependencies: {
      fetchImpl: async (url, options = {}) => {
        requests.push({ url, options });
        const routes = [
          {
            matches: (candidateUrl) => candidateUrl === 'https://api.github.com/graphql',
            response: () => {
              const body = JSON.parse(options.body);
              const branchName = body.variables.input.branch.branchName;
              if (branchName === 'main') {
                return {
                  ok: true,
                  status: 200,
                  json: async () => ({ errors: [{ message: 'protected branch' }] })
                };
              }

              return {
                ok: true,
                status: 200,
                json: async () => ({
                  data: {
                    createCommitOnBranch: {
                      commit: {
                        oid: 'def456',
                        url: 'https://example.com/commit/def456'
                      }
                    }
                  }
                })
              };
            }
          },
          {
            matches: (candidateUrl) => candidateUrl.endsWith('/git/refs'),
            response: () => ({
              ok: true,
              status: 201,
              json: async () => ({ ref: 'refs/heads/auto/update-artifacts-20260319' })
            })
          },
          {
            matches: (candidateUrl) => candidateUrl.includes('/pulls?'),
            response: () => ({
              ok: true,
              status: 200,
              json: async () => []
            })
          },
          {
            matches: (candidateUrl) => candidateUrl.endsWith('/pulls'),
            response: () => ({
              ok: true,
              status: 201,
              json: async () => ({ html_url: 'https://example.com/pr/123' })
            })
          }
        ];
        const route = routes.find((candidate) => candidate.matches(url));

        if (route) {
          return route.response();
        }

        throw new Error(`Unexpected URL: ${url}`);
      },
      sleepImpl: async () => {}
    },
    now: new Date('2026-03-19T12:00:00Z')
  });

  assert.equal(result.resultUrl, 'https://example.com/pr/123');
  assert.ok(requests.some((request) => request.url.endsWith('/git/refs')));
  assert.ok(outputs.includes('changed=true'));
  assert.ok(outputs.includes('result-url=https://example.com/pr/123'));
});
