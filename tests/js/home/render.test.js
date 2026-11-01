import test from 'node:test';
import assert from 'node:assert/strict';

import {
  applyDynamicStyles,
  buildFilterDropdowns,
  buildFilterNotes,
  buildGridHtml,
  createDetailContent,
  escapeHtml,
  handleThumbnailError,
  registerThumbnailFallback,
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

const SLOT_PATTERN = /class="page-(?:btn|ellipsis)[ "]/g;

test('renderPagination keeps a disabled row for one page or none, as wide as a two-page row', () => {
  const twoPages = { innerHTML: '', dataset: {} };
  renderPagination(twoPages, 1, 2);

  for (const total of [1, 0]) {
    const container = { innerHTML: 'stale', dataset: { renderKey: '1/2' } };
    renderPagination(container, 1, total);
    assert.equal(container.dataset.renderKey, '1/1', `${total} pages render as one`);
    assert.equal(container.innerHTML.match(/<button/g).length, 5, 'four nav buttons and the one page');
    assert.equal(container.innerHTML.match(/type="button" disabled/g).length, 4, 'every nav button is disabled');
    assert.match(container.innerHTML, /aria-current="page"/);
    assert.match(container.innerHTML, /<span class="page-ellipsis page-slot-empty" aria-hidden="true"><\/span>/);
    assert.equal(
      container.innerHTML.match(SLOT_PATTERN).length,
      twoPages.innerHTML.match(SLOT_PATTERN).length,
      'same number of slots as two pages'
    );
  }
});

test('renderPagination keeps the same number of slots on every page of a long range', () => {
  const container = { innerHTML: '', dataset: {} };
  const slotCounts = new Set();
  for (let page = 1; page <= 12; page += 1) {
    renderPagination(container, page, 12);
    slotCounts.add(container.innerHTML.match(SLOT_PATTERN).length);
  }
  assert.deepEqual([...slotCounts], [7 + 4]);
});

test('renderPagination renders ellipsis for long ranges', () => {
  const container = { innerHTML: '', dataset: {} };
  renderPagination(container, 5, 10);
  assert.match(container.innerHTML, /aria-label="First page"/);
  assert.match(container.innerHTML, /page-ellipsis/);
  assert.match(container.innerHTML, /aria-current="page"/);
  assert.match(container.innerHTML, /aria-label="Last page"/);
});

test('renderPagination gives Previous and Next relative steps and labels', () => {
  const container = { innerHTML: '', dataset: {} };
  renderPagination(container, 3, 5);

  assert.match(container.innerHTML, /data-page="2" data-page-step="-1"[^>]*aria-label="Prev page"/);
  assert.match(container.innerHTML, /data-page="4" data-page-step="1"[^>]*aria-label="Next page"/);
  assert.match(container.innerHTML, /page-btn-label">Prev</);
  assert.match(container.innerHTML, /page-btn-label">Next</);
  assert.doesNotMatch(container.innerHTML, /data-page="1" data-page-step/);
});

test('renderPagination disables nav buttons at the ends', () => {
  const container = { innerHTML: '', dataset: {} };
  renderPagination(container, 1, 3);
  assert.match(container.innerHTML, /data-page="0" data-page-step="-1" type="button" disabled/);

  renderPagination(container, 3, 3);
  assert.match(container.innerHTML, /data-page="4" data-page-step="1" type="button" disabled/);
});

test('renderPagination skips the DOM write when the page and total are unchanged', () => {
  const container = { innerHTML: '', dataset: {} };
  renderPagination(container, 2, 4);
  container.innerHTML = 'marker';
  renderPagination(container, 2, 4);
  assert.equal(container.innerHTML, 'marker');

  renderPagination(container, 3, 4);
  assert.notEqual(container.innerHTML, 'marker');
  assert.equal(container.dataset.renderKey, '3/4');
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
  assert.doesNotMatch(html, /filter-dropdown|filter-panel/, 'the dropdowns render separately');
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

/** @param {number} count - How many tag values the group has. */
const tagGroup = (count, activeValues = []) => ({
  kind: 'tags',
  heading: 'Tags',
  noteValue: 'all-tags',
  values: Array.from({ length: count }, (_, index) => `tag-${index}`),
  activeValues,
  datasetName: 'data-filter-tag',
  labelFor: (value) => value.toUpperCase(),
  countFor: (value) => Number(value.split('-')[1]) + 1
});

test('buildFilterDropdowns renders a button and a checklist panel per group, in order', () => {
  const html = buildFilterDropdowns([
    tagGroup(2, ['tag-1']),
    { ...tagGroup(1), kind: 'tools', heading: 'Tools', noteValue: 'all-tools', datasetName: 'data-filter-tool' }
  ]);

  assert.ok(html.indexOf('data-filter-open="tags"') < html.indexOf('data-filter-open="tools"'));
  assert.match(html, /class="filter-dropdown-toggle" type="button" data-filter-open="tags" aria-haspopup="dialog" aria-controls="filter-panel-tags" aria-expanded="false" aria-label="Tags">/);
  assert.match(html, /data-filter-summary="tags" aria-hidden="true">1</);
  assert.match(html, /data-filter-summary="tools" aria-hidden="true"></, 'no picks shows no count');
  assert.match(html, /<dialog id="filter-panel-tags" class="filter-panel" aria-labelledby="filter-panel-tags-title">/);
  assert.match(html, /class="filter-option"[^>]*data-filter-surface="mobile" data-filter-tag="tag-0"[^>]*aria-pressed="false"><span class="filter-option-label">TAG-0<\/span><span class="filter-option-count" aria-hidden="true">1</);
  assert.match(html, /class="filter-option is-active"[^>]*data-filter-tag="tag-1"[^>]*aria-pressed="true"/);
  assert.match(html, /class="btn-reset-link filter-panel-clear"[^>]*data-filter-note="all-tags" data-filter-surface="mobile"/);
  assert.match(html, /class="btn-icon filter-panel-close"[^>]*data-close-filter-panel aria-label="Close tags"/);
  assert.match(html, /class="filter-panel-done"[^>]*data-close-filter-panel/);
});

test('buildFilterDropdowns adds a search box only to a long list', () => {
  assert.doesNotMatch(buildFilterDropdowns([tagGroup(8)]), /data-filter-panel-search/);
  assert.match(buildFilterDropdowns([tagGroup(9)]), /<input class="filter-panel-search" type="search" placeholder="Find tags\.\.\." aria-label="Find tags"/);
  assert.equal(buildFilterDropdowns([]), '');
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

function createdPlaceholder() {
  return { tagName: 'DIV', className: '' };
}

function fakeFrame({ withParent = true } = {}) {
  const created = createdPlaceholder();
  const ownerDocument = {
    createElement(tag) {
      created.tagName = tag.toUpperCase();
      return created;
    }
  };
  const parent = withParent
    ? {
        replaced: null,
        removed: null,
        replaceChild(next, old) {
          this.replaced = next;
          this.removed = old;
        }
      }
    : null;
  const frame = { ownerDocument, parentNode: parent, className: 'card-photo-frame' };
  return { frame, parent, created };
}

function fakeImage(frameResult, { className = 'card-thumbnail', tagName = 'IMG' } = {}) {
  return {
    tagName,
    classList: { contains: (name) => className.split(' ').includes(name) },
    closest: (selector) => (selector === '.card-photo-frame' ? frameResult : null)
  };
}

test('handleThumbnailError swaps a broken card thumbnail for the placeholder', () => {
  const { frame, parent, created } = fakeFrame();
  const img = fakeImage(frame);

  handleThumbnailError({ target: img });

  assert.equal(created.className, 'card-thumbnail-placeholder');
  assert.equal(parent.replaced, created);
  assert.equal(parent.removed, frame);
});

test('handleThumbnailError ignores non-image targets', () => {
  const { frame, parent } = fakeFrame();
  handleThumbnailError({ target: { tagName: 'DIV', classList: { contains: () => true }, closest: () => frame } });
  assert.equal(parent.replaced, null);
});

test('handleThumbnailError ignores images without the card-thumbnail class', () => {
  const { frame, parent } = fakeFrame();
  const img = fakeImage(frame, { className: 'detail-media' });
  handleThumbnailError({ target: img });
  assert.equal(parent.replaced, null);
});

test('handleThumbnailError ignores a null target', () => {
  assert.doesNotThrow(() => handleThumbnailError({ target: null }));
});

test('handleThumbnailError is a no-op when no photo frame is found', () => {
  const img = fakeImage(null);
  assert.doesNotThrow(() => handleThumbnailError({ target: img }));
});

test('handleThumbnailError is a no-op when the frame has no parent', () => {
  const { frame } = fakeFrame({ withParent: false });
  const img = fakeImage(frame);
  assert.doesNotThrow(() => handleThumbnailError({ target: img }));
});

test('registerThumbnailFallback binds a capture-phase error listener', () => {
  const calls = [];
  const grid = {
    addEventListener(type, handler, capture) {
      calls.push({ type, handler, capture });
    }
  };

  registerThumbnailFallback(grid);

  assert.equal(calls.length, 1);
  assert.equal(calls[0].type, 'error');
  assert.equal(calls[0].handler, handleThumbnailError);
  assert.equal(calls[0].capture, true);
});

test('buildGridHtml keeps the happy-path thumbnail image untouched', () => {
  const html = buildGridHtml([{ id: 'a', name: 'A', thumbnail: 'thumb.webp' }], null);
  assert.match(html, /card-photo-frame/);
  assert.match(html, /<img class="card-thumbnail" src="thumb\.webp"[^>]*loading="lazy">/);
  assert.doesNotMatch(html, /onerror/);
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

test('buildGridHtml deals cards onto left and right pages with printed page numbers', () => {
  const items = ['a', 'b', 'c', 'd'].map((id) => ({ id, name: id.toUpperCase(), thumbnail: null }));
  const html = buildGridHtml(items, null, 3);

  const left = html.slice(html.indexOf('artifact-page-left'), html.indexOf('artifact-page-right'));
  const right = html.slice(html.indexOf('artifact-page-right'));
  assert.match(left, /data-id="a"[^]*data-id="c"/);
  assert.doesNotMatch(left, /data-id="b"/);
  assert.match(right, /data-id="b"[^]*data-id="d"/);
  assert.match(left, /<span class="page-number" aria-hidden="true">5<\/span>/);
  assert.match(right, /<span class="page-number" aria-hidden="true">6<\/span>/);
  assert.doesNotMatch(html, /is-empty/);
});

test('buildGridHtml numbers pages from one by default and marks an empty page', () => {
  const html = buildGridHtml([{ id: 'only', name: 'Only', thumbnail: null }], null);

  assert.match(html, /artifact-page-left"[^>]*aria-label="Left book page"/);
  assert.match(html, /artifact-page-right is-empty"[^>]*aria-label="Right book page"/);
  assert.match(html, /page-number" aria-hidden="true">1</);
  assert.match(html, /page-number" aria-hidden="true">2</);
});

test('buildGridHtml picks a stable attachment style and tape colour from the card id', () => {
  const item = { id: 'loan-amortization', name: 'Loan', thumbnail: null };
  const first = buildGridHtml([item], null);
  const again = buildGridHtml([item, { id: 'other', name: 'Other', thumbnail: null }], null, 2);

  const attachOf = (html, id) => html.match(new RegExp(`data-id="${id}"[^>]*data-attach="([a-z-]+)" data-tape="(\\d)"`));
  const a = attachOf(first, 'loan-amortization');
  const b = attachOf(again, 'loan-amortization');
  assert.ok(a);
  assert.deepEqual(a.slice(1), b.slice(1));
  assert.ok(['tape-pair', 'tape-center', 'corners', 'clip', 'tape-diagonal'].includes(a[1]));
  assert.ok(Number(a[2]) >= 1 && Number(a[2]) <= 6);
});

test('buildGridHtml spreads attachment styles across ids', () => {
  const items = Array.from({ length: 40 }, (_, index) => ({ id: `artifact-${index}`, name: `A${index}`, thumbnail: null }));
  const html = buildGridHtml(items, null);
  const styles = new Set([...html.matchAll(/data-attach="([a-z-]+)"/g)].map((match) => match[1]));
  const tapes = new Set([...html.matchAll(/data-tape="(\d)"/g)].map((match) => match[1]));

  assert.equal(styles.size, 5);
  assert.equal(tapes.size, 6);
});
