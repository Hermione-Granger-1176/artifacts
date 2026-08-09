import assert from 'node:assert/strict';
import test from 'node:test';

import {
  FIELD_KEYS,
  LINE_ITEM_KEYS,
  SCHEMA_VERSION,
  TRANSACTION_KEYS,
  annotationsToJson,
  annotationsToJsonl,
  buildAnnotations,
  datasetReadme
} from '../../../../apps/vendor-docs-generator/js/modules/annotations.js';
import {
  planDegradation,
  resolveSettings
} from '../../../../apps/vendor-docs-generator/js/modules/degrade.js';
import { buildDocument } from '../../../../apps/vendor-docs-generator/js/modules/document-model.js';
import { renderPaper } from '../../../../apps/vendor-docs-generator/js/modules/paper-render.js';
import {
  DOCUMENT_TYPES,
  VENDORS
} from '../../../../apps/vendor-docs-generator/js/modules/vendors.js';

import { createFakeDocument, createFakeElement, findTagged } from './fake-dom.js';

const TODAY = new Date(2026, 5, 15);
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Build the sidecar for one selection.
 * @param {Record<string, any>} [overrides={}] - buildDocument overrides.
 * @returns {Record<string, any>} The sidecar payload.
 */
function annotate(overrides = {}) {
  return buildAnnotations(
    buildDocument({ docTypeId: 'invoice', seed: 4242, today: TODAY, vendorId: 'apex', ...overrides })
  );
}

/**
 * Every vendor by every type by both invoice treatments, over a spread of seeds.
 * @param {number} [seedCount=4] - Seeds per combination.
 * @returns {Record<string, any>[]} One selection per combination.
 */
function everyCombination(seedCount = 4) {
  const selections = [];

  for (const vendor of VENDORS) {
    for (const type of DOCUMENT_TYPES) {
      for (const style of type.id === 'invoice' ? ['clean', 'dense'] : ['clean']) {
        for (let index = 0; index < seedCount; index += 1) {
          selections.push({
            docTypeId: type.id,
            seed: 1_009 + index * 7_919,
            style,
            today: TODAY,
            vendorId: vendor.id
          });
        }
      }
    }
  }

  return selections;
}

test('every document emits every key, with null standing for "not on the page"', () => {
  for (const selection of everyCombination(2)) {
    const payload = annotate(selection);
    const where = `${selection.vendorId}/${selection.docTypeId}/${selection.style}`;

    assert.deepEqual(Object.keys(payload.fields), FIELD_KEYS, `${where} field key set`);

    for (const [key, field] of Object.entries(payload.fields)) {
      if (field === null) {
        continue;
      }

      assert.deepEqual(
        Object.keys(field).sort(),
        ['text', 'value'],
        `${where} ${key} should carry both representations`
      );
      assert.notEqual(field.text, '', `${where} ${key} should be null rather than blank`);
    }
  }
});

test('line items and ledger rows carry their full key set too', () => {
  for (const selection of everyCombination(1)) {
    const payload = annotate(selection);

    for (const item of payload.line_items) {
      assert.deepEqual(Object.keys(item), ['index', ...LINE_ITEM_KEYS]);
    }

    for (const entry of payload.transactions) {
      assert.deepEqual(Object.keys(entry), ['index', ...TRANSACTION_KEYS]);
    }
  }
});

test('a field is non-null only when the page prints it', () => {
  const invoice = annotate({ docTypeId: 'invoice' });
  assert.equal(invoice.fields.po_number, null, 'a clean invoice carries no PO reference');
  assert.equal(invoice.fields.buyer_phone, null, 'and does not print the buyer phone');
  assert.equal(invoice.fields.vendor_company_reg, null, 'nor the company registration');
  assert.equal(invoice.fields.balance_due, null);
  assert.ok(invoice.fields.due_date, 'but it does print a due date');

  const dense = annotate({ docTypeId: 'invoice', style: 'dense' });
  assert.ok(dense.fields.buyer_phone, 'the dense consignee block prints the phone');
  assert.ok(dense.fields.vendor_company_reg, 'and the key grid prints the registration');
  assert.ok(dense.fields.order_number);
  assert.ok(dense.fields.reference);

  const challan = annotate({ docTypeId: 'challan' });
  assert.ok(challan.fields.po_number, 'a challan prints a PO reference');
  assert.ok(challan.fields.vehicle_number);
  assert.equal(challan.fields.subtotal, null, 'and no money at all');
  assert.equal(challan.fields.grand_total, null);
  assert.ok(
    challan.line_items.every((item) => item.unit_price === null && item.amount === null),
    'a goods dispatch note lists quantities without prices'
  );
  assert.ok(challan.line_items.every((item) => item.remarks));

  const statement = annotate({ docTypeId: 'statement' });
  assert.equal(statement.line_items.length, 0, 'a statement has a ledger, not line items');
  assert.ok(statement.transactions.length > 0);
  assert.ok(statement.fields.period_start);
  assert.ok(statement.fields.period_end);
  assert.ok(statement.fields.balance_due);

  const receipt = annotate({ docTypeId: 'receipt' });
  assert.ok(receipt.fields.payment_method);
  assert.ok(receipt.fields.against_invoice);
  assert.equal(receipt.fields.balance_due.value, 0, 'a settled receipt closes at zero');
});

test('the money adds up on every document the generator can produce', () => {
  for (const selection of everyCombination(6)) {
    const payload = annotate(selection);
    const where = `${selection.vendorId}/${selection.docTypeId}/${selection.style}/${selection.seed}`;
    const { grand_total: grand, shipping, subtotal, tax_amount: tax } = payload.fields;

    if (subtotal === null) {
      assert.equal(grand, null, `${where} cannot total what it does not price`);
      continue;
    }

    const lineSum = payload.line_items.reduce((sum, item) => sum + item.amount.value, 0);
    assert.equal(
      Math.round(lineSum * 100),
      Math.round(subtotal.value * 100),
      `${where} line amounts should sum to the subtotal`
    );

    const parts = subtotal.value + (tax?.value ?? 0) + (shipping?.value ?? 0);
    assert.equal(
      Math.round(parts * 100),
      Math.round(grand.value * 100),
      `${where} subtotal plus tax plus shipping should be the grand total`
    );
  }
});

test('per-line tax sums to the document tax wherever it is printed', () => {
  for (const selection of everyCombination(4).filter((entry) => entry.style === 'dense')) {
    const payload = annotate(selection);
    const lineTax = payload.line_items.reduce((sum, item) => sum + item.tax_amount.value, 0);
    assert.equal(Math.round(lineTax * 100), Math.round(payload.fields.tax_amount.value * 100));

    for (const item of payload.line_items) {
      assert.equal(
        Math.round(item.line_total.value * 100),
        Math.round((item.amount.value + item.tax_amount.value) * 100)
      );
    }
  }
});

test('values are normalised: ISO dates, numeric money, fractional rates', () => {
  const dense = annotate({ docTypeId: 'invoice', style: 'dense' });

  assert.match(dense.fields.document_date.value, ISO_DATE);
  assert.match(dense.fields.due_date.value, ISO_DATE);
  assert.equal(typeof dense.fields.grand_total.value, 'number');
  assert.equal(typeof dense.fields.tax_rate.value, 'number');
  assert.ok(dense.fields.tax_rate.value < 1, 'a rate is a fraction, not a percentage');
  assert.match(dense.fields.tax_rate.text, /%$/, 'but it prints as one');
  assert.match(dense.fields.grand_total.text, /^\$[\d,]+\.\d{2}$/);
});

test('a printed date and its ISO form describe the same calendar day', () => {
  // toISOString would convert to UTC first, so a date built west of Greenwich
  // would report the previous day and silently contradict the page.
  for (const selection of everyCombination(3)) {
    const payload = annotate(selection);
    const printed = payload.fields.document_date;
    const [year, month, day] = printed.value.split('-').map(Number);
    const rebuilt = new Date(year, month - 1, day);

    assert.equal(rebuilt.getFullYear(), year);
    assert.ok(printed.text.includes(String(day).padStart(2, '0')));
    assert.ok(printed.text.endsWith(String(year)));
  }
});

test('the buyer address keeps its line break in text and loses it in value', () => {
  const payload = annotate();
  assert.ok(payload.fields.buyer_address.text.includes('\n'));
  assert.ok(!payload.fields.buyer_address.value.includes('\n'));
  assert.equal(
    payload.fields.buyer_address.value,
    payload.fields.buyer_address.text.split('\n').join(', ')
  );
});

test('every labelled value on the page matches the sidecar text for that field', () => {
  for (const selection of everyCombination(2)) {
    const model = buildDocument(selection);
    const payload = buildAnnotations(model);
    const paper = createFakeElement('article');
    renderPaper(paper, model, createFakeDocument());
    const where = `${selection.vendorId}/${selection.docTypeId}/${selection.style}`;

    const tagged = findTagged(paper);
    assert.ok(tagged.length > 10, `${where} should label a real number of values`);

    for (const node of tagged) {
      const field = node.getAttribute('data-field');
      const parts = field.split('.');
      const annotation =
        parts.length === 1
          ? payload.fields[field]
          : payload[parts[0]][Number(parts[1])][parts[2]];

      assert.ok(annotation, `${where} labelled ${field} on the page but not in the sidecar`);
      // A field printed across several nodes, such as a two-line address or a
      // split logo lockup, contributes part of its text to each of them.
      assert.ok(
        annotation.text.includes(node.textContent),
        `${where} ${field}: page reads "${node.textContent}", sidecar says "${annotation.text}"`
      );
    }
  }
});

test('the envelope names the generator, the seed, and the schema', () => {
  const payload = annotate({ docTypeId: 'creditnote', seed: 1_001, vendorId: 'verde' });

  assert.equal(payload.schema_version, SCHEMA_VERSION);
  assert.equal(payload.generator, 'vendor-docs-generator');
  assert.equal(payload.seed, 1_001);
  assert.equal(payload.vendor_id, 'verde');
  assert.equal(payload.doc_type, 'debitnote', 'the resolved variant, not the selected type');
  assert.equal(payload.style, 'clean');
  assert.equal(payload.locale, 'en-US');
  assert.equal(payload.currency, 'USD');
  assert.equal(payload.page_size, 'A4');
  assert.equal(payload.filename_base, 'verde_debitnote_1001');
});

test('boxes are absent, and declared absent, until they are collected', () => {
  const bare = annotate();
  assert.equal(bare.boxes, null);
  assert.equal(bare.boxes_apply_to, null);

  const withBoxes = buildAnnotations(
    buildDocument({ docTypeId: 'invoice', seed: 4_242, today: TODAY, vendorId: 'apex' }),
    { page: { width: 794, height: 1123, unit: 'normalised' }, regions: [] }
  );
  assert.deepEqual(withBoxes.boxes_apply_to, ['png', 'pdf_raster']);
});

test('JSON serialisation is indented and newline-terminated', () => {
  const text = annotationsToJson(annotate());

  assert.ok(text.endsWith('\n'));
  assert.ok(text.includes('\n  "seed": 4242'));
  assert.deepEqual(JSON.parse(text).fields.document_number.text.slice(0, 4), 'INV-');
});

test('JSON Lines holds one compact object per document', () => {
  const entries = [annotate({ seed: 11 }), annotate({ seed: 12 })];
  const text = annotationsToJsonl(entries);

  assert.equal(text.split('\n').filter(Boolean).length, 2);
  assert.ok(!text.split('\n')[0].includes('\n  '), 'lines are compact, not indented');
  assert.equal(JSON.parse(text.split('\n')[1]).seed, 12);
  assert.equal(annotationsToJsonl([]), '', 'an empty run writes an empty file');
});

test('degradation is null on a clean page and fully described otherwise', () => {
  const built = buildDocument({ docTypeId: 'invoice', seed: 4242, today: TODAY, vendorId: 'apex' });
  assert.equal(buildAnnotations(built).degradation, null);

  const degradation = planDegradation({
    width: 794,
    height: 1123,
    preset: 'copier',
    seed: 4242,
    settings: resolveSettings('copier')
  });
  const payload = buildAnnotations(built, null, degradation);

  assert.equal(payload.degradation.preset, 'copier');
  assert.equal(payload.degradation.seed, 4242);
  assert.deepEqual(payload.degradation.applies_to, ['png', 'pdf_raster']);
  assert.deepEqual(payload.degradation.transform, degradation.transform);
  // Every resolved value, not just the ones the preset named, so a reader can
  // reproduce the page without also owning this version of the preset table.
  assert.equal(payload.degradation.settings.contrast, 1.35);
  assert.ok('lightCenter' in payload.degradation.settings, 'the seeded choices count too');
  assert.deepEqual(JSON.parse(JSON.stringify(payload)).degradation, payload.degradation);
});

test('the dataset README records the settings the run used', () => {
  const text = datasetReadme({
    boxes: true,
    count: 120,
    degradation: 'copier',
    format: 'png',
    generatedAt: '2026-06-15T00:00:00.000Z',
    pair: true,
    pdfMode: 'n/a',
    words: true
  });

  assert.ok(text.includes('Documents: 120'));
  assert.ok(text.includes('Format:    png'));
  assert.ok(text.includes('region and word level'));
  assert.ok(text.includes(`Schema:    ${SCHEMA_VERSION}`));
  assert.ok(text.includes('manifest.jsonl'));
  assert.ok(text.includes('not the text-layer PDF') || text.includes('text-layer PDF'));

  assert.ok(text.includes('Scan:      copier, paired with the clean original'));

  const plain = datasetReadme({
    boxes: false,
    count: 1,
    degradation: 'clean',
    format: 'json',
    generatedAt: '2026-06-15T00:00:00.000Z',
    pair: false,
    pdfMode: 'n/a',
    words: false
  });
  assert.ok(plain.includes('Boxes:     off'));
  assert.ok(plain.includes('Scan:      clean'));
  assert.ok(!plain.includes('paired with'));
});
