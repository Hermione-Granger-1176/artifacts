import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildFilterNotes,
  buildGridHtml,
  createDetailContent,
  escapeHtml,
  renderPagination
} from '../../js/modules/render.js';

test('escapeHtml escapes reserved HTML characters', () => {
  assert.equal(escapeHtml('<script src="x">&"\''), '&lt;script src=&quot;x&quot;&gt;&amp;&quot;&#039;');
  assert.equal(escapeHtml(''), '');
});

test('createDetailContent renders fallback and escaped values', () => {
  const html = createDetailContent({
    name: 'Artifact <One>',
    description: '',
    thumbnail: null,
    url: 'apps/artifact-1/?x=<tag>'
  });

  assert.match(html, /detail-media-placeholder/);
  assert.match(html, /Artifact &lt;One&gt;/);
  assert.match(html, /id="detail-description"/);
  assert.match(html, /Open the artifact to explore the interactive experience\./);
  assert.match(html, /href="apps\/artifact-1\/\?x=&lt;tag&gt;"/);
  assert.match(html, /aria-label="Open artifact in a new tab"/);
});

test('buildGridHtml marks the expanded card and lazy-loads thumbnails', () => {
  const html = buildGridHtml(
    [
      {
        id: 'artifact-1',
        name: 'Artifact One',
        thumbnail: 'thumb.webp'
      },
      {
        id: 'artifact-2',
        name: 'Artifact Two',
        thumbnail: null
      }
    ],
    'artifact-2'
  );

  assert.match(html, /data-id="artifact-1"/);
  assert.match(html, /loading="lazy"/);
  assert.match(html, /data-id="artifact-2"[^]*aria-expanded="true"/);
  assert.match(html, /card-thumbnail-placeholder/);
});

test('renderPagination clears single-page output and renders ellipsis for long ranges', () => {
  const container = { innerHTML: 'stale' };
  renderPagination(container, 1, 1);
  assert.equal(container.innerHTML, '');

  renderPagination(container, 5, 10);
  assert.match(container.innerHTML, /aria-label="First page"/);
  assert.match(container.innerHTML, /page-ellipsis/);
  assert.match(container.innerHTML, /aria-current="page"/);
  assert.match(container.innerHTML, /aria-label="Last page"/);
});

test('buildFilterNotes marks All as active when no filters are selected', () => {
  const html = buildFilterNotes({
    tools: ['claude', 'chatgpt'],
    tags: ['game'],
    activeTools: [],
    activeTags: [],
    toolLabel: (v) => v.toUpperCase(),
    tagLabel: (v) => `#${v}`
  });

  assert.match(html, /class="desk-note is-active"[^>]*data-filter-note="all-tools"/);
  assert.match(html, /data-filter-tool="claude"/);
  assert.match(html, /data-filter-tool="chatgpt"/);
  assert.match(html, /data-filter-tag="game"/);
  assert.match(html, />CLAUDE</);
  assert.match(html, />CHATGPT</);
  assert.match(html, />#game</);
});

test('buildFilterNotes marks active tools and tags and deactivates All', () => {
  const html = buildFilterNotes({
    tools: ['claude', 'chatgpt'],
    tags: ['game', 'finance'],
    activeTools: ['claude'],
    activeTags: ['finance'],
    toolLabel: (v) => v,
    tagLabel: (v) => v
  });

  assert.doesNotMatch(html, /desk-note is-active"[^>]*data-filter-note="all-tools"/);
  assert.match(html, /desk-note is-active"[^>]*data-filter-tool="claude"/);
  assert.doesNotMatch(html, /desk-note is-active"[^>]*data-filter-tool="chatgpt"/);
  assert.doesNotMatch(html, /desk-note is-active"[^>]*data-filter-tag="game"/);
  assert.match(html, /desk-note is-active"[^>]*data-filter-tag="finance"/);
});

test('buildFilterNotes escapes HTML in labels', () => {
  const html = buildFilterNotes({
    tools: ['<xss>'],
    tags: [],
    activeTools: [],
    activeTags: [],
    toolLabel: (v) => v,
    tagLabel: (v) => v
  });

  assert.match(html, /data-filter-tool="&lt;xss&gt;"/);
  assert.match(html, />&lt;xss&gt;</);
  assert.doesNotMatch(html, /<xss>/);
});
