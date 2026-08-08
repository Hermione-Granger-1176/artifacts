/**
 * Mock DOM and vendored globals for the vendor-docs-generator entry point.
 *
 * Builds on the shared app-entry mocks and adds this app's own element ids,
 * the layout toggle, a <dialog> stand-in for the full-size overlay, and
 * stand-ins for the three UMD export libraries.
 */

import { makeElement, setupFullMocks } from '../../common/app-entry-test-support.js';

import { createFakeHtml2Canvas, createFakeJsPdf, createFakeJsZip } from './library-fakes.js';

const ELEMENT_IDS = [
  'vdVendor',
  'vdDocType',
  'vdPdfMode',
  'vdBatchFormat',
  'vdBatchCount',
  'vdBatchCountOut',
  'vdAllTypes',
  'vdAllVendors',
  'vdPaper',
  'vdPaperScale',
  'vdPaperFrame',
  'vdLayout',
  'vdLayoutNote',
  'vdZoomLevel',
  'vdFullOpen',
  'vdFullClose',
  'vdFullscreen',
  'vdFullscreenBody',
  'vdFullCaption',
  'vdChipVendor',
  'vdChipType',
  'vdChipSeed',
  'vdProgress',
  'vdProgressFill',
  'vdBatchStatus',
  'vdBatchEstimate',
  'vdGenerate',
  'vdDownloadPdf',
  'vdDownloadPng',
  'vdDownloadJson',
  'vdGroundTruth',
  'vdBoxes',
  'vdWordBoxes',
  'vdWordBoxesLabel',
  'vdGroundTruthNote',
  'vdBatch'
];

/**
 * Build a segmented-toggle button carrying one data attribute.
 * @param {string} id - Element id.
 * @param {string} attribute - Attribute name.
 * @param {string} value - Attribute value.
 * @param {boolean} active - Whether it starts active.
 * @returns {Record<string, any>} The button.
 */
function makeToggleButton(id, attribute, value, active) {
  const button = makeElement(id);
  button.setAttribute(attribute, value);
  button.textContent = value;

  if (active) {
    button.classList.add('active');
  }

  return button;
}

/**
 * Install every mock the app entry point needs.
 * @returns {Record<string, any>} Element handles and library fakes.
 */
export function setupAppMocks() {
  const shared = setupFullMocks();
  const { elementMap } = shared;

  for (const id of ELEMENT_IDS) {
    elementMap[id] = makeElement(id);
  }

  const layoutButtons = [
    makeToggleButton('vdLayoutClean', 'data-style', 'clean', true),
    makeToggleButton('vdLayoutDense', 'data-style', 'dense', false)
  ];

  elementMap.vdLayout.querySelectorAll = () => layoutButtons;

  // A <dialog> stand-in: showModal/close flip `open` and close() notifies its
  // listeners the way the real element does for both the button and Escape.
  const dialog = elementMap.vdFullscreen;
  dialog.open = false;
  dialog.showModal = () => {
    dialog.open = true;
  };
  dialog.close = () => {
    dialog.open = false;

    for (const handler of dialog._listeners.close ?? []) {
      handler.call(dialog, { type: 'close' });
    }
  };
  // Mirror the labels index.html ships, since the busy-state handling swaps
  // them out and puts them back.
  elementMap.vdGenerate.textContent = 'Generate new document';
  elementMap.vdDownloadPdf.textContent = 'Download PDF';
  elementMap.vdDownloadPng.textContent = 'Download PNG';
  elementMap.vdDownloadJson.textContent = 'Download ground truth JSON';
  elementMap.vdBatch.textContent = 'Generate batch as ZIP';

  // index.html ships the meter with a `hidden` attribute; the mock has no
  // markup to read it from, so the initial state is mirrored here.
  elementMap.vdProgress.hidden = true;
  elementMap.vdBatchCount.value = '2';
  elementMap.vdPdfMode.value = 'text';
  elementMap.vdBatchFormat.value = 'pdf';
  elementMap.vdAllTypes.checked = false;
  elementMap.vdAllVendors.checked = false;
  // index.html ships ground truth on and both box modes off, which is the
  // "labels but no geometry" default the app opens in.
  elementMap.vdGroundTruth.checked = true;
  elementMap.vdBoxes.checked = false;
  elementMap.vdWordBoxes.checked = false;
  // The paper stands in for a laid-out A4 page so the box collector has real
  // geometry to normalise against.
  elementMap.vdPaper.offsetWidth = 794;
  elementMap.vdPaper.offsetHeight = 1123;
  elementMap.vdPaper.rect = { left: 0, top: 0, width: 794, height: 1123 };

  const pdf = createFakeJsPdf();
  const canvas = createFakeHtml2Canvas();
  const zip = createFakeJsZip();

  globalThis.window.jspdf = { jsPDF: pdf.JsPdf };
  globalThis.window.html2canvas = canvas.html2canvas;
  globalThis.window.JSZip = zip.JsZip;

  return { ...shared, canvas, dialog, layoutButtons, pdf, zip };
}

/**
 * Dispatch an event to every handler registered for it.
 * @param {Record<string, any>} element - Element holding the handlers.
 * @param {string} type - Event type.
 * @returns {void}
 */
export function fire(element, type) {
  for (const handler of element._listeners[type] ?? []) {
    handler.call(element, { type });
  }
}

/**
 * Let queued promise callbacks run before asserting on async handlers.
 * @param {number} [ticks=6] - How many macrotask turns to wait.
 * @returns {Promise<void>} Resolves once the turns have elapsed.
 */
export async function flush(ticks = 6) {
  for (let index = 0; index < ticks; index += 1) {
    await new Promise((resolve) => {
      setImmediate(resolve);
    });
  }
}
