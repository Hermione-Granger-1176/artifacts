import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildFilterPanelHtml,
  buildGridHtml,
  createDetailContent,
  escapeHtml,
  getFilterSummary,
  renderPagination,
  updateFilterDropdownUI
} from '../../js/modules/render.js';

function createOptionStub() {
  return {
    attributes: {},
    classList: {
      state: {},
      toggle(name, value) {
        this.state[name] = value;
      }
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
    }
  };
}

function createCheckboxStub(value) {
  const option = createOptionStub();

  return {
    value,
    checked: false,
    closest(selector) {
      assert.equal(selector, '.filter-dropdown-item');
      return option;
    },
    option
  };
}

test('escapeHtml escapes reserved HTML characters', () => {
  assert.equal(escapeHtml('<script src="x">&"\''), '&lt;script src=&quot;x&quot;&gt;&amp;&quot;&#039;');
  assert.equal(escapeHtml(''), '');
});

test('buildFilterPanelHtml escapes values and labels', () => {
  const html = buildFilterPanelHtml({
    key: 'tool',
    values: ['claude<script>'],
    labelFormatter: (value) => `Tool: ${value}`
  });

  assert.match(html, /value="claude&lt;script&gt;"/);
  assert.match(html, /Tool: claude&lt;script&gt;/);
  assert.match(html, /data-filter-group="tool"/);
});

test('getFilterSummary returns empty, single, and plural labels', () => {
  const control = {
    emptyLabel: 'All tools',
    pluralLabel: 'tools',
    labelFormatter: (value) => value.toUpperCase()
  };

  assert.equal(getFilterSummary([], control), 'All tools');
  assert.equal(getFilterSummary(['claude'], control), 'CLAUDE');
  assert.equal(getFilterSummary(['claude', 'chatgpt'], control), '2 tools');
});

test('updateFilterDropdownUI syncs checkbox state and selected styles', () => {
  const firstCheckbox = createCheckboxStub('claude');
  const secondCheckbox = createCheckboxStub('chatgpt');
  const control = {
    emptyLabel: 'All tools',
    pluralLabel: 'tools',
    labelFormatter: (value) => value.toUpperCase(),
    label: { textContent: '' },
    panel: {
      querySelectorAll(selector) {
        assert.equal(selector, '.filter-dropdown-checkbox');
        return [firstCheckbox, secondCheckbox];
      }
    }
  };

  updateFilterDropdownUI(control, ['chatgpt']);

  assert.equal(control.label.textContent, 'CHATGPT');
  assert.equal(firstCheckbox.checked, false);
  assert.equal(secondCheckbox.checked, true);
  assert.equal(firstCheckbox.option.attributes['aria-selected'], 'false');
  assert.equal(secondCheckbox.option.attributes['aria-selected'], 'true');
  assert.equal(firstCheckbox.option.classList.state['is-selected'], false);
  assert.equal(secondCheckbox.option.classList.state['is-selected'], true);
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
  assert.match(html, /Open the artifact to explore the interactive experience\./);
  assert.match(html, /href="apps\/artifact-1\/\?x=&lt;tag&gt;"/);
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
