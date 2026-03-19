import test from 'node:test';
import assert from 'node:assert/strict';

import {
  filterAndSortArtifacts,
  getPageNumbers,
  hydrateArtifacts,
  normalizeSelection,
  sortValuesByDisplayOrder,
  splitListParam
} from '../../js/modules/catalog.js';

test('hydrateArtifacts precomputes lowercase search text', () => {
  const [artifact] = hydrateArtifacts([
    {
      id: 'loan-tool',
      name: 'Loan Tool',
      description: 'Helpful calculator',
      tags: ['finance'],
      tools: ['claude'],
      url: 'apps/loan-tool/',
      thumbnail: null
    }
  ]);

  assert.equal(
    artifact.searchText,
    'loan tool helpful calculator finance claude loan-tool'
  );
});

test('splitListParam and normalizeSelection preserve allowed values', () => {
  const raw = splitListParam('claude, chatgpt,claude,unknown');
  assert.deepEqual(raw, ['claude', 'chatgpt', 'claude', 'unknown']);
  assert.deepEqual(normalizeSelection(raw, ['claude', 'chatgpt']), ['claude', 'chatgpt']);
});

test('sortValuesByDisplayOrder keeps configured values first', () => {
  assert.deepEqual(
    sortValuesByDisplayOrder(['gemini', 'claude', 'custom'], ['claude', 'chatgpt', 'gemini']),
    ['claude', 'gemini', 'custom']
  );
});

test('filterAndSortArtifacts filters by search/tool/tag and sort order', () => {
  const artifacts = hydrateArtifacts([
    {
      id: 'artifact-b',
      name: 'Artifact B',
      description: 'Finance helper',
      tags: ['finance'],
      tools: ['claude'],
      url: 'apps/artifact-b/',
      thumbnail: null
    },
    {
      id: 'artifact-a',
      name: 'Artifact A',
      description: 'Calculator helper',
      tags: ['calculator'],
      tools: ['chatgpt'],
      url: 'apps/artifact-a/',
      thumbnail: null
    }
  ]);

  const filtered = filterAndSortArtifacts(artifacts, {
    currentFilter: 'helper',
    currentSort: 'newest',
    currentTags: ['finance'],
    currentTools: ['claude']
  });

  assert.deepEqual(filtered.map((item) => item.id), ['artifact-b']);
  assert.deepEqual(
    filterAndSortArtifacts(artifacts, {
      currentFilter: '',
      currentSort: 'oldest',
      currentTags: [],
      currentTools: []
    }).map((item) => item.id),
    ['artifact-a', 'artifact-b']
  );
});

test('getPageNumbers collapses long page ranges', () => {
  assert.deepEqual(getPageNumbers(5, 10), [1, 2, '...', 4, 5, 6, '...', 9, 10]);
});
