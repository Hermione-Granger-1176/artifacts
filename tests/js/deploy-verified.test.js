import test from 'node:test';
import assert from 'node:assert/strict';

import {
  walkDir,
  computeChanges,
  runVerifiedDeploy
} from '../../.github/actions/deploy-site/deploy-verified.mjs';

test('walkDir lists all files recursively', () => {
  const tree = {
    'site': [
      { name: 'index.html', isDirectory: () => false },
      { name: 'js', isDirectory: () => true }
    ],
    'site/js': [
      { name: 'app.js', isDirectory: () => false }
    ]
  };

  const readdirSync = (dir) => (tree[dir] || []).map((e) => ({
    ...e,
    isDirectory: e.isDirectory
  }));

  const files = walkDir('site', 'site', { readdirSync });
  assert.deepEqual(files.sort(), ['index.html', 'js/app.js']);
});

test('walkDir returns empty array for empty directory', () => {
  const readdirSync = () => [];
  assert.deepEqual(walkDir('empty', 'empty', { readdirSync }), []);
});

test('computeChanges produces additions for all local files', () => {
  const fileContents = new Map([
    ['deploy/index.html', Buffer.from('<html>')],
    ['deploy/js/app.js', Buffer.from('code')]
  ]);

  const { additions, deletions } = computeChanges(
    ['index.html', 'js/app.js'],
    new Map(),
    'pr-preview',
    'deploy',
    { readFileSync: (p) => fileContents.get(p) }
  );

  assert.equal(additions.length, 2);
  assert.equal(deletions.length, 0);
  assert.equal(additions[0].path, 'index.html');
  assert.ok(additions[0].contents);
});

test('computeChanges produces deletions for remote files not in local', () => {
  const fileContents = new Map([
    ['deploy/index.html', Buffer.from('<html>')]
  ]);

  const remoteFiles = new Map([
    ['index.html', 'sha1'],
    ['old-file.js', 'sha2'],
    ['stale/page.html', 'sha3']
  ]);

  const { deletions } = computeChanges(
    ['index.html'],
    remoteFiles,
    'pr-preview',
    'deploy',
    { readFileSync: (p) => fileContents.get(p) }
  );

  assert.deepEqual(deletions, [
    { path: 'old-file.js' },
    { path: 'stale/page.html' }
  ]);
});

test('computeChanges preserves pr-preview directory', () => {
  const fileContents = new Map([
    ['deploy/index.html', Buffer.from('<html>')]
  ]);

  const remoteFiles = new Map([
    ['index.html', 'sha1'],
    ['pr-preview/pr-42/index.html', 'sha2'],
    ['pr-preview/pr-42/js/app.js', 'sha3'],
    ['old-file.js', 'sha4']
  ]);

  const { deletions } = computeChanges(
    ['index.html'],
    remoteFiles,
    'pr-preview',
    'deploy',
    { readFileSync: (p) => fileContents.get(p) }
  );

  assert.deepEqual(deletions, [{ path: 'old-file.js' }]);
});

test('computeChanges respects custom preview root', () => {
  const fileContents = new Map([
    ['deploy/index.html', Buffer.from('<html>')]
  ]);

  const remoteFiles = new Map([
    ['index.html', 'sha1'],
    ['previews/pr-1/index.html', 'sha2'],
    ['old.js', 'sha3']
  ]);

  const { deletions } = computeChanges(
    ['index.html'],
    remoteFiles,
    'previews',
    'deploy',
    { readFileSync: (p) => fileContents.get(p) }
  );

  assert.deepEqual(deletions, [{ path: 'old.js' }]);
});

test('runVerifiedDeploy creates a verified commit', async () => {
  let graphqlInput = null;

  const env = {
    GH_TOKEN: 'test-token',
    PAGES_BRANCH: 'gh-pages',
    PREVIEW_ROOT: 'pr-preview',
    COMMIT_MESSAGE: 'Deploy site for abc123',
    DEPLOY_DIR: 'site',
    GITHUB_REPOSITORY: 'owner/repo'
  };

  const fakeFetch = async (url, options) => {
    const body = options?.body ? JSON.parse(options.body) : null;

    if (url === 'https://api.github.com/graphql' && body?.query?.includes('createCommitOnBranch')) {
      graphqlInput = body.variables.input;
      return {
        ok: true,
        status: 200,
        json: async () => ({
          data: {
            createCommitOnBranch: {
              commit: { oid: 'abc123', url: 'https://github.com/owner/repo/commit/abc123' }
            }
          }
        })
      };
    }

    if (url.includes('/git/ref/heads/gh-pages')) {
      return {
        ok: true,
        status: 200,
        json: async () => ({ object: { sha: 'deadbeef' } })
      };
    }

    if (url.includes('/git/trees/')) {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          tree: [
            { path: 'index.html', type: 'blob', sha: 'old-sha' },
            { path: 'stale.css', type: 'blob', sha: 'stale-sha' },
            { path: 'pr-preview/pr-1/index.html', type: 'blob', sha: 'preview-sha' }
          ]
        })
      };
    }

    return { ok: true, status: 200, json: async () => ({}) };
  };

  const result = await runVerifiedDeploy({
    env,
    consoleObj: { log() {} },
    fetchDependencies: { fetchImpl: fakeFetch },
    readFileSyncImpl: () => Buffer.from('<html>'),
    walkDirImpl: () => ['index.html', 'js/app.js']
  });

  assert.ok(graphqlInput, 'GraphQL mutation should be called');
  assert.equal(graphqlInput.branch.branchName, 'gh-pages');
  assert.equal(graphqlInput.expectedHeadOid, 'deadbeef');
  assert.equal(graphqlInput.message.headline, 'Deploy site for abc123');
  assert.equal(graphqlInput.fileChanges.additions.length, 2);
  assert.deepEqual(graphqlInput.fileChanges.deletions, [{ path: 'stale.css' }]);
  assert.ok(result.deployed);
  assert.ok(result.commitUrl.includes('abc123'));
});

test('runVerifiedDeploy deploys idempotently when files match', async () => {
  const env = {
    GH_TOKEN: 'test-token',
    PAGES_BRANCH: 'gh-pages',
    PREVIEW_ROOT: 'pr-preview',
    COMMIT_MESSAGE: 'Deploy',
    DEPLOY_DIR: 'site',
    GITHUB_REPOSITORY: 'owner/repo'
  };

  const fakeFetch = async (url, options) => {
    const body = options?.body ? JSON.parse(options.body) : null;
    if (url === 'https://api.github.com/graphql' && body?.query?.includes('createCommitOnBranch')) {
      return {
        ok: true, status: 200,
        json: async () => ({
          data: { createCommitOnBranch: { commit: { oid: 'new', url: 'https://github.com/o/r/commit/new' } } }
        })
      };
    }
    if (url.includes('/git/ref/')) {
      return { ok: true, status: 200, json: async () => ({ object: { sha: 'abc' } }) };
    }
    if (url.includes('/git/trees/')) {
      return {
        ok: true, status: 200,
        json: async () => ({ tree: [{ path: 'index.html', type: 'blob', sha: 'sha1' }] })
      };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  };

  const result = await runVerifiedDeploy({
    env,
    consoleObj: { log() {} },
    fetchDependencies: { fetchImpl: fakeFetch },
    readFileSyncImpl: () => Buffer.from('<html>'),
    walkDirImpl: () => ['index.html']
  });

  assert.ok(result.deployed);
});

test('runVerifiedDeploy throws on missing environment', async () => {
  await assert.rejects(
    () => runVerifiedDeploy({ env: {} }),
    /Missing required GitHub environment for deploy action/
  );
});
