import assert from 'node:assert/strict';
import test from 'node:test';

import { cleanupMocks } from '../../common/app-entry-test-support.js';

import { fire, flush, setupAppMocks } from './app-test-support.js';

// One import, one pass over every control. The entry point is a module with
// side effects, so re-importing it per assertion would both re-run the
// bootstrap and split its coverage across cache-busted URLs; driving the whole
// workbench inside a single test keeps the run honest.
test('the vendor-docs-generator workbench boots and drives every control', async () => {
  const { canvas, dialog, elementMap, layoutButtons, pdf, zip } = setupAppMocks();

  try {
    await import(`../../../../apps/vendor-docs-generator/js/app.js?t=${Date.now()}`);

    // ── Boot ──────────────────────────────────────────────────────────
    assert.equal(globalThis.window.__ARTIFACT_READY__, true);
    assert.equal(globalThis.document.documentElement.dataset.runtimeStatus, 'ready');
    assert.equal(elementMap.vdVendor.children.length, 6, 'six vendors should be offered');
    assert.equal(elementMap.vdDocType.children.length, 6, 'six document types should be offered');
    assert.equal(elementMap.vdPaper.children.length, 1, 'a page should be on the paper');
    assert.equal(elementMap.vdChipVendor.textContent, 'Apex Industrial Supply');
    assert.equal(elementMap.vdChipType.textContent, 'Invoice');
    assert.match(elementMap.vdChipSeed.textContent, /^seed \d+$/);

    // ── Vendor and type selection ─────────────────────────────────────
    elementMap.vdVendor.value = 'verde';
    fire(elementMap.vdVendor, 'change');
    assert.equal(elementMap.vdChipVendor.textContent, 'Verde Organic Foods');

    elementMap.vdDocType.value = 'statement';
    fire(elementMap.vdDocType, 'change');
    assert.equal(elementMap.vdChipType.textContent, 'Statement of account');
    assert.equal(elementMap.vdPaper.children.length, 1, 'the previous page should be replaced');

    // The dense treatment is invoice-only, so it withdraws elsewhere.
    assert.ok(layoutButtons.every((button) => button.disabled === true));
    assert.ok(elementMap.vdLayout.classList.contains('is-disabled'));
    assert.match(elementMap.vdLayoutNote.textContent, /only applies to invoices/);

    elementMap.vdDocType.value = 'invoice';
    fire(elementMap.vdDocType, 'change');
    assert.ok(layoutButtons.every((button) => button.disabled === false));
    assert.match(elementMap.vdLayoutNote.textContent, /same seed/);

    // ── Invoice layout ────────────────────────────────────────────────
    fire(layoutButtons[1], 'click');
    assert.equal(elementMap.vdChipType.textContent, 'Invoice (dense)');
    fire(layoutButtons[0], 'click');
    assert.equal(elementMap.vdChipType.textContent, 'Invoice');

    // ── Fresh seeds ───────────────────────────────────────────────────
    const seedBefore = elementMap.vdChipSeed.textContent;
    let seedChanged = false;

    for (let attempt = 0; attempt < 25 && !seedChanged; attempt += 1) {
      fire(elementMap.vdGenerate, 'click');
      seedChanged = elementMap.vdChipSeed.textContent !== seedBefore;
    }

    assert.ok(seedChanged, 'generating should roll a new seed');

    // ── Fitted preview ────────────────────────────────────────────────
    // The mock frame reports no dimensions, so the fallback fits a full page
    // into a full page: exactly 1, which is also the readout.
    assert.equal(elementMap.vdPaperScale.style.getPropertyValue('--vd-zoom'), '1');
    assert.equal(elementMap.vdZoomLevel.textContent, '100%');

    // ── Full-size overlay ─────────────────────────────────────────────
    fire(elementMap.vdFullOpen, 'click');
    assert.equal(dialog.open, true, 'the overlay should be modal');
    assert.equal(elementMap.vdFullscreenBody.children.length, 1, 'the page moves into it');
    assert.equal(elementMap.vdFullscreenBody.children[0], elementMap.vdPaperScale);
    assert.equal(elementMap.vdPaperScale.style.getPropertyValue('--vd-zoom'), '1');
    assert.equal(elementMap.vdFullCaption.textContent, 'Verde Organic Foods - Invoice');

    // Exporting from the overlay must not drag the page back to the frame.
    fire(elementMap.vdDownloadPng, 'click');
    await flush();
    assert.equal(canvas.captures.length, 1);
    assert.equal(elementMap.vdFullscreenBody.children.length, 1, 'the overlay keeps the page');

    fire(elementMap.vdFullClose, 'click');
    assert.equal(dialog.open, false);
    assert.equal(elementMap.vdPaperFrame.children.length, 1, 'the page returns to the frame');
    assert.equal(elementMap.vdPaperFrame.children[0], elementMap.vdPaperScale);

    // ── Single-document exports ───────────────────────────────────────
    elementMap.vdVendor.value = 'apex';
    fire(elementMap.vdVendor, 'change');

    fire(elementMap.vdDownloadPdf, 'click');
    await flush();
    assert.equal(pdf.documents.length, 1, 'the text path builds exactly one PDF');
    assert.match(pdf.documents[0].saved, /^apex_invoice_\d+\.pdf$/);
    assert.ok(pdf.documents[0].texts.length > 0, 'the text path should emit a text layer');
    assert.equal(elementMap.vdDownloadPdf.disabled, false);
    assert.equal(elementMap.vdDownloadPdf.textContent, 'Download PDF');

    elementMap.vdPdfMode.value = 'image';
    fire(elementMap.vdDownloadPdf, 'click');
    await flush();
    assert.equal(canvas.captures.length, 2, 'the rasterised path goes through html2canvas');
    assert.equal(pdf.documents[1].images.length, 1);

    fire(elementMap.vdDownloadPng, 'click');
    await flush();
    assert.equal(canvas.captures.length, 3);
    assert.equal(elementMap.vdDownloadPng.textContent, 'Download PNG');

    // ── A missing library fails loudly, not silently ──────────────────
    elementMap.vdPdfMode.value = 'text';
    const realJsPdf = globalThis.window.jspdf;
    delete globalThis.window.jspdf;

    fire(elementMap.vdDownloadPdf, 'click');
    await flush();
    assert.match(elementMap.vdBatchStatus.textContent, /jsPDF did not load/);
    assert.equal(elementMap.vdDownloadPdf.disabled, false, 'the button must not stay stuck');
    assert.equal(elementMap.vdDownloadPdf.textContent, 'Download PDF');
    globalThis.window.jspdf = realJsPdf;

    // ── Batch export ──────────────────────────────────────────────────
    elementMap.vdBatchCount.value = '25';
    fire(elementMap.vdBatchCount, 'input');
    assert.equal(elementMap.vdBatchCountOut.textContent, '25');

    // An idle meter is an empty grey track under the button, so it stays out
    // of the layout until there is progress to report.
    assert.equal(elementMap.vdProgress.hidden, true, 'the meter starts hidden');

    elementMap.vdBatchCount.value = '2';
    fire(elementMap.vdBatch, 'click');
    await flush(12);

    const files = [...zip.archives[0].files.keys()];
    // Two documents, each as a PDF and a sidecar, plus the two root files that
    // make the archive self-describing.
    assert.deepEqual(files.filter((path) => !path.includes('/')).sort(), [
      'README.txt',
      'manifest.jsonl'
    ]);
    const documents = files.filter((path) => path.includes('/'));
    assert.equal(documents.length, 4, 'one vendor, one type, two documents, page plus label');
    assert.ok(documents.every((path) => path.startsWith('apex/invoice/')));
    assert.equal(documents.filter((path) => path.endsWith('.json')).length, 2);

    const manifest = zip.archives[0].files.get('manifest.jsonl').data.trim().split('\n');
    assert.equal(manifest.length, 2, 'one compact object per document');
    assert.equal(JSON.parse(manifest[0]).vendor_id, 'apex');
    assert.equal(JSON.parse(manifest[0]).boxes, null, 'boxes are off by default');
    assert.match(elementMap.vdBatchStatus.textContent, /^Done\. 2 documents in [\d.]+s\.$/);
    assert.equal(elementMap.vdProgress.hidden, true, 'and goes away again when done');
    assert.equal(elementMap.vdProgressFill.style.width, '100%');
    assert.equal(elementMap.vdProgress.getAttribute('aria-valuenow'), '100');
    assert.equal(elementMap.vdBatch.disabled, false);
    assert.equal(elementMap.vdBatch.textContent, 'Generate batch as ZIP');

    // ── Full cross product ────────────────────────────────────────────
    elementMap.vdAllTypes.checked = true;
    elementMap.vdAllVendors.checked = true;
    elementMap.vdBatchCount.value = '1';
    fire(elementMap.vdBatch, 'click');
    await flush(40);

    assert.equal(
      [...zip.archives[1].files.keys()].filter((path) => path.endsWith('.pdf')).length,
      36,
      'six vendors by six types by one document each'
    );
  } finally {
    cleanupMocks();
  }
});
