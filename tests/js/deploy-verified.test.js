import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

import {
  gitBlobSha,
  walkDir,
  computeChanges,
  computeRemoval,
  runVerifiedDeploy
} from '../../.github/actions/deploy-site/deploy-verified.mjs';

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
  assert.equal(graphqlInput.fileChanges.additions[0].path, 'pr-preview/pr-42/index.html');
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
});

test('runVerifiedDeploy throws on missing environment', async () => {
  await assert.rejects(
    () => runVerifiedDeploy({ env: {} }),
    /Missing required GitHub environment for deploy action/
  );
});
