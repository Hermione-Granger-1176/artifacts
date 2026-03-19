import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildGalleryUrl,
  readGalleryStateFromSearch
} from '../../js/modules/gallery-app.js';

test('readGalleryStateFromSearch normalizes query params against allowed values', () => {
  const state = readGalleryStateFromSearch({
    search: '?page=0&sort=oldest&q=Loan%20Calc&tool=chatgpt,claude,unknown&tag=finance,calculator,invalid',
    allTools: ['claude', 'chatgpt'],
    allTags: ['finance', 'calculator']
  });

  assert.deepEqual(state, {
    page: 1,
    q: 'loan calc',
    sort: 'oldest',
    tools: ['claude', 'chatgpt'],
    tags: ['finance', 'calculator'],
    rawQuery: 'Loan Calc'
  });
});

test('readGalleryStateFromSearch falls back to defaults for invalid params', () => {
  const state = readGalleryStateFromSearch({
    search: '?page=abc&sort=latest&tool=unknown&tag=invalid',
    allTools: ['claude'],
    allTags: ['finance']
  });

  assert.deepEqual(state, {
    page: 1,
    q: '',
    sort: 'newest',
    tools: [],
    tags: [],
    rawQuery: ''
  });
});

test('buildGalleryUrl omits default state from the query string', () => {
  assert.equal(
    buildGalleryUrl({
      pathname: '/gallery/',
      page: 1,
      sort: 'newest',
      q: '',
      tools: [],
      tags: []
    }),
    '/gallery/'
  );
});

test('buildGalleryUrl encodes non-default gallery state', () => {
  assert.equal(
    buildGalleryUrl({
      pathname: '/gallery/',
      page: 2,
      sort: 'oldest',
      q: 'loan calc',
      tools: ['claude', 'chatgpt'],
      tags: ['finance']
    }),
    '/gallery/?page=2&tool=claude%2Cchatgpt&tag=finance&sort=oldest&q=loan+calc'
  );
});
