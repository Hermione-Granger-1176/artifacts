import test from 'node:test';
import assert from 'node:assert/strict';

import {
  applyDynamicStyles,
  buildFilterNotes,
  buildGridHtml,
  createDetailContent,
  escapeHtml,
  renderPagination
} from '../../../js/modules/gallery/render.js';

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

  assert.match(html, /<button class="artifact-card/);
  assert.match(html, /data-id="artifact-1"/);
  assert.match(html, /loading="lazy"/);
  assert.match(html, /data-id="artifact-2"[^]*aria-expanded="true"/);
  assert.match(html, /card-thumbnail-placeholder/);
  assert.match(html, /type="button"/);
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
  assert.match(html, /data-filter-note="all-tools"[^>]*aria-pressed="true"/);
  assert.match(html, /data-filter-tool="claude"/);
  assert.match(html, /data-filter-tool="chatgpt"/);
  assert.match(html, /data-filter-tag="game"/);
  assert.match(html, /data-filter-tool="claude"[^>]*aria-controls="artifacts-grid"/);
  assert.match(html, />CLAUDE</);
  assert.match(html, />CHATGPT</);
  assert.match(html, />#game</);
  assert.match(html, /class="mobile-filter-chip is-active"[^>]*data-filter-note="all-tools"/);
  assert.match(html, /class="mobile-filter-chip is-active"[^>]*data-filter-note="all-tags"/);
  assert.match(html, /mobile-filter-heading">Tools</);
  assert.match(html, /mobile-filter-summary"[^>]*>All tools</);
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
  assert.match(html, /mobile-filter-summary"[^>]*>1 active</);
  assert.match(html, /class="mobile-filter-chip is-active"[^>]*data-filter-tool="claude"/);
  assert.match(html, /class="mobile-filter-chip is-active"[^>]*data-filter-tag="finance"/);
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

test('applyDynamicStyles sets CSS custom properties from data attributes', () => {
  function fakeElement(dataset) {
    const props = {};
    return {
      dataset,
      style: {
        setProperty(name, value) { props[name] = value; },
        _props: props
      }
    };
  }

  const chipEl = fakeElement({ chipColor: 'rgb(1,2,3)', rotate: '5' });
  const capsuleEl = fakeElement({ capsuleBg: 'rgb(4,5,6)' });
  const cardEl = fakeElement({ cardColor: 'var(--c)', noteRotate: '-1deg', noteHoverRotate: '0.5deg' });

  const container = {
    querySelectorAll(selector) {
      if (selector === '[data-chip-color]') return [chipEl];
      if (selector === '[data-capsule-bg]') return [capsuleEl];
      if (selector === '[data-card-color]') return [cardEl];
      return [];
    }
  };

  applyDynamicStyles(container);

  assert.equal(chipEl.style._props['--chip-color'], 'rgb(1,2,3)');
  assert.equal(chipEl.style._props['--note-color'], 'rgb(1,2,3)');
  assert.equal(chipEl.style._props['--rotate'], '5deg');
  assert.equal(capsuleEl.style._props['--capsule-bg'], 'rgb(4,5,6)');
  assert.equal(cardEl.style._props['--card-bg-color'], 'var(--c)');
  assert.equal(cardEl.style._props['--note-rotate'], '-1deg');
  assert.equal(cardEl.style._props['--note-hover-rotate'], '0.5deg');
});

test('applyDynamicStyles skips rotate when data-rotate is absent', () => {
  const props = {};
  const el = {
    dataset: { chipColor: 'red' },
    style: { setProperty(name, value) { props[name] = value; } }
  };

  applyDynamicStyles({
    querySelectorAll(selector) {
      return selector === '[data-chip-color]' ? [el] : [];
    }
  });

  assert.equal(props['--chip-color'], 'red');
  assert.equal(props['--rotate'], undefined);
});
