import assert from 'node:assert/strict';
import test from 'node:test';

import { cleanupMocks } from '../../common/app-entry-test-support.js';

import { choose, cleanupAppMocks, fire, flush, setupAppMocks } from './app-test-support.js';

/**
 * The names of everything a click hands to the browser as a download.
 *
 * Downloads are normally unlinked on a timer that the mock runs inline; holding
 * it open leaves the anchors in the body to be read back.
 * @param {() => void} click - Triggers the export.
 * @returns {Promise<string[]>} File names, with the seed stripped out.
 */
async function downloadsDuring(click) {
  const realSetTimeout = globalThis.window.setTimeout;
  globalThis.window.setTimeout = () => 0;
  globalThis.document.body.children = [];
  click();
  await flush();
  globalThis.window.setTimeout = realSetTimeout;

  return globalThis.document.body.children
    .map((node) => node.download)
    .filter(Boolean)
    .map((name) => name.replace(/_\d+\./, '.'));
}

/**
 * The value of the lone active button in a segmented control.
 * @param {Record<string, any>} container - The segmented container.
 * @param {string} attribute - Data attribute carrying each value.
 * @returns {string | undefined} The active value.
 */
function activeValue(container, attribute) {
  const active = container.children.filter((button) => button.classList.contains('active'));
  assert.ok(active.length <= 1, 'at most one segment is active');
  return active[0]?.getAttribute(attribute);
}

async function waitForBatch(button, maxTicks = 500) {
  for (let tick = 0; tick < maxTicks; tick += 1) {
    if (!button.disabled) {
      return;
    }
    await flush(1);
  }
  assert.fail('batch did not return to its idle state');
}

// One import, one pass over every control. The entry point is a module with
// side effects, so re-importing it per assertion would both re-run the
// bootstrap and split its coverage across cache-busted URLs; driving the whole
// workbench inside a single test keeps the run honest.
test('the vendor-docs-generator studio boots and drives every control', async () => {
  const { canvas, dialog, elementMap, layoutButtons, pdf, resizeObservers, zip } = setupAppMocks();
  const { vdPair, vdPairLabel, vdPdfMode } = elementMap;

  /** @returns {boolean} Whether the PDF type control is live rather than dimmed. */
  const pdfModeApplies = () => {
    const dimmed = vdPdfMode.classList.contains('is-disabled');
    assert.ok(
      vdPdfMode.children.every((button) => button.disabled === dimmed),
      'the buttons are disabled exactly when the control is dimmed'
    );
    return !dimmed;
  };

  /** @returns {boolean} Whether the pair option is live rather than dimmed. */
  const pairApplies = () => {
    assert.equal(vdPair.disabled, vdPairLabel.classList.contains('is-disabled'));
    return !vdPair.disabled;
  };

  try {
    await import(`../../../../apps/vendor-docs-generator/js/app.js?t=${Date.now()}`);

    // ── Boot ──────────────────────────────────────────────────────────
    assert.equal(globalThis.window.__ARTIFACT_READY__, true);
    assert.equal(globalThis.document.documentElement.dataset.runtimeStatus, 'ready');
    assert.equal(elementMap.vdVendor.children.length, 6, 'six vendors should be offered');
    assert.equal(elementMap.vdDocType.children.length, 6, 'six document type pills');
    assert.equal(elementMap.vdDocTypeSelect.children.length, 6, 'and the dropdown they fall back to');
    assert.equal(elementMap.vdDegradePreset.children.length, 5, 'five scan presets');
    assert.equal(elementMap.vdPaper.children.length, 1, 'a page should be on the paper');
    assert.equal(elementMap.vdCaptionVendor.textContent, 'Apex Industrial Supply');
    assert.equal(elementMap.vdCaptionType.textContent, 'Invoice');
    assert.equal(elementMap.vdCaptionScan.textContent, 'Clean');
    assert.match(elementMap.vdChipSeed.textContent, /^seed \d+$/);
    assert.equal(elementMap.vdVendorSwatch.style.getPropertyValue('--vd-accent'), '#1d4ed8');
    assert.equal(activeValue(elementMap.vdDocType, 'data-type'), 'invoice');
    assert.equal(activeValue(elementMap.vdDegradePreset, 'data-preset'), 'clean');

    // The panel opens as "this page": no batch rows, one primary button, and
    // the estimate already names the files a click will write.
    assert.equal(elementMap.vdBatchOptions.hidden, true);
    assert.equal(elementMap.vdFormatJson.hidden, true, 'JSON is a batch-only format');
    assert.equal(elementMap.vdDownloadJson.hidden, false);
    assert.equal(pairApplies(), false, 'nothing to pair a clean page with');
    assert.equal(pdfModeApplies(), true);
    assert.equal(elementMap.vdExport.textContent, 'Download');
    assert.match(elementMap.vdEstimate.textContent, /^PDF \+ JSON, roughly \d+ KB\.$/);
    assert.equal(elementMap.vdBatchStatus.textContent, '', 'the status line has nothing to say yet');
    assert.equal(elementMap.vdBatchStatus.hidden, false, 'but it keeps its row');
    assert.ok(elementMap.vdProgress.classList.contains('is-idle'), 'the meter holds its row, unseen');
    assert.equal(elementMap.vdProgress.hidden, false);
    assert.equal(elementMap.vdBatchStop.hidden, true, 'no stop button in page mode');

    // ── Vendor and type selection ─────────────────────────────────────
    elementMap.vdVendor.value = 'verde';
    fire(elementMap.vdVendor, 'change');
    assert.equal(elementMap.vdCaptionVendor.textContent, 'Verde Organic Foods');
    assert.equal(elementMap.vdVendorSwatch.style.getPropertyValue('--vd-accent'), '#15803d');

    choose(elementMap.vdDocType, 'data-type', 'statement');
    assert.equal(elementMap.vdCaptionType.textContent, 'Statement of account');
    assert.equal(elementMap.vdPaper.children.length, 1, 'the previous page should be replaced');
    assert.equal(activeValue(elementMap.vdDocType, 'data-type'), 'statement');
    assert.equal(elementMap.vdDocTypeSelect.value, 'statement', 'the dropdown follows the pills');

    // The dense treatment is invoice-only, so it withdraws elsewhere.
    assert.ok(layoutButtons.every((button) => button.disabled === true));
    assert.ok(elementMap.vdLayout.classList.contains('is-disabled'));
    assert.match(elementMap.vdLayout.getAttribute('title'), /only applies to invoices/);

    // The dropdown is the same control: choosing there moves the pills.
    elementMap.vdDocTypeSelect.value = 'invoice';
    fire(elementMap.vdDocTypeSelect, 'change');
    assert.equal(activeValue(elementMap.vdDocType, 'data-type'), 'invoice');
    assert.equal(elementMap.vdCaptionType.textContent, 'Invoice');
    assert.ok(layoutButtons.every((button) => button.disabled === false));
    assert.match(elementMap.vdLayout.getAttribute('title'), /same seed/);

    // ── Invoice layout ────────────────────────────────────────────────
    fire(layoutButtons[1], 'click');
    assert.equal(elementMap.vdCaptionType.textContent, 'Invoice (dense)');
    fire(layoutButtons[0], 'click');
    assert.equal(elementMap.vdCaptionType.textContent, 'Invoice');

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
    choose(elementMap.vdFormat, 'data-format', 'png');
    assert.equal(pdfModeApplies(), false, 'a PNG has no PDF type to choose');
    assert.equal(elementMap.vdPdfModeField.hidden, false, 'but the row stays put');
    assert.match(elementMap.vdPdfModeField.getAttribute('title'), /only applies when the format includes a PDF/);
    fire(elementMap.vdExport, 'click');
    await flush();
    assert.equal(canvas.captures.length, 1);
    assert.equal(elementMap.vdFullscreenBody.children.length, 1, 'the overlay keeps the page');

    fire(elementMap.vdFullClose, 'click');
    assert.equal(dialog.open, false);
    assert.equal(elementMap.vdPaperFrame.children.length, 1, 'the page returns to the frame');
    assert.equal(elementMap.vdPaperFrame.children[0], elementMap.vdPaperScale);

    // ── Single-page exports ───────────────────────────────────────────
    elementMap.vdVendor.value = 'apex';
    fire(elementMap.vdVendor, 'change');

    choose(elementMap.vdFormat, 'data-format', 'pdf');
    assert.equal(pdfModeApplies(), true);
    assert.equal(elementMap.vdPdfModeField.getAttribute('title'), null, 'nothing to explain once it applies');
    const pdfFiles = await downloadsDuring(() => fire(elementMap.vdExport, 'click'));
    assert.equal(pdf.documents.length, 1, 'the text path builds exactly one PDF');
    assert.match(pdf.documents[0].saved, /^apex_invoice_\d+\.pdf$/);
    assert.ok(pdf.documents[0].texts.length > 0, 'the text path should emit a text layer');
    assert.deepEqual(pdfFiles, ['apex_invoice.json'], 'the sidecar rides along with the page');
    assert.equal(elementMap.vdExport.disabled, false);
    assert.equal(elementMap.vdExport.textContent, 'Download');

    choose(elementMap.vdPdfMode, 'data-pdf-mode', 'image');
    assert.match(elementMap.vdLabelsNote.textContent, /Every page ships with a JSON sidecar/);
    fire(elementMap.vdExport, 'click');
    await flush();
    assert.equal(canvas.captures.length, 2, 'the rasterised path goes through html2canvas');
    assert.equal(pdf.documents[1].images.length, 1);

    // Both formats in one click: the PDF, the PNG, and one sidecar for the page.
    choose(elementMap.vdFormat, 'data-format', 'both');
    const bothFiles = await downloadsDuring(() => fire(elementMap.vdExport, 'click'));
    assert.equal(canvas.captures.length, 4, 'a rasterised PDF and a PNG capture once each');
    assert.equal(pdf.documents.length, 3);
    assert.equal(bothFiles.filter((name) => name.endsWith('.json')).length, 1, 'one sidecar, not one per format');
    assert.equal(bothFiles.filter((name) => name.endsWith('.png')).length, 1);
    assert.match(elementMap.vdEstimate.textContent, /^PDF \+ PNG \+ JSON, roughly /);

    // ── A missing library fails loudly, not silently ──────────────────
    choose(elementMap.vdFormat, 'data-format', 'pdf');
    choose(elementMap.vdPdfMode, 'data-pdf-mode', 'text');
    const realJsPdf = globalThis.window.jspdf;
    delete globalThis.window.jspdf;

    fire(elementMap.vdExport, 'click');
    await flush();
    assert.match(elementMap.vdBatchStatus.textContent, /jsPDF did not load/);
    assert.equal(elementMap.vdExport.disabled, false, 'the button must not stay stuck');
    assert.equal(elementMap.vdExport.textContent, 'Download');
    globalThis.window.jspdf = realJsPdf;

    // ── The Labels ladder keeps the three switches it stands for ──────
    // None writes no sidecar; JSON writes one; each rung above adds boxes.
    choose(elementMap.vdLabels, 'data-labels', 'none');
    assert.match(elementMap.vdLabelsNote.textContent, /No labels are written/);
    assert.match(elementMap.vdEstimate.textContent, /^PDF, roughly /);
    assert.deepEqual(await downloadsDuring(() => fire(elementMap.vdExport, 'click')), []);

    // The explicit JSON button still writes the sidecar for the page on screen.
    assert.deepEqual(await downloadsDuring(() => fire(elementMap.vdDownloadJson, 'click')), ['apex_invoice.json']);
    assert.equal(elementMap.vdDownloadJson.textContent, 'Download JSON only');

    choose(elementMap.vdLabels, 'data-labels', 'fields');
    assert.match(elementMap.vdLabelsNote.textContent, /not the text-layer PDF/);
    const fieldSidecar = await downloadsDuring(() => fire(elementMap.vdDownloadJson, 'click'));
    assert.deepEqual(fieldSidecar, ['apex_invoice.json']);
    // Both still writes the text-layer PDF, so the boxes caveat stays.
    choose(elementMap.vdFormat, 'data-format', 'both');
    assert.match(elementMap.vdLabelsNote.textContent, /not the text-layer PDF/);

    choose(elementMap.vdFormat, 'data-format', 'png');
    assert.match(elementMap.vdLabelsNote.textContent, /carries its box, in normalised page coordinates/);
    choose(elementMap.vdLabels, 'data-labels', 'words');
    assert.match(elementMap.vdLabelsNote.textContent, /every word/);
    choose(elementMap.vdLabels, 'data-labels', 'json');
    assert.equal(activeValue(elementMap.vdLabels, 'data-labels'), 'json');
    choose(elementMap.vdFormat, 'data-format', 'pdf');

    // ── Batch scope ───────────────────────────────────────────────────
    choose(elementMap.vdMode, 'data-mode', 'batch');
    assert.equal(elementMap.vdBatchOptions.hidden, false);
    assert.equal(elementMap.vdFormatJson.hidden, false, 'JSON joins the formats in batch mode');
    assert.equal(elementMap.vdDownloadJson.hidden, true, 'the single-page JSON button steps aside');
    assert.equal(elementMap.vdExport.textContent, 'Generate ZIP');
    assert.equal(elementMap.vdBatchStatus.textContent, 'One ZIP, foldered as vendor / type.');
    // The stop button holds an invisible slot under the primary button, so a
    // run starting does not move anything.
    assert.equal(elementMap.vdBatchStop.hidden, false);
    assert.ok(elementMap.vdBatchStop.classList.contains('is-idle'));

    elementMap.vdBatchCount.value = '25';
    fire(elementMap.vdBatchCount, 'input');
    assert.equal(elementMap.vdBatchCountOut.textContent, '25');
    assert.match(elementMap.vdEstimate.textContent, /^25 documents, roughly /);

    // An idle meter is an empty grey track above the button, so it stays
    // invisible (in its row) until there is progress to report.
    assert.ok(elementMap.vdProgress.classList.contains('is-idle'), 'the meter starts idle');

    elementMap.vdBatchCount.value = '2';
    const replacePaperChildren = elementMap.vdPaper.replaceChildren.bind(elementMap.vdPaper);
    let paperRenderCount = 0;
    elementMap.vdPaper.replaceChildren = (...nodes) => {
      paperRenderCount += 1;
      replacePaperChildren(...nodes);
    };
    const rendersBeforeTextBatch = paperRenderCount;
    fire(elementMap.vdExport, 'click');
    await waitForBatch(elementMap.vdExport);
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
    assert.ok(elementMap.vdProgress.classList.contains('is-idle'), 'and goes idle again when done');
    assert.equal(elementMap.vdProgressFill.style.scale, '1 1');
    assert.equal(elementMap.vdProgress.getAttribute('aria-valuenow'), '100');
    assert.equal(elementMap.vdExport.disabled, false);
    assert.equal(elementMap.vdExport.textContent, 'Generate ZIP');
    assert.ok(elementMap.vdBatchStop.classList.contains('is-idle'), 'the stop button goes idle with the run');

    // A failed archive still restores the idle controls and the selected page.
    const realJsZip = globalThis.window.JSZip;
    delete globalThis.window.JSZip;
    const previewBeforeFailedBatch = elementMap.vdChipSeed.textContent;
    fire(elementMap.vdExport, 'click');
    await waitForBatch(elementMap.vdExport);
    assert.match(elementMap.vdBatchStatus.textContent, /JSZip did not load/);
    assert.ok(elementMap.vdBatchStop.classList.contains('is-idle'));
    assert.ok(elementMap.vdProgress.classList.contains('is-idle'));
    assert.equal(elementMap.vdExport.disabled, false);
    assert.equal(elementMap.vdChipSeed.textContent, previewBeforeFailedBatch);
    globalThis.window.JSZip = realJsZip;

    // ── Stopping a run keeps what it finished ─────────────────────────
    elementMap.vdBatchCount.value = '4';
    const archivesBeforeStop = zip.archives.length;
    let stoppedAt = 0;
    elementMap.vdPaper.replaceChildren = (...nodes) => {
      paperRenderCount += 1;
      // Click Stop the way a person would: mid-run, once pages are appearing.
      if (!stoppedAt && !elementMap.vdBatchStop.classList.contains('is-idle') && paperRenderCount % 2 === 0) {
        stoppedAt = paperRenderCount;
        // Touching the panel mid-run re-syncs it, but the run owns the label.
        choose(elementMap.vdLabels, 'data-labels', 'json');
        assert.equal(elementMap.vdExport.textContent, 'Generating...');
        fire(elementMap.vdBatchStop, 'click');
      }
      replacePaperChildren(...nodes);
    };
    fire(elementMap.vdExport, 'click');
    assert.equal(elementMap.vdBatchStop.classList.contains('is-idle'), false, 'the stop button goes live with the run');
    await waitForBatch(elementMap.vdExport);

    assert.ok(elementMap.vdBatchStop.classList.contains('is-idle'));
    assert.match(elementMap.vdBatchStatus.textContent, /^Stopped\. \d+ of 4 documents in [\d.]+s\.$/);
    assert.equal(elementMap.vdExport.textContent, 'Generate ZIP');
    const partial = [...zip.archives[archivesBeforeStop].files.keys()]
      .filter((path) => path.endsWith('.pdf'));
    assert.ok(partial.length > 0 && partial.length < 4, `kept a partial run, got ${partial.length}`);
    assert.match(
      zip.archives[archivesBeforeStop].files.get('README.txt').data,
      new RegExp(`Documents: ${partial.length} \\(run stopped early; 4 were planned\\)`)
    );
    // Back to plain counting; the later runs still measure stage renders.
    elementMap.vdPaper.replaceChildren = (...nodes) => {
      paperRenderCount += 1;
      replacePaperChildren(...nodes);
    };

    // ── Include maps onto the two cross-product switches ──────────────
    elementMap.vdBatchCount.value = '1';
    choose(elementMap.vdInclude, 'data-include', 'types');
    assert.match(elementMap.vdEstimate.textContent, /^6 documents, roughly /);
    choose(elementMap.vdInclude, 'data-include', 'vendors');
    assert.match(elementMap.vdEstimate.textContent, /^6 documents, roughly /);
    choose(elementMap.vdInclude, 'data-include', 'all');
    assert.match(elementMap.vdEstimate.textContent, /^36 documents, roughly /);

    fire(elementMap.vdExport, 'click');
    await waitForBatch(elementMap.vdExport);

    assert.equal(
      [...zip.archives.at(-1).files.keys()].filter((path) => path.endsWith('.pdf')).length,
      36,
      'six vendors by six types by one document each'
    );

    // Only the types axis: one vendor, six types.
    choose(elementMap.vdInclude, 'data-include', 'types');
    fire(elementMap.vdExport, 'click');
    await waitForBatch(elementMap.vdExport);
    const typeOnly = [...zip.archives.at(-1).files.keys()].filter((path) => path.endsWith('.pdf'));
    assert.equal(typeOnly.length, 6);
    assert.ok(typeOnly.every((path) => path.startsWith('apex/')));

    // ── Scan quality ──────────────────────────────────────────────────
    choose(elementMap.vdInclude, 'data-include', 'combo');

    assert.equal(elementMap.vdKnobs.children.length, 9, 'a slider per exposed setting');
    assert.equal(pairApplies(), false, 'nothing to pair a clean page with');
    assert.match(elementMap.vdDegradeNote.textContent, /No geometry, no grain/);

    choose(elementMap.vdDegradePreset, 'data-preset', 'copier');
    assert.equal(activeValue(elementMap.vdDegradePreset, 'data-preset'), 'copier');
    assert.equal(elementMap.vdCaptionScan.textContent, 'Office copier');
    assert.match(elementMap.vdDegradeNote.textContent, /dust on the platen/);
    assert.match(elementMap.vdEstimate.textContent, /documents, roughly/);
    // Pair mode is offered once there is a scan to pair and a PNG to put it in.
    assert.equal(pairApplies(), false, 'a PDF-only run has no PNG to pair');
    assert.equal(elementMap.vdPairLabel.hidden, false, 'but the option keeps its row');
    assert.match(elementMap.vdPairLabel.getAttribute('title'), /needs a scan preset and a PNG/);
    choose(elementMap.vdFormat, 'data-format', 'both');
    assert.equal(pairApplies(), true);
    assert.equal(elementMap.vdPairLabel.getAttribute('title'), null);
    choose(elementMap.vdFormat, 'data-format', 'pdf');
    assert.equal(pairApplies(), false);

    // Touching a knob is what makes a run custom, so the sidecar never claims a
    // preset the page was not rendered under.
    const grain = elementMap.vdKnobs.children[6].children[1];
    grain.value = '3';
    fire(grain, 'input');
    assert.equal(activeValue(elementMap.vdDegradePreset, 'data-preset'), undefined, 'no preset is active');
    assert.equal(elementMap.vdCaptionScan.textContent, 'Custom');
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
    choose(elementMap.vdMode, 'data-mode', 'page');
    assert.equal(elementMap.vdBatchStatus.textContent, '', 'the batch hint leaves with batch mode');
    assert.equal(elementMap.vdBatchStop.hidden, true, 'and so does the stop button slot');
    choose(elementMap.vdDegradePreset, 'data-preset', 'fax');
    choose(elementMap.vdFormat, 'data-format', 'png');
    assert.equal(pairApplies(), true);
    elementMap.vdPair.checked = true;
    fire(elementMap.vdPair, 'change');
    assert.match(elementMap.vdEstimate.textContent, /^PNG \+ clean PNG \+ JSON, roughly /);

    assert.deepEqual(
      await downloadsDuring(() => fire(elementMap.vdExport, 'click')),
      ['apex_invoice.jpg', 'apex_invoice.clean.png', 'apex_invoice.json'],
      'a lossy scan, the clean original beside it, and one sidecar for both'
    );

    // ── A degraded batch labels what it actually rendered ─────────────
    choose(elementMap.vdMode, 'data-mode', 'batch');
    choose(elementMap.vdLabels, 'data-labels', 'fields');
    elementMap.vdBatchCount.value = '1';
    fire(elementMap.vdExport, 'click');
    await waitForBatch(elementMap.vdExport);

    // The seed picks the layout, so the stem varies; what must not vary is that
    // a lossy scan writes a JPEG, pair mode writes the clean PNG beside it, and
    // one sidecar labels both.
    const scanDocs = [...zip.archives.at(-1).files.keys()].filter((path) => path.includes('/'));
    assert.deepEqual(
      scanDocs.map((path) => path.slice(path.indexOf('apex_invoice') + 'apex_invoice'.length).replace(/^[\w]*?(?=\.)/, '')),
      ['.jpg', '.clean.png', '.json']
    );
    assert.ok(scanDocs.every((path) => path.startsWith('apex/invoice/apex_invoice_')));
    assert.ok(zip.archives.at(-1).files.get('README.txt').data.includes('Scan:      fax, paired'));

    const scanned = JSON.parse(zip.archives.at(-1).files.get('manifest.jsonl').data.trim());
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
    // A JSON batch is necessarily labelled, so it lifts Labels off None and
    // will not let it back until another format is chosen.
    choose(elementMap.vdLabels, 'data-labels', 'none');
    choose(elementMap.vdFormat, 'data-format', 'json');
    assert.equal(activeValue(elementMap.vdLabels, 'data-labels'), 'json');
    assert.equal(elementMap.vdLabels.children[0].disabled, true, 'None is not an option for JSON');
    assert.equal(pdfModeApplies(), false, 'JSON has no PDF type either');
    choose(elementMap.vdLabels, 'data-labels', 'fields');

    const archivesBeforeBoxedJson = zip.archives.length;
    const rendersBeforeBoxedJson = paperRenderCount;
    fire(elementMap.vdExport, 'click');
    await waitForBatch(elementMap.vdExport);
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

    choose(elementMap.vdLabels, 'data-labels', 'json');
    const archivesBeforeUnboxedJson = zip.archives.length;
    const rendersBeforeUnboxedJson = paperRenderCount;
    fire(elementMap.vdExport, 'click');
    await waitForBatch(elementMap.vdExport);
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

    // Leaving batch mode with JSON selected falls back to a format a page can
    // be exported in, rather than stranding the panel on one it cannot write.
    choose(elementMap.vdMode, 'data-mode', 'page');
    assert.equal(activeValue(elementMap.vdFormat, 'data-format'), 'pdf');
    assert.equal(elementMap.vdFormatJson.hidden, true);
    assert.equal(elementMap.vdLabels.children[0].disabled, false, 'None is available again');
    assert.equal(elementMap.vdBatchOptions.hidden, true);
    assert.equal(elementMap.vdExport.textContent, 'Download');

    // ── The frame is watched, not the window ──────────────────────────
    assert.equal(resizeObservers.length, 1, 'one observer refits the preview');
    const [observer] = resizeObservers;
    assert.equal(observer.target, elementMap.vdPaperFrame);
    const zoom = () => Number(elementMap.vdPaperScale.style.getPropertyValue('--vd-zoom'));

    // A frame 400 by 600 leaves 368 by 568 inside its padding: width is the
    // tighter fit, and the readout follows.
    elementMap.vdPaperFrame.clientWidth = 400;
    elementMap.vdPaperFrame.clientHeight = 600;
    observer.callback([]);
    assert.ok(Math.abs(zoom() - 368 / 794) < 1e-9, `fit to width, got ${zoom()}`);
    assert.equal(elementMap.vdZoomLevel.textContent, '46%');

    // Height is the tighter fit in a short frame.
    elementMap.vdPaperFrame.clientHeight = 400;
    observer.callback([]);
    assert.ok(Math.abs(zoom() - 368 / 1123) < 1e-9, `fit to height, got ${zoom()}`);
    elementMap.vdPaperFrame.clientHeight = 600;
    observer.callback([]);

    // The overlay owns the zoom while it is open.
    fire(elementMap.vdFullOpen, 'click');
    observer.callback([]);
    assert.equal(zoom(), 1, 'a resize does not shrink the page in the overlay');
    fire(elementMap.vdFullClose, 'click');
    assert.ok(Math.abs(zoom() - 368 / 794) < 1e-9, 'and closing it refits');

    // An export owns it too: a resize mid-capture must not bake a scale into
    // the raster, and the fit comes back once the export is done.
    choose(elementMap.vdFormat, 'data-format', 'png');
    const zoomsDuringCapture = [];
    const realHtml2Canvas = globalThis.window.html2canvas;
    globalThis.window.html2canvas = (...args) => {
      observer.callback([]);
      zoomsDuringCapture.push(zoom());
      return realHtml2Canvas(...args);
    };
    fire(elementMap.vdExport, 'click');
    await flush();
    globalThis.window.html2canvas = realHtml2Canvas;
    assert.deepEqual(zoomsDuringCapture, [1], 'the capture ran at actual size');
    assert.ok(Math.abs(zoom() - 368 / 794) < 1e-9, 'the fit returns after the export');
  } finally {
    cleanupAppMocks();
    cleanupMocks();
  }
});
