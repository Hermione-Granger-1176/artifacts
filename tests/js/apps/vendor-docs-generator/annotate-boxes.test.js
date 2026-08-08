import assert from 'node:assert/strict';
import test from 'node:test';

import {
  BOXES_APPLY_TO,
  collectBoxes
} from '../../../../apps/vendor-docs-generator/js/modules/annotate-boxes.js';
import { buildDocument } from '../../../../apps/vendor-docs-generator/js/modules/document-model.js';
import { renderPaper } from '../../../../apps/vendor-docs-generator/js/modules/paper-render.js';
import {
  DOCUMENT_TYPES,
  VENDORS
} from '../../../../apps/vendor-docs-generator/js/modules/vendors.js';

import { createFakeDocument, createFakeElement, findTagged, layOut } from './fake-dom.js';

const TODAY = new Date(2026, 5, 15);

/**
 * Render a document onto a measured page.
 * @param {Record<string, any>} [overrides={}] - buildDocument overrides.
 * @returns {{ doc: Record<string, any>, model: any, paper: Record<string, any> }} Page and model.
 */
function render(overrides = {}) {
  const doc = createFakeDocument();
  const paper = createFakeElement('article');
  const model = buildDocument({
    docTypeId: 'invoice',
    seed: 4_242,
    today: TODAY,
    vendorId: 'apex',
    ...overrides
  });

  renderPaper(paper, model, doc);
  layOut(paper);
  return { doc, model, paper };
}

test('every labelled node on the page becomes exactly one region', () => {
  const { doc, paper } = render();
  const tagged = findTagged(paper);
  const { regions } = collectBoxes(paper, { doc });

  assert.equal(regions.length, tagged.length);
  assert.deepEqual(
    regions.map((region) => region.field),
    tagged.map((node) => node.getAttribute('data-field')),
    'regions come back in document order'
  );
  assert.deepEqual(
    regions.map((region) => region.text),
    tagged.map((node) => node.textContent.trim())
  );
});

test('boxes are normalised into the page, not reported in pixels', () => {
  const { doc, paper } = render();
  const { page, regions } = collectBoxes(paper, { doc });

  assert.deepEqual(page, { width: 794, height: 1123, unit: 'normalised' });

  for (const region of regions) {
    const [x, y, width, height] = region.box;
    assert.ok(x >= 0 && x <= 1, `${region.field} x out of range: ${x}`);
    assert.ok(y >= 0 && y <= 1, `${region.field} y out of range: ${y}`);
    assert.ok(width > 0 && width <= 1, `${region.field} width out of range: ${width}`);
    assert.ok(height > 0 && height <= 1, `${region.field} height out of range: ${height}`);
    assert.ok(x + width <= 1.0001, `${region.field} runs off the right edge`);
  }
});

test('a preview scaled by a CSS transform reports the same boxes', () => {
  // Normalising against the page's own rect is what makes this true: both the
  // element rect and the page rect scale together, so the ratio does not move.
  // Without it every box would be wrong at any zoom other than 100%.
  const { doc, paper } = render();
  const full = collectBoxes(paper, { doc });

  const scale = 0.593;
  /**
   * @param {Record<string, any>} node - Node to shrink.
   * @returns {void}
   */
  const shrink = (node) => {
    node.rect = {
      left: node.rect.left * scale,
      top: node.rect.top * scale,
      right: node.rect.right * scale,
      bottom: node.rect.bottom * scale,
      width: node.rect.width * scale,
      height: node.rect.height * scale
    };
    node.children.forEach(shrink);
  };
  shrink(paper);

  const scaled = collectBoxes(paper, { doc });
  assert.deepEqual(scaled.regions.map((region) => region.box), full.regions.map((region) => region.box));
  assert.deepEqual(scaled.page, full.page, 'and the page still reports its layout size');
});

test('a field printed in two places produces two regions', () => {
  const { doc, paper } = render();
  const { regions } = collectBoxes(paper, { doc });
  const addresses = regions.filter((region) => region.field === 'buyer_address');

  assert.equal(addresses.length, 2, 'a two-line address occupies two boxes');
  assert.notDeepEqual(addresses[0].box, addresses[1].box);
  assert.ok(addresses[1].box[1] > addresses[0].box[1], 'the second line sits below the first');
});

test('row-scoped fields are addressed by index', () => {
  const { doc, model, paper } = render({ style: 'dense' });
  const { regions } = collectBoxes(paper, { doc });
  const amounts = regions.filter((region) => /^line_items\.\d+\.amount$/.test(region.field));

  assert.equal(amounts.length, model.facts.items.length);
  assert.deepEqual(
    amounts.map((region) => region.field),
    model.facts.items.map((_item, index) => `line_items.${index}.amount`)
  );

  const ledger = collectBoxes(render({ docTypeId: 'statement' }).paper, { doc }).regions;
  assert.ok(ledger.some((region) => region.field === 'transactions.0.balance'));
});

test('blank ledger cells are not labelled, because the sidecar calls them null', () => {
  const { doc, paper } = render({ docTypeId: 'statement' });
  const { regions } = collectBoxes(paper, { doc });

  assert.equal(
    regions.filter((region) => region.text === '').length,
    0,
    'an empty charges cell should carry no region at all'
  );
  // The brought-forward row has neither a charge nor a payment, so those two
  // cells must be missing from the regions rather than present and empty.
  assert.ok(!regions.some((region) => region.field === 'transactions.0.charge'));
  assert.ok(regions.some((region) => region.field === 'transactions.1.balance'));
});

test('word boxes are off by default and land inside their region when on', () => {
  const { doc, paper } = render();
  const plain = collectBoxes(paper, { doc });
  assert.ok(plain.regions.every((region) => region.words === undefined));

  const detailed = collectBoxes(paper, { doc, words: true });
  const multiWord = detailed.regions.find((region) => region.text.split(' ').length > 2);
  assert.ok(multiWord, 'the page should contain at least one multi-word value');
  assert.equal(multiWord.words.length, multiWord.text.split(/\s+/).length);
  assert.deepEqual(
    multiWord.words.map((word) => word.text),
    multiWord.text.split(/\s+/)
  );

  const [regionX, regionY, regionWidth] = multiWord.box;

  for (const word of multiWord.words) {
    const [x, y, width] = word.box;
    assert.ok(x >= regionX - 0.0001, `${word.text} starts left of its region`);
    assert.ok(x + width <= regionX + regionWidth + 0.0001, `${word.text} runs past its region`);
    assert.equal(y, regionY, 'words share the baseline of the line they are on');
  }
});

test('a page with no measurable size yields finite coordinates', () => {
  const doc = createFakeDocument();
  const paper = createFakeElement('article');
  renderPaper(paper, buildDocument({ docTypeId: 'invoice', seed: 7, today: TODAY, vendorId: 'apex' }), doc);

  // Never laid out, so every rect is zero. Dividing by the page would produce
  // NaN and Infinity throughout the payload rather than an obvious zero.
  const { page, regions } = collectBoxes(paper, { doc });

  assert.equal(page.width, 0);
  assert.ok(regions.length > 0);
  assert.ok(regions.every((region) => region.box.every(Number.isFinite)));
});

test('a node carrying an empty data-field is skipped rather than emitted', () => {
  const { doc, paper } = render();
  const stray = createFakeElement('div');
  stray.setAttribute('data-field', '');
  paper.appendChild(stray);

  const { regions } = collectBoxes(paper, { doc });
  assert.ok(regions.every((region) => region.field !== ''));
});

test('word measurement copes with a node whose range reports nothing', () => {
  const doc = createFakeDocument();
  const paper = createFakeElement('article');
  const child = createFakeElement('div');
  // No text, so there is no text node to range over and no rect to report.
  child.setAttribute('data-field', 'grand_total');
  paper.appendChild(child);
  layOut(paper);

  const { regions } = collectBoxes(paper, { doc, words: true });
  assert.deepEqual(regions[0].words, []);
});

test('every vendor and document type produces measurable regions', () => {
  for (const vendor of VENDORS) {
    for (const type of DOCUMENT_TYPES) {
      const { doc, paper } = render({ docTypeId: type.id, vendorId: vendor.id });
      const { regions } = collectBoxes(paper, { doc });
      const where = `${vendor.id}/${type.id}`;

      assert.ok(regions.length > 10, `${where} produced only ${regions.length} regions`);
      assert.ok(
        regions.some((region) => region.field === 'document_number'),
        `${where} should locate its own document number`
      );
      assert.ok(regions.some((region) => region.field === 'vendor_name'), `${where} vendor name`);
    }
  }
});

test('the applicability of DOM-measured boxes is a published constant', () => {
  assert.deepEqual(BOXES_APPLY_TO, ['png', 'pdf_raster']);
});
