import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

import {
  gitBlobSha,
  walkDir,
  computeChanges,
  computeRemoval,
  runVerifiedDeploy,
  writeGitHubOutputs,
  isNotFoundError
} from '../../../.github/actions/deploy-site/deploy-verified.mjs';

/** Build a fetch Response-like object with a JSON body. */
function jsonResponse(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

/** Build a non-2xx Response-like object whose text() carries the body. */
function errorResponse(status, statusText, bodyText = '') {
  return { ok: false, status, statusText, text: async () => bodyText };
}

/** Compute the expected Git blob SHA for a string. */
function expectedSha(content) {
  const buf = Buffer.from(content);
  const header = `blob ${buf.length}\0`;
  return createHash('sha1').update(header).update(buf).digest('hex');
}

test('gitBlobSha matches Git blob hashing format', () => {
  const content = Buffer.from('hello world');
  const sha = gitBlobSha(content);
  assert.equal(sha, expectedSha('hello world'));
  assert.equal(sha.length, 40);
});

test('walkDir lists all files recursively', () => {
  const tree = {
    site: [
      { name: 'index.html', isDirectory: () => false },
      { name: 'js', isDirectory: () => true }
    ],
    'site/js': [
      { name: 'app.js', isDirectory: () => false }
    ]
  };

  const readdirSync = (dir) => tree[dir] || [];

  const files = walkDir('site', 'site', { readdirSync });
  assert.deepEqual(files.sort(), ['index.html', 'js/app.js']);
});

test('walkDir returns empty array for empty directory', () => {
  const readdirSync = () => [];
  assert.deepEqual(walkDir('empty', 'empty', { readdirSync }), []);
});

test('computeChanges skips unchanged files by blob SHA', () => {
  const htmlContent = Buffer.from('<html>');
  const htmlSha = gitBlobSha(htmlContent);

  const remoteFiles = new Map([
    ['index.html', htmlSha],
    ['old.js', 'stale-sha']
  ]);

  const { additions, deletions } = computeChanges(
    ['index.html'],
    remoteFiles,
    'pr-preview',
    'deploy',
    '',
    { readFileSync: () => htmlContent }
  );

  assert.equal(additions.length, 0, 'unchanged file should be skipped');
  assert.deepEqual(deletions, [{ path: 'old.js' }]);
});

test('computeChanges adds changed files', () => {
  const newContent = Buffer.from('<html>new</html>');

  const remoteFiles = new Map([
    ['index.html', 'old-sha-different']
  ]);

  const { additions } = computeChanges(
    ['index.html'],
    remoteFiles,
    'pr-preview',
    'deploy',
    '',
    { readFileSync: () => newContent }
  );

  assert.equal(additions.length, 1);
  assert.equal(additions[0].path, 'index.html');
});

test('computeChanges preserves pr-preview directory', () => {
  const remoteFiles = new Map([
    ['index.html', 'sha1'],
    ['pr-preview/pr-42/index.html', 'sha2'],
    ['old-file.js', 'sha4']
  ]);

  const { deletions } = computeChanges(
    ['index.html'],
    remoteFiles,
    'pr-preview',
    'deploy',
    '',
    { readFileSync: () => Buffer.from('x') }
  );

  assert.deepEqual(deletions, [{ path: 'old-file.js' }]);
});

test('computeChanges with targetPrefix for preview deploys', () => {
  const content = Buffer.from('<html>');

  const remoteFiles = new Map([
    ['pr-preview/pr-5/old.html', 'sha1'],
    ['index.html', 'root-sha']
  ]);

  const { additions, deletions } = computeChanges(
    ['index.html', 'js/app.js'],
    remoteFiles,
    'pr-preview',
    'deploy',
    'pr-preview/pr-5',
    { readFileSync: () => content }
  );

  assert.equal(additions.length, 2);
  assert.equal(additions[0].path, 'pr-preview/pr-5/index.html');
  assert.equal(additions[1].path, 'pr-preview/pr-5/js/app.js');
  assert.deepEqual(deletions, [{ path: 'pr-preview/pr-5/old.html' }]);
});

test('computeRemoval deletes all files under a subdirectory', () => {
  const remoteFiles = new Map([
    ['index.html', 'sha1'],
    ['pr-preview/pr-42/index.html', 'sha2'],
    ['pr-preview/pr-42/js/app.js', 'sha3'],
    ['pr-preview/pr-10/index.html', 'sha4']
  ]);

  const { additions, deletions } = computeRemoval(remoteFiles, 'pr-preview/pr-42');

  assert.deepEqual(additions, []);
  assert.deepEqual(deletions, [
    { path: 'pr-preview/pr-42/index.html' },
    { path: 'pr-preview/pr-42/js/app.js' }
  ]);
});

test('computeRemoval returns empty when subdirectory does not exist', () => {
  const remoteFiles = new Map([['index.html', 'sha1']]);
  const { deletions } = computeRemoval(remoteFiles, 'pr-preview/pr-99');
  assert.deepEqual(deletions, []);
});

test('runVerifiedDeploy creates a verified commit for full deploy', async () => {
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
        ok: true, status: 200,
        json: async () => ({
          data: { createCommitOnBranch: { commit: { oid: 'abc', url: 'https://github.com/o/r/commit/abc' } } }
        })
      };
    }
    if (url.includes('/git/ref/heads/gh-pages')) {
      return { ok: true, status: 200, json: async () => ({ object: { sha: 'deadbeef' } }) };
    }
    if (url.includes('/git/commits/deadbeef')) {
      return { ok: true, status: 200, json: async () => ({ tree: { sha: 'tree-sha' } }) };
    }
    if (url.includes('/git/trees/tree-sha')) {
      return {
        ok: true, status: 200,
        json: async () => ({
          tree: [
            { path: 'stale.css', type: 'blob', sha: 'stale-sha' },
            { path: 'pr-preview/pr-1/index.html', type: 'blob', sha: 'p-sha' }
          ]
        })
      };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  };

  const result = await runVerifiedDeploy({
    env,
    consoleObj: { log() {}, error() {} },
    fetchDependencies: { fetchImpl: fakeFetch },
    readFileSyncImpl: () => Buffer.from('<html>'),
    walkDirImpl: () => ['index.html']
  });

  assert.ok(graphqlInput);
  assert.equal(graphqlInput.expectedHeadOid, 'deadbeef');
  assert.equal(graphqlInput.fileChanges.additions.length, 1);
  assert.deepEqual(graphqlInput.fileChanges.deletions, [{ path: 'stale.css' }]);
  assert.ok(result.deployed);
  assert.equal(result.commitSha, 'abc');
  assert.equal(result.commitUrl, 'https://github.com/o/r/commit/abc');
});

test('runVerifiedDeploy returns deployed false when nothing changed', async () => {
  const htmlContent = Buffer.from('<html>');
  const htmlSha = gitBlobSha(htmlContent);

  const env = {
    GH_TOKEN: 'test-token',
    PAGES_BRANCH: 'gh-pages',
    PREVIEW_ROOT: 'pr-preview',
    COMMIT_MESSAGE: 'Deploy',
    DEPLOY_DIR: 'site',
    GITHUB_REPOSITORY: 'owner/repo'
  };

  let graphqlCalled = false;

  const fakeFetch = async (url, options) => {
    const body = options?.body ? JSON.parse(options.body) : null;
    if (url === 'https://api.github.com/graphql' && body?.query?.includes('createCommitOnBranch')) {
      graphqlCalled = true;
      return { ok: true, status: 200, json: async () => ({}) };
    }
    if (url.includes('/git/ref/')) {
      return { ok: true, status: 200, json: async () => ({ object: { sha: 'abc' } }) };
    }
    if (url.includes('/git/commits/abc')) {
      return { ok: true, status: 200, json: async () => ({ tree: { sha: 'tsha' } }) };
    }
    if (url.includes('/git/trees/')) {
      return {
        ok: true, status: 200,
        json: async () => ({ tree: [{ path: 'index.html', type: 'blob', sha: htmlSha }] })
      };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  };

  const result = await runVerifiedDeploy({
    env,
    consoleObj: { log() {}, error() {} },
    fetchDependencies: { fetchImpl: fakeFetch },
    readFileSyncImpl: () => htmlContent,
    walkDirImpl: () => ['index.html']
  });

  assert.equal(result.deployed, false, 'should not deploy when content matches');
  assert.equal(result.commitSha, 'abc');
  assert.equal(result.commitUrl, '');
  assert.equal(graphqlCalled, false, 'GraphQL should not be called');
});

test('runVerifiedDeploy handles preview deploy mode', async () => {
  let graphqlInput = null;

  const env = {
    GH_TOKEN: 'test-token',
    PAGES_BRANCH: 'gh-pages',
    PREVIEW_ROOT: 'pr-preview',
    COMMIT_MESSAGE: 'Deploy preview for PR 42',
    DEPLOY_DIR: 'site',
    DEPLOY_SUBDIR: 'pr-preview/pr-42',
    GITHUB_REPOSITORY: 'owner/repo'
  };

  const fakeFetch = async (url, options) => {
    const body = options?.body ? JSON.parse(options.body) : null;
    if (url === 'https://api.github.com/graphql' && body?.query?.includes('createCommitOnBranch')) {
      graphqlInput = body.variables.input;
      return {
        ok: true, status: 200,
        json: async () => ({
          data: { createCommitOnBranch: { commit: { oid: 'p', url: 'https://github.com/o/r/commit/p' } } }
        })
      };
    }
    if (url.includes('/git/ref/')) {
      return { ok: true, status: 200, json: async () => ({ object: { sha: 'h' } }) };
    }
    if (url.includes('/git/commits/h')) {
      return { ok: true, status: 200, json: async () => ({ tree: { sha: 't' } }) };
    }
    if (url.includes('/git/trees/')) {
      return { ok: true, status: 200, json: async () => ({ tree: [] }) };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  };

  const result = await runVerifiedDeploy({
    env,
    consoleObj: { log() {}, error() {} },
    fetchDependencies: { fetchImpl: fakeFetch },
    readFileSyncImpl: () => Buffer.from('html'),
    walkDirImpl: () => ['index.html']
  });

  assert.ok(result.deployed);
  assert.equal(result.commitSha, 'p');
  assert.equal(graphqlInput.fileChanges.additions[0].path, 'pr-preview/pr-42/index.html');
});

test('runVerifiedDeploy reads from a custom deploy directory', async () => {
  let observedPath = null;

  const env = {
    GH_TOKEN: 'test-token',
    PAGES_BRANCH: 'gh-pages',
    PREVIEW_ROOT: 'pr-preview',
    COMMIT_MESSAGE: 'Deploy site for abc123',
    DEPLOY_DIR: 'custom-site',
    GITHUB_REPOSITORY: 'owner/repo'
  };

  const fakeFetch = async (url, options) => {
    const body = options?.body ? JSON.parse(options.body) : null;
    if (url === 'https://api.github.com/graphql' && body?.query?.includes('createCommitOnBranch')) {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          data: { createCommitOnBranch: { commit: { oid: 'abc', url: 'https://github.com/o/r/commit/abc' } } }
        })
      };
    }
    if (url.includes('/git/ref/')) {
      return { ok: true, status: 200, json: async () => ({ object: { sha: 'abc' } }) };
    }
    if (url.includes('/git/commits/abc')) {
      return { ok: true, status: 200, json: async () => ({ tree: { sha: 'tree' } }) };
    }
    if (url.includes('/git/trees/tree')) {
      return { ok: true, status: 200, json: async () => ({ tree: [] }) };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  };

  await runVerifiedDeploy({
    env,
    consoleObj: { log() {}, error() {} },
    fetchDependencies: { fetchImpl: fakeFetch },
    readFileSyncImpl(filePath) {
      observedPath = filePath;
      return Buffer.from('<html>');
    },
    walkDirImpl: () => ['index.html']
  });

  assert.equal(observedPath, 'custom-site/index.html');
});

test('runVerifiedDeploy handles preview remove mode', async () => {
  let graphqlInput = null;

  const env = {
    GH_TOKEN: 'test-token',
    PAGES_BRANCH: 'gh-pages',
    PREVIEW_ROOT: 'pr-preview',
    COMMIT_MESSAGE: 'Remove preview for PR 42',
    REMOVE_SUBDIR: 'pr-preview/pr-42',
    GITHUB_REPOSITORY: 'owner/repo'
  };

  const fakeFetch = async (url, options) => {
    const body = options?.body ? JSON.parse(options.body) : null;
    if (url === 'https://api.github.com/graphql' && body?.query?.includes('createCommitOnBranch')) {
      graphqlInput = body.variables.input;
      return {
        ok: true, status: 200,
        json: async () => ({
          data: { createCommitOnBranch: { commit: { oid: 'r', url: 'https://github.com/o/r/commit/r' } } }
        })
      };
    }
    if (url.includes('/git/ref/')) {
      return { ok: true, status: 200, json: async () => ({ object: { sha: 'h' } }) };
    }
    if (url.includes('/git/commits/h')) {
      return { ok: true, status: 200, json: async () => ({ tree: { sha: 't' } }) };
    }
    if (url.includes('/git/trees/')) {
      return {
        ok: true, status: 200,
        json: async () => ({
          tree: [
            { path: 'index.html', type: 'blob', sha: 'root' },
            { path: 'pr-preview/pr-42/index.html', type: 'blob', sha: 's1' },
            { path: 'pr-preview/pr-42/js/app.js', type: 'blob', sha: 's2' }
          ]
        })
      };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  };

  const result = await runVerifiedDeploy({
    env,
    consoleObj: { log() {}, error() {} },
    fetchDependencies: { fetchImpl: fakeFetch }
  });

  assert.ok(result.deployed);
  assert.equal(result.commitSha, 'r');
  assert.deepEqual(graphqlInput.fileChanges.additions, []);
  assert.equal(graphqlInput.fileChanges.deletions.length, 2);
});

test('runVerifiedDeploy returns deployed false for empty removal', async () => {
  const env = {
    GH_TOKEN: 'test-token',
    PAGES_BRANCH: 'gh-pages',
    PREVIEW_ROOT: 'pr-preview',
    COMMIT_MESSAGE: 'Remove preview',
    REMOVE_SUBDIR: 'pr-preview/pr-99',
    GITHUB_REPOSITORY: 'owner/repo'
  };

  const fakeFetch = async (url) => {
    if (url.includes('/git/ref/')) {
      return { ok: true, status: 200, json: async () => ({ object: { sha: 'h' } }) };
    }
    if (url.includes('/git/commits/h')) {
      return { ok: true, status: 200, json: async () => ({ tree: { sha: 't' } }) };
    }
    if (url.includes('/git/trees/')) {
      return { ok: true, status: 200, json: async () => ({ tree: [] }) };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  };

  const result = await runVerifiedDeploy({
    env,
    consoleObj: { log() {}, error() {} },
    fetchDependencies: { fetchImpl: fakeFetch }
  });

  assert.equal(result.deployed, false);
  assert.equal(result.commitSha, 'h');
});

test('runVerifiedDeploy throws on missing environment', async () => {
  await assert.rejects(
    () => runVerifiedDeploy({ env: {} }),
    /Missing required GitHub environment for deploy action/
  );
});

test('writeGitHubOutputs writes deploy metadata when output file is present', () => {
  let observedPath = null;
  let observedData = null;

  writeGitHubOutputs(
    { deployed: true, commitUrl: 'https://github.com/o/r/commit/abc', commitSha: 'abc' },
    { GITHUB_OUTPUT: '/tmp/github-output' },
    (filePath, data, encoding) => {
      observedPath = filePath;
      observedData = { data, encoding };
    }
  );

  assert.equal(observedPath, '/tmp/github-output');
  assert.deepEqual(observedData, {
    data: [
      'deployed=true',
      'commit-url=https://github.com/o/r/commit/abc',
      'commit-sha=abc',
      ''
    ].join('\n'),
    encoding: 'utf8'
  });
});

test('writeGitHubOutputs skips writes when output file is absent', () => {
  let wrote = false;

  writeGitHubOutputs(
    { deployed: false, commitUrl: '', commitSha: 'abc' },
    {},
    () => {
      wrote = true;
    }
  );

  assert.equal(wrote, false);
});

test('isNotFoundError matches only leading 404 status errors', () => {
  assert.equal(isNotFoundError(new Error('404 Not Found: Branch not found')), true);
  assert.equal(isNotFoundError('404 Not Found'), true);
  assert.equal(isNotFoundError(new Error('403 Forbidden: no access')), false);
  assert.equal(isNotFoundError(new Error('500 Internal Server Error')), false);
  assert.equal(isNotFoundError(new Error('Server said error 404 somewhere')), false);
  assert.equal(isNotFoundError(null), false);
});

test('runVerifiedDeploy bootstraps gh-pages when the branch ref is missing', async () => {
  const calls = [];
  const bodies = {};
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
    const method = options?.method;
    const body = options?.body ? JSON.parse(options.body) : null;

    if (url === 'https://api.github.com/graphql') {
      graphqlInput = body.variables.input;
      return jsonResponse({
        data: { createCommitOnBranch: { commit: { oid: 'boot-sha', url: 'https://github.com/o/r/commit/boot' } } }
      });
    }
    if (url.endsWith('/git/ref/heads/gh-pages')) {
      return errorResponse(404, 'Not Found', 'Not Found');
    }
    if (method === 'POST' && url.endsWith('/git/blobs')) {
      calls.push('blob');
      bodies.blob = body;
      return jsonResponse({ sha: 'blob-sha' });
    }
    if (method === 'POST' && url.endsWith('/git/trees')) {
      calls.push('tree');
      bodies.tree = body;
      return jsonResponse({ sha: 'boot-tree' });
    }
    if (method === 'POST' && url.endsWith('/git/commits')) {
      calls.push('commit');
      bodies.commit = body;
      return jsonResponse({ sha: 'boot-sha' });
    }
    if (method === 'POST' && url.endsWith('/git/refs')) {
      calls.push('refs');
      bodies.refs = body;
      return jsonResponse({ ref: 'refs/heads/gh-pages' });
    }
    if (url.includes('/git/commits/boot-sha')) {
      return jsonResponse({ tree: { sha: 'boot-tree' } });
    }
    if (url.includes('/git/trees/boot-tree')) {
      return jsonResponse({ tree: [] });
    }
    return jsonResponse({});
  };

  const result = await runVerifiedDeploy({
    env,
    consoleObj: { log() {}, error() {} },
    fetchDependencies: { fetchImpl: fakeFetch },
    readFileSyncImpl: () => Buffer.from('<html>'),
    walkDirImpl: () => ['index.html']
  });

  assert.deepEqual(calls, ['blob', 'tree', 'commit', 'refs'], 'bootstrap creates blob, tree, commit, ref in order');
  assert.equal(bodies.blob.content, '');
  assert.deepEqual(bodies.commit.parents, [], 'bootstrap commit is parentless');
  assert.equal(bodies.commit.message, 'Bootstrap gh-pages');
  assert.equal(bodies.refs.ref, 'refs/heads/gh-pages');
  assert.equal(bodies.tree.tree[0].path, '.nojekyll');
  assert.ok(result.deployed, 'deploy proceeds after bootstrap');
  assert.equal(graphqlInput.expectedHeadOid, 'boot-sha', 'deploy targets the bootstrapped HEAD');
});

test('runVerifiedDeploy adopts the winning HEAD when bootstrap loses the ref race', async () => {
  let refFetches = 0;
  let graphqlInput = null;

  const env = {
    GH_TOKEN: 'test-token',
    PAGES_BRANCH: 'gh-pages',
    PREVIEW_ROOT: 'pr-preview',
    COMMIT_MESSAGE: 'Deploy',
    DEPLOY_DIR: 'site',
    GITHUB_REPOSITORY: 'owner/repo'
  };

  const fakeFetch = async (url, options) => {
    const method = options?.method;
    const body = options?.body ? JSON.parse(options.body) : null;

    if (url === 'https://api.github.com/graphql') {
      graphqlInput = body.variables.input;
      return jsonResponse({
        data: { createCommitOnBranch: { commit: { oid: 'next', url: 'https://github.com/o/r/commit/next' } } }
      });
    }
    if (url.endsWith('/git/ref/heads/gh-pages')) {
      refFetches += 1;
      // The first lookup sees the missing branch; the retry after the lost
      // race sees the concurrent run's commit.
      return refFetches === 1
        ? errorResponse(404, 'Not Found', 'Not Found')
        : jsonResponse({ object: { sha: 'winner-sha' } });
    }
    if (method === 'POST' && url.endsWith('/git/blobs')) {
      return jsonResponse({ sha: 'blob-sha' });
    }
    if (method === 'POST' && url.endsWith('/git/trees')) {
      return jsonResponse({ sha: 'boot-tree' });
    }
    if (method === 'POST' && url.endsWith('/git/commits')) {
      return jsonResponse({ sha: 'loser-sha' });
    }
    if (method === 'POST' && url.endsWith('/git/refs')) {
      return errorResponse(422, 'Unprocessable Entity', 'Reference already exists');
    }
    if (url.includes('/git/commits/winner-sha')) {
      return jsonResponse({ tree: { sha: 'winner-tree' } });
    }
    if (url.includes('/git/trees/winner-tree')) {
      return jsonResponse({ tree: [] });
    }
    return jsonResponse({});
  };

  const result = await runVerifiedDeploy({
    env,
    consoleObj: { log() {}, error() {} },
    fetchDependencies: { fetchImpl: fakeFetch },
    readFileSyncImpl: () => Buffer.from('<html>'),
    walkDirImpl: () => ['index.html']
  });

  assert.equal(refFetches, 2, 'the ref is refetched after losing the create race');
  assert.ok(result.deployed);
  assert.equal(graphqlInput.expectedHeadOid, 'winner-sha', 'deploy targets the concurrent winner HEAD');
});

test('runVerifiedDeploy does not bootstrap on non-404 ref errors', async () => {
  let blobRequested = false;

  const env = {
    GH_TOKEN: 'test-token',
    PAGES_BRANCH: 'gh-pages',
    PREVIEW_ROOT: 'pr-preview',
    COMMIT_MESSAGE: 'Deploy',
    DEPLOY_DIR: 'site',
    GITHUB_REPOSITORY: 'owner/repo'
  };

  const fakeFetch = async (url) => {
    if (url.endsWith('/git/ref/heads/gh-pages')) {
      return errorResponse(403, 'Forbidden', 'no access');
    }
    if (url.includes('/git/blobs')) {
      blobRequested = true;
    }
    return jsonResponse({});
  };

  await assert.rejects(
    () =>
      runVerifiedDeploy({
        env,
        consoleObj: { log() {}, error() {} },
        fetchDependencies: { fetchImpl: fakeFetch },
        readFileSyncImpl: () => Buffer.from('<html>'),
        walkDirImpl: () => ['index.html']
      }),
    /403/
  );
  assert.equal(blobRequested, false, 'no bootstrap attempted on non-404 errors');
});

test('runVerifiedDeploy does not bootstrap on the happy path', async () => {
  let blobRequested = false;

  const env = {
    GH_TOKEN: 'test-token',
    PAGES_BRANCH: 'gh-pages',
    PREVIEW_ROOT: 'pr-preview',
    COMMIT_MESSAGE: 'Deploy site',
    DEPLOY_DIR: 'site',
    GITHUB_REPOSITORY: 'owner/repo'
  };

  const fakeFetch = async (url, options) => {
    const body = options?.body ? JSON.parse(options.body) : null;
    if (url === 'https://api.github.com/graphql' && body?.query?.includes('createCommitOnBranch')) {
      return jsonResponse({
        data: { createCommitOnBranch: { commit: { oid: 'abc', url: 'https://github.com/o/r/commit/abc' } } }
      });
    }
    if (url.includes('/git/blobs') || url.includes('/git/refs')) {
      blobRequested = true;
      return jsonResponse({ sha: 'x' });
    }
    if (url.includes('/git/ref/heads/gh-pages')) {
      return jsonResponse({ object: { sha: 'deadbeef' } });
    }
    if (url.includes('/git/commits/deadbeef')) {
      return jsonResponse({ tree: { sha: 'tree-sha' } });
    }
    if (url.includes('/git/trees/tree-sha')) {
      return jsonResponse({ tree: [] });
    }
    return jsonResponse({});
  };

  const result = await runVerifiedDeploy({
    env,
    consoleObj: { log() {}, error() {} },
    fetchDependencies: { fetchImpl: fakeFetch },
    readFileSyncImpl: () => Buffer.from('<html>'),
    walkDirImpl: () => ['index.html']
  });

  assert.ok(result.deployed);
  assert.equal(blobRequested, false, 'no bootstrap calls when the branch already exists');
});
