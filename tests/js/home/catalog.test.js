import test from 'node:test';
import assert from 'node:assert/strict';
import { performance } from 'node:perf_hooks';

import {
  filterAndSortArtifacts,
  getPageNumbers,
  hydrateArtifacts,
  normalizeSelection,
  sortValuesByDisplayOrder,
  splitListParam
} from '../../../js/modules/gallery/catalog.js';

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
    currentQuery: 'helper',
    currentSort: 'newest',
    currentTags: ['finance'],
    currentTools: ['claude']
  });

  assert.deepEqual(filtered.map((item) => item.id), ['artifact-b']);
  assert.deepEqual(
    filterAndSortArtifacts(artifacts, {
      currentQuery: '',
      currentSort: 'oldest',
      currentTags: [],
      currentTools: []
    }).map((item) => item.id),
    ['artifact-a', 'artifact-b']
  );
});

test('getPageNumbers lists every page up to seven', () => {
  assert.deepEqual(getPageNumbers(1, 1), [1]);
  assert.deepEqual(getPageNumbers(2, 2), [1, 2]);
  assert.deepEqual(getPageNumbers(4, 7), [1, 2, 3, 4, 5, 6, 7]);
});

test('getPageNumbers collapses long page ranges around the current page', () => {
  assert.deepEqual(getPageNumbers(5, 10), [1, '...', 4, 5, 6, '...', 10]);
  assert.deepEqual(getPageNumbers(6, 10), [1, '...', 5, 6, 7, '...', 10]);
});

test('getPageNumbers keeps one ellipsis near either end of a long range', () => {
  assert.deepEqual(getPageNumbers(1, 10), [1, 2, 3, 4, 5, '...', 10]);
  assert.deepEqual(getPageNumbers(4, 10), [1, 2, 3, 4, 5, '...', 10]);
  assert.deepEqual(getPageNumbers(7, 10), [1, '...', 6, 7, 8, 9, 10]);
  assert.deepEqual(getPageNumbers(10, 10), [1, '...', 6, 7, 8, 9, 10]);
});

test('getPageNumbers always returns seven slots past seven pages, and never hides one page behind an ellipsis', () => {
  for (const total of [8, 9, 10, 25, 100]) {
    for (let current = 1; current <= total; current += 1) {
      const slots = getPageNumbers(current, total);
      assert.equal(slots.length, 7, `${current} of ${total}`);
      assert.equal(slots[0], 1);
      assert.equal(slots.at(-1), total);
      assert.ok(slots.includes(current), `${current} of ${total} shows the current page`);

      slots.forEach((slot, index) => {
        if (slot === '...') {
          const gap = slots[index + 1] - slots[index - 1] - 1;
          assert.ok(gap >= 2, `${current} of ${total}: an ellipsis stands for at least two pages`);
        }
      });
    }
  }
});


test('filterAndSortArtifacts stays responsive on a larger catalog fixture', () => {
  const artifacts = hydrateArtifacts(
    Array.from({ length: 500 }, (_, index) => ({
      id: `artifact-${String(index + 1).padStart(3, '0')}`,
      name: `Artifact ${index + 1}`,
      description: index % 2 === 0 ? 'Finance helper and calculator' : 'LLM education explorer',
      tags: index % 3 === 0 ? ['finance', 'calculator'] : ['ai', 'education'],
      tools: index % 2 === 0 ? ['claude'] : ['chatgpt'],
      url: `apps/artifact-${String(index + 1).padStart(3, '0')}/`,
      thumbnail: null
    }))
  );

  const startedAt = performance.now();
  const filtered = filterAndSortArtifacts(artifacts, {
    currentQuery: 'helper',
    currentSort: 'newest',
    currentTags: ['finance'],
    currentTools: ['claude']
  });
  const durationMs = performance.now() - startedAt;

  assert.equal(filtered.length > 0, true);
  assert.equal(filtered[0].id, 'artifact-499');
  assert.equal(durationMs < 50, true);
});
