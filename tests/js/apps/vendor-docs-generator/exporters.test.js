import assert from 'node:assert/strict';
import test from 'node:test';

import { buildDocument } from '../../../../apps/vendor-docs-generator/js/modules/document-model.js';
import {
  buildPdf,
  canvasToPdf,
  capturePaper,
  downloadPdf,
  downloadPng,
  planBatch,
  runBatch,
  triggerDownload
} from '../../../../apps/vendor-docs-generator/js/modules/exporters.js';

import { createFakeElement } from './fake-dom.js';
import { createExportDeps } from './library-fakes.js';

const TODAY = new Date(2026, 5, 15);

/**
 * Build a document model for export tests.
 * @param {Record<string, any>} [overrides={}] - buildDocument overrides.
 * @returns {ReturnType<typeof buildDocument>} The model.
 */
function model(overrides = {}) {
  return buildDocument({ docTypeId: 'invoice', seed: 4242, today: TODAY, vendorId: 'apex', ...overrides });
}

/**
 * Build the document and window stand-ins triggerDownload needs.
 * @returns {Record<string, any>} Fakes plus the recorded activity.
 */
function createDownloadHost() {
  const anchors = [];
  const revoked = [];
  const timers = [];
  const body = createFakeElement('body');

  const documentObj = {
    body,
    createElement(tag) {
      const element = createFakeElement(tag);
      element.clicked = 0;
      element.removed = false;
      element.click = () => {
        element.clicked += 1;
      };
      element.remove = () => {
        element.removed = true;
      };
      anchors.push(element);
      return element;
    }
  };

  const windowObj = {
    URL: {
      createObjectURL: () => 'blob:fake-url',
      revokeObjectURL: (url) => revoked.push(url)
    },
    setTimeout: (fn, delay) => {
      timers.push({ fn, delay });
      return timers.length;
    }
  };

  return { anchors, body, documentObj, revoked, timers, windowObj };
}

test('triggerDownload attaches, clicks, and then cleans up a blob anchor', () => {
  const host = createDownloadHost();
  const blob = { size: 12 };
  triggerDownload(blob, 'sample.zip', { documentObj: host.documentObj, windowObj: host.windowObj });

  const [anchor] = host.anchors;
  assert.equal(anchor.href, 'blob:fake-url');
  assert.equal(anchor.download, 'sample.zip');
  assert.equal(anchor.rel, 'noopener');
  assert.equal(anchor.hidden, true);
  assert.equal(host.body.children.length, 1, 'the anchor must be in the document to click it');
  assert.equal(anchor.clicked, 1);

  // The object URL survives the click and is revoked on a later tick.
  assert.deepEqual(host.revoked, []);
  assert.equal(host.timers[0].delay, 1500);
  host.timers[0].fn();
  assert.equal(anchor.removed, true);
  assert.deepEqual(host.revoked, ['blob:fake-url']);
});

test('triggerDownload passes a data URL straight through without revoking it', () => {
  const host = createDownloadHost();
  triggerDownload('data:image/png;base64,AAA', 'sample.png', {
    documentObj: host.documentObj,
    windowObj: host.windowObj
  });

  assert.equal(host.anchors[0].href, 'data:image/png;base64,AAA');
  host.timers[0].fn();
  assert.deepEqual(host.revoked, [], 'a data URL has nothing to revoke');
});

test('capturePaper rasterises the paper on a white ground at double density', async () => {
  const { canvas, deps } = createExportDeps();
  const paper = createFakeElement('article');
  await capturePaper(paper, deps);

  assert.equal(canvas.captures.length, 1);
  assert.equal(canvas.captures[0].element, paper);
  assert.equal(canvas.captures[0].options.scale, 2);
  assert.equal(canvas.captures[0].options.backgroundColor, '#ffffff');
});

test('canvasToPdf fits the capture to the page width, preserving aspect ratio', () => {
  const { deps } = createExportDeps();
  const canvas = { width: 1588, height: 2246, toDataURL: () => 'data:image/png;base64,AAA' };
  const doc = canvasToPdf(canvas, deps);
  const [, , x, y, width, height] = doc.images[0];

  assert.equal(x, 0);
  assert.equal(y, 0);
  assert.equal(width, 595);
  assert.ok(Math.abs(height / width - canvas.height / canvas.width) < 1e-9, 'aspect ratio drifted');
});

test('buildPdf writes a text layer in text mode and never touches the canvas', async () => {
  const { canvas, deps } = createExportDeps();
  const doc = await buildPdf(model(), 'text', createFakeElement('article'), deps);

  assert.equal(canvas.captures.length, 0, 'the text path must not rasterise');
  assert.equal(doc.images.length, 0);
  assert.ok(doc.texts.length > 0, 'the text path should print a text layer');
});

test('buildPdf rasterises in image mode and embeds a single picture', async () => {
  const { canvas, deps } = createExportDeps();
  const doc = await buildPdf(model(), 'image', createFakeElement('article'), deps);

  assert.equal(canvas.captures.length, 1);
  assert.equal(doc.images.length, 1);
  assert.equal(doc.texts.length, 0, 'the image path has no text layer, which is the point of it');
});

test('downloadPdf and downloadPng name their files after the seed', async () => {
  const current = model({ seed: 90_210, vendorId: 'harbor', docTypeId: 'receipt' });
  const { deps } = createExportDeps();
  const host = createDownloadHost();

  const pdfDeps = { ...deps, ...host };
  const doc = await buildPdf(current, 'text', createFakeElement('article'), pdfDeps);
  assert.equal(doc.saved, null);

  await downloadPdf(current, 'text', createFakeElement('article'), pdfDeps);
  await downloadPng(current, createFakeElement('article'), pdfDeps);

  assert.equal(current.filenameBase, 'harbor_receipt_90210');
  assert.equal(host.anchors[0].download, 'harbor_receipt_90210.png');
});

test('planBatch expands the full cross product of vendors, types, and count', () => {
  const plan = planBatch({
    vendorIds: ['apex', 'verde'],
    docTypeIds: ['invoice', 'receipt'],
    perCombination: 3,
    seedSource: () => 0.5,
    styleSource: () => 0.9
  });

  assert.equal(plan.length, 12);
  assert.deepEqual(new Set(plan.map((item) => item.vendorId)), new Set(['apex', 'verde']));
  assert.ok(plan.every((item) => item.seed === 451_000));
  assert.ok(plan.every((item) => item.style === 'clean'), 'a 0.9 draw stays under the dense threshold');
});

test('planBatch only marks invoices dense, and only below the threshold', () => {
  const dense = planBatch({
    vendorIds: ['apex'],
    docTypeIds: ['invoice', 'receipt'],
    perCombination: 1,
    seedSource: () => 0,
    styleSource: () => 0.1
  });

  assert.equal(dense.find((item) => item.docTypeId === 'invoice').style, 'dense');
  assert.equal(dense.find((item) => item.docTypeId === 'receipt').style, 'clean');
});

test('planBatch defaults to real randomness and stays in the seed range', () => {
  const plan = planBatch({ vendorIds: ['apex'], docTypeIds: ['invoice'], perCombination: 5 });
  assert.equal(plan.length, 5);
  assert.ok(plan.every((item) => item.seed >= 1000 && item.seed < 901_000));
});

/**
 * Run a batch over a fixed two-item plan.
 * @param {Record<string, any>} options - format, pdfMode, and any overrides.
 * @returns {Promise<Record<string, any>>} The batch result plus its fakes.
 */
async function runFixture({ format, pdfMode }) {
  const { canvas, deps, zip } = createExportDeps();
  const paper = createFakeElement('article');
  const progress = [];
  const plan = [
    { vendorId: 'apex', docTypeId: 'invoice', seed: 1000, style: 'clean' },
    { vendorId: 'verde', docTypeId: 'receipt', seed: 2000, style: 'clean' }
  ];

  const result = await runBatch({
    deps,
    format,
    paper,
    pdfMode,
    plan,
    onProgress: (entry) => progress.push(entry),
    renderPreview: (item) => buildDocument({ ...item, today: TODAY })
  });

  return { canvas, files: [...zip.archives[0].files.keys()], progress, result, zip };
}

test('a text-PDF batch folders by vendor and type and skips rasterising', async () => {
  const { canvas, files, result } = await runFixture({ format: 'pdf', pdfMode: 'text' });

  assert.deepEqual(files, [
    'apex/invoice/apex_invoice_1000.pdf',
    'verde/receipt/verde_receipt_2000.pdf'
  ]);
  assert.equal(canvas.captures.length, 0, 'the fast path must not rasterise');
  assert.equal(result.count, 2);
  assert.equal(result.blob.type, 'zip');
});

test('a PNG batch captures once per document and stores base64 entries', async () => {
  const { canvas, files, zip } = await runFixture({ format: 'png', pdfMode: 'text' });

  assert.deepEqual(files, [
    'apex/invoice/apex_invoice_1000.png',
    'verde/receipt/verde_receipt_2000.png'
  ]);
  assert.equal(canvas.captures.length, 2);
  const entry = zip.archives[0].files.get('apex/invoice/apex_invoice_1000.png');
  assert.deepEqual(entry.options, { base64: true });
  assert.equal(entry.data, 'ZmFrZQ==', 'the data URL prefix should be stripped');
});

test('a both-format image batch writes a PDF and a PNG from one capture each', async () => {
  const { canvas, files } = await runFixture({ format: 'both', pdfMode: 'image' });

  assert.deepEqual(files.sort(), [
    'apex/invoice/apex_invoice_1000.pdf',
    'apex/invoice/apex_invoice_1000.png',
    'verde/receipt/verde_receipt_2000.pdf',
    'verde/receipt/verde_receipt_2000.png'
  ]);
  assert.equal(canvas.captures.length, 2, 'one capture should serve both outputs');
});

test('a both-format text batch still needs a capture for the PNG half', async () => {
  const { canvas, files } = await runFixture({ format: 'both', pdfMode: 'text' });

  assert.equal(files.length, 4);
  assert.equal(canvas.captures.length, 2);
});

test('batch progress reports each document and then the zipping phase', async () => {
  const { progress } = await runFixture({ format: 'pdf', pdfMode: 'text' });

  assert.deepEqual(progress.slice(0, 2), [
    { done: 1, total: 2, phase: 'generating' },
    { done: 2, total: 2, phase: 'generating' }
  ]);
  assert.deepEqual(
    progress.slice(2).map((entry) => entry.phase),
    ['zipping 50%', 'zipping 100%']
  );
});

test('runBatch tolerates a caller that supplies no progress callback', async () => {
  const { deps } = createExportDeps();
  const result = await runBatch({
    deps,
    format: 'pdf',
    paper: createFakeElement('article'),
    pdfMode: 'text',
    plan: [{ vendorId: 'apex', docTypeId: 'invoice', seed: 7, style: 'clean' }],
    renderPreview: (item) => buildDocument({ ...item, today: TODAY })
  });

  assert.equal(result.count, 1);
});
