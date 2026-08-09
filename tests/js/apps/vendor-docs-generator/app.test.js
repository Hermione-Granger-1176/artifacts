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
    const replacePaperChildren = elementMap.vdPaper.replaceChildren.bind(elementMap.vdPaper);
    let paperRenderCount = 0;
    elementMap.vdPaper.replaceChildren = (...nodes) => {
      paperRenderCount += 1;
      replacePaperChildren(...nodes);
    };
    const rendersBeforeTextBatch = paperRenderCount;
    fire(elementMap.vdBatch, 'click');
    await flush(12);
    assert.equal(
      paperRenderCount - rendersBeforeTextBatch,
      3,
      'the two text-PDF documents and restored preview should render on stage'
    );

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

    // ── Scan quality ──────────────────────────────────────────────────
    elementMap.vdAllTypes.checked = false;
    elementMap.vdAllVendors.checked = false;

    assert.equal(elementMap.vdKnobs.children.length, 9, 'a slider per exposed setting');
    assert.equal(elementMap.vdDegradePreset.children.length, 6, 'five presets plus custom');
    assert.equal(elementMap.vdPair.disabled, true, 'nothing to pair a clean page with');
    assert.match(elementMap.vdDegradeNote.textContent, /No geometry, no grain/);

    elementMap.vdDegradePreset.value = 'copier';
    fire(elementMap.vdDegradePreset, 'change');
    assert.equal(elementMap.vdPair.disabled, false);
    assert.match(elementMap.vdDegradeNote.textContent, /dust on the platen/);
    assert.match(elementMap.vdBatchEstimate.textContent, /documents, roughly/);

    // Touching a knob is what makes a run custom, so the sidecar never claims a
    // preset the page was not rendered under.
    const grain = elementMap.vdKnobs.children[6].children[1];
    grain.value = '3';
    fire(grain, 'input');
    assert.equal(elementMap.vdDegradePreset.value, 'custom');
    assert.match(elementMap.vdDegradeNote.textContent, /still driven by the document seed/);
    assert.equal(elementMap.vdKnobs.children[6].children[0].children[1].textContent, '3');

    // ── Scan preview ──────────────────────────────────────────────────
    const capturesBeforePreview = canvas.captures.length;
    fire(elementMap.vdPreviewScan, 'click');
    await flush();
    assert.equal(canvas.captures.length, capturesBeforePreview + 1);
    assert.equal(dialog.open, true);
    assert.equal(elementMap.vdFullscreenBody.children.length, 1);
    assert.equal(elementMap.vdFullscreenBody.children[0].className, 'vd-scan-preview');
    assert.match(elementMap.vdFullCaption.textContent, / - Custom$/);

    fire(elementMap.vdFullClose, 'click');
    assert.equal(elementMap.vdFullscreenBody.children.length, 0, 'the preview image is cleared');
    assert.equal(elementMap.vdPaperFrame.children[0], elementMap.vdPaperScale);

    // ── A lossy preset writes a JPEG, and pair mode writes both ───────
    elementMap.vdDegradePreset.value = 'fax';
    fire(elementMap.vdDegradePreset, 'change');
    elementMap.vdPair.checked = true;
    fire(elementMap.vdPair, 'change');

    // Downloads are normally unlinked on a timer that the mock runs inline;
    // holding it open leaves the anchors in the body to be read back.
    const realSetTimeout = globalThis.window.setTimeout;
    globalThis.window.setTimeout = () => 0;
    fire(elementMap.vdDownloadPng, 'click');
    await flush();
    globalThis.window.setTimeout = realSetTimeout;

    const saved = globalThis.document.body.children.map((node) => node.download).filter(Boolean);
    assert.deepEqual(
      saved.map((name) => name.replace(/_\d+\./, '.')),
      ['apex_invoice.jpg', 'apex_invoice.clean.png', 'apex_invoice.json'],
      'a lossy scan, the clean original beside it, and one sidecar for both'
    );

    // ── A degraded batch labels what it actually rendered ─────────────
    elementMap.vdBatchFormat.value = 'png';
    elementMap.vdBoxes.checked = true;
    fire(elementMap.vdBoxes, 'change');
    elementMap.vdBatchCount.value = '1';
    fire(elementMap.vdBatch, 'click');
    await flush(20);

    // The seed picks the layout, so the stem varies; what must not vary is that
    // a lossy scan writes a JPEG, pair mode writes the clean PNG beside it, and
    // one sidecar labels both.
    const scanDocs = [...zip.archives[2].files.keys()].filter((path) => path.includes('/'));
    assert.deepEqual(
      scanDocs.map((path) => path.slice(path.indexOf('apex_invoice') + 'apex_invoice'.length).replace(/^[\w]*?(?=\.)/, '')),
      ['.jpg', '.clean.png', '.json']
    );
    assert.ok(scanDocs.every((path) => path.startsWith('apex/invoice/apex_invoice_')));
    assert.ok(zip.archives[2].files.get('README.txt').data.includes('Scan:      fax, paired'));

    const scanned = JSON.parse(zip.archives[2].files.get('manifest.jsonl').data.trim());
    assert.equal(scanned.degradation.preset, 'fax');
    assert.equal(scanned.degradation.seed, scanned.seed, 'the page and its wear share one seed');
    assert.deepEqual(scanned.degradation.applies_to, ['png', 'pdf_raster']);
    // The mock paper has no queryable children, so the regions themselves are
    // exercised in annotate-boxes.test.js and in Chromium; what matters here is
    // that a degraded run still asks for boxes and still declares where they
    // apply, rather than quietly dropping them.
    assert.deepEqual(scanned.boxes_apply_to, ['png', 'pdf_raster']);
    assert.deepEqual(scanned.boxes.page, { width: 794, height: 1123, unit: 'normalised' });
    assert.ok(scanned.degradation.transform.flat().every(Number.isFinite));

    // ── JSON-only format gating ───────────────────────────────────────
    // JSON is necessarily labelled, so its box controls must remain available
    // even when page-export sidecars are off.
    elementMap.vdGroundTruth.checked = false;
    fire(elementMap.vdGroundTruth, 'change');
    elementMap.vdBatchFormat.value = 'json';
    fire(elementMap.vdBatchFormat, 'change');
    assert.equal(elementMap.vdBoxes.disabled, false);
    assert.match(elementMap.vdGroundTruthNote.textContent, /JSON-only batches still contain labels/);

    const archivesBeforeBoxedJson = zip.archives.length;
    const rendersBeforeBoxedJson = paperRenderCount;
    fire(elementMap.vdBatch, 'click');
    await flush(12);
    assert.equal(zip.archives.length, archivesBeforeBoxedJson + 1);
    assert.equal(
      paperRenderCount - rendersBeforeBoxedJson,
      2,
      'the JSON document and restored preview should render on stage'
    );
    const boxedJsonArchive = zip.archives.at(-1).files;
    const boxedSidecarPath = [...boxedJsonArchive.keys()].find((path) => path.includes('/') && path.endsWith('.json'));
    assert.ok(boxedSidecarPath, 'the boxed JSON batch should contain a document sidecar');
    assert.ok(JSON.parse(boxedJsonArchive.get(boxedSidecarPath).data).boxes);

    elementMap.vdBoxes.checked = false;
    fire(elementMap.vdBoxes, 'change');
    const archivesBeforeUnboxedJson = zip.archives.length;
    const rendersBeforeUnboxedJson = paperRenderCount;
    fire(elementMap.vdBatch, 'click');
    await flush(12);
    assert.equal(zip.archives.length, archivesBeforeUnboxedJson + 1);
    assert.equal(
      paperRenderCount - rendersBeforeUnboxedJson,
      2,
      'unboxed JSON should preserve the same stage progress behavior'
    );
    const unboxedJsonArchive = zip.archives.at(-1).files;
    const unboxedSidecarPath = [...unboxedJsonArchive.keys()].find(
      (path) => path.includes('/') && path.endsWith('.json')
    );
    assert.ok(unboxedSidecarPath, 'the unboxed JSON batch should contain a document sidecar');
    assert.equal(JSON.parse(unboxedJsonArchive.get(unboxedSidecarPath).data).boxes, null);
  } finally {
    cleanupMocks();
  }
});
