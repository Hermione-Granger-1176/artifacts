import assert from 'node:assert/strict';
import test from 'node:test';

import { buildDocument } from '../../../../apps/vendor-docs-generator/js/modules/document-model.js';
import {
  applyVendorTheme,
  buildLogo,
  renderPaper
} from '../../../../apps/vendor-docs-generator/js/modules/paper-render.js';
import { DOCUMENT_TYPES, VENDORS, findVendor } from '../../../../apps/vendor-docs-generator/js/modules/vendors.js';

import { createFakeDocument, createFakeElement, findByClass, findByTag, textOf } from './fake-dom.js';

const TODAY = new Date(2026, 5, 15);

/**
 * Render one document onto a fresh fake paper element.
 * @param {Record<string, any>} options - buildDocument options.
 * @returns {{ model: any, paper: any }} The model and the paper it rendered into.
 */
function render(options) {
  const doc = createFakeDocument();
  const paper = createFakeElement('article');
  const model = buildDocument({ today: TODAY, ...options });
  renderPaper(paper, model, doc);
  return { model, paper };
}

test('applyVendorTheme pushes brand values through CSSOM, never inline styles', () => {
  const element = createFakeElement('div');
  const vendor = findVendor('nimbus');
  applyVendorTheme(element, vendor);

  assert.equal(element.style.getPropertyValue('--vd-accent'), vendor.accent);
  assert.equal(element.style.getPropertyValue('--vd-accent-soft'), vendor.accentSoft);
  assert.equal(element.style.getPropertyValue('--vd-ink'), vendor.ink);
  assert.equal(element.style.getPropertyValue('--vd-font'), vendor.font);
});

test('every logo treatment builds a distinct, labelled lockup', () => {
  const doc = createFakeDocument();
  const seen = new Set();

  for (const vendor of VENDORS) {
    const logo = buildLogo(doc, vendor);
    assert.ok(logo.className.includes(`is-${vendor.logoStyle}`));
    assert.ok(logo.children.length >= 1, `${vendor.id} produced an empty logo`);
    assert.ok(textOf(logo).length > 0, `${vendor.id} produced a logo with no text`);
    seen.add(vendor.logoStyle);
  }

  assert.equal(seen.size, 6, 'all six treatments should be exercised');
});

test('the block and stamp treatments print a two-letter monogram', () => {
  const doc = createFakeDocument();

  for (const id of ['apex', 'ironwood']) {
    const logo = buildLogo(doc, findVendor(id));
    const [mark] = findByClass(logo, 'vd-logo-mark');
    assert.match(mark.textContent, /^[A-Z]{2}$/);
  }
});

test('the thin treatment splits the name into a lead word and a tail', () => {
  const logo = buildLogo(createFakeDocument(), findVendor('lumen'));
  assert.equal(findByClass(logo, 'vd-logo-name')[0].textContent, 'Lumen');
  assert.equal(findByClass(logo, 'vd-logo-sub')[0].textContent, 'Office Interiors');
});

test('the paper carries the letterhead, title, and sample footer', () => {
  const { model, paper } = render({ docTypeId: 'invoice', seed: 2024, vendorId: 'apex' });
  const [page] = findByClass(paper, 'vd-page');

  assert.ok(page.className.includes('is-left'), 'the page should carry the vendor layout class');
  assert.equal(findByClass(paper, 'vd-accent-bar').length, 1);
  assert.equal(findByClass(paper, 'vd-doc-title')[0].textContent, model.title);
  assert.match(findByClass(paper, 'vd-doc-foot')[0].textContent, /Not a valid tax record/);

  const vendorLines = findByClass(paper, 'vd-vendor-line').map((node) => node.textContent);
  assert.deepEqual(vendorLines, [
    model.vendor.addr,
    `${model.vendor.phone} · ${model.vendor.email}`,
    model.vendor.taxId
  ]);
});

test('rendering twice replaces the page rather than stacking pages', () => {
  const doc = createFakeDocument();
  const paper = createFakeElement('article');
  renderPaper(paper, buildDocument({ docTypeId: 'invoice', seed: 1, today: TODAY, vendorId: 'apex' }), doc);
  renderPaper(paper, buildDocument({ docTypeId: 'receipt', seed: 2, today: TODAY, vendorId: 'verde' }), doc);

  assert.equal(findByClass(paper, 'vd-page').length, 1);
  assert.equal(findByClass(paper, 'vd-doc-title')[0].textContent, 'Receipt');
});

test('the subtitle is omitted when a document type has none', () => {
  const { paper } = render({ docTypeId: 'invoice', seed: 3, vendorId: 'apex' });
  assert.equal(findByClass(paper, 'vd-doc-subtitle').length, 0);

  const { paper: quotation } = render({ docTypeId: 'quotation', seed: 3, vendorId: 'apex' });
  assert.equal(
    findByClass(quotation, 'vd-doc-subtitle')[0].textContent,
    'THIS IS NOT A TAX INVOICE'
  );
});

test('item tables carry a header, one row per line, and per-column alignment', () => {
  const { model, paper } = render({ docTypeId: 'invoice', seed: 4242, vendorId: 'lumen' });
  const [table] = findByClass(paper, 'vd-items');
  const [head, body] = table.children;
  const tableBlock = model.blocks.find((block) => block.kind === 'table');

  assert.equal(head.children[0].children.length, tableBlock.columns.length);
  assert.equal(body.children.length, tableBlock.rows.length);

  const alignments = head.children[0].children.map((cell) => cell.className);
  assert.deepEqual(
    alignments,
    tableBlock.columns.map((column) => `is-${column.align}`)
  );
});

test('the dense invoice renders its grid, party pair, and table footer', () => {
  const { paper } = render({
    docTypeId: 'invoice',
    seed: 5150,
    style: 'dense',
    vendorId: 'nimbus'
  });

  assert.ok(findByClass(paper, 'vd-page')[0].className.includes('is-dense'));
  assert.equal(findByClass(paper, 'vd-keygrid').length, 1);
  assert.equal(findByClass(paper, 'vd-kv').length, 2, 'the key grid should hold two tables');
  assert.equal(findByClass(paper, 'vd-partypair').length, 1);
  assert.equal(findByClass(paper, 'vd-partypair-head').length, 2);
  assert.ok(findByClass(paper, 'vd-items')[0].className.includes('is-dense'));
  assert.equal(findByTag(paper, 'tfoot').length, 1);
  assert.equal(findByClass(paper, 'vd-words').length, 1);
  assert.equal(findByClass(paper, 'vd-signoff').length, 1);
});

test('the totals block emphasises exactly the row the model marks', () => {
  const { model, paper } = render({ docTypeId: 'invoice', seed: 909, vendorId: 'harbor' });
  const totalsBlock = model.blocks.find((block) => block.kind === 'totals');
  const rows = findByClass(paper, 'vd-totals')[0].children[0].children;
  const emphasised = rows.map((row) => row.className === 'is-emphasis');

  assert.deepEqual(
    emphasised,
    totalsBlock.rows.map((_row, index) => index === totalsBlock.emphasisIndex)
  );
});

test('the receipt renders its stamp and the challan its signature lines', () => {
  const { paper: receipt } = render({ docTypeId: 'receipt', seed: 606, vendorId: 'lumen' });
  assert.equal(findByClass(receipt, 'vd-stamp')[0].textContent, 'PAID');

  const { paper: challan } = render({ docTypeId: 'challan', seed: 909, vendorId: 'harbor' });
  assert.equal(findByClass(challan, 'vd-signature').length, 2);
  assert.equal(findByClass(challan, 'vd-doc-chip').length, 2);
});

test('the credit note renders a callout and the statement a balance banner', () => {
  const { paper: credit } = render({ docTypeId: 'creditnote', seed: 100, vendorId: 'apex' });
  assert.match(findByClass(credit, 'vd-doc-callout')[0].textContent, /credit note/);

  const { paper: statement } = render({ docTypeId: 'statement', seed: 1357, vendorId: 'verde' });
  assert.equal(findByClass(statement, 'vd-banner-label')[0].textContent, 'Balance due');
  assert.match(findByClass(statement, 'vd-banner-value')[0].textContent, /^\$/);
});

test('notes render with the tone the model asked for', () => {
  const { paper: invoice } = render({ docTypeId: 'invoice', seed: 7, vendorId: 'apex' });
  assert.ok(findByClass(invoice, 'vd-note')[0].className.includes('is-accent'));

  const { paper: receipt } = render({ docTypeId: 'receipt', seed: 7, vendorId: 'apex' });
  assert.ok(findByClass(receipt, 'vd-note')[0].className.includes('is-plain'));
});

test('the centre and right layouts reach the page as layout classes', () => {
  const { paper: centred } = render({ docTypeId: 'invoice', seed: 8, vendorId: 'verde' });
  assert.ok(findByClass(centred, 'vd-page')[0].className.includes('is-center'));

  const { paper: right } = render({ docTypeId: 'invoice', seed: 8, vendorId: 'nimbus' });
  assert.ok(findByClass(right, 'vd-page')[0].className.includes('is-right'));
});

test('every vendor and type combination renders without throwing', () => {
  for (const vendor of VENDORS) {
    for (const type of DOCUMENT_TYPES) {
      const { paper } = render({ docTypeId: type.id, seed: 4321, vendorId: vendor.id });
      assert.ok(
        textOf(paper).length > 200,
        `${vendor.id}/${type.id} rendered suspiciously little text`
      );
    }
  }
});
