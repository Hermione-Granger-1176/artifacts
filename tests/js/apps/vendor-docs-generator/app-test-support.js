/**
 * Mock DOM and vendored globals for the vendor-docs-generator entry point.
 *
 * Builds on the shared app-entry mocks and adds this app's own element ids,
 * the layout toggle, a <dialog> stand-in for the full-size overlay, and
 * stand-ins for the three UMD export libraries.
 */

import { makeElement, setupFullMocks } from '../../common/app-entry-test-support.js';

import { createFakeCanvas, createFakeHtml2Canvas, createFakeJsPdf, createFakeJsZip } from './library-fakes.js';

const ELEMENT_IDS = [
  'vdVendor',
  'vdVendorSwatch',
  'vdDocType',
  'vdDocTypeSelect',
  'vdLayout',
  'vdMode',
  'vdInclude',
  'vdBatchOptions',
  'vdBatchCount',
  'vdBatchCountOut',
  'vdDegradePreset',
  'vdDegradeNote',
  'vdKnobs',
  'vdPair',
  'vdPairLabel',
  'vdLabels',
  'vdLabelsNote',
  'vdFormat',
  'vdFormatJson',
  'vdPdfMode',
  'vdPdfModeField',
  'vdPaper',
  'vdPaperScale',
  'vdPaperFrame',
  'vdZoomLevel',
  'vdFullOpen',
  'vdFullClose',
  'vdFullscreen',
  'vdFullscreenBody',
  'vdFullCaption',
  'vdCaptionVendor',
  'vdCaptionType',
  'vdCaptionScan',
  'vdChipSeed',
  'vdProgress',
  'vdProgressFill',
  'vdBatchStatus',
  'vdEstimate',
  'vdGenerate',
  'vdDownloadJson',
  'vdPreviewScan',
  'vdExport',
  'vdBatchStop'
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
 * Fill a segmented container with buttons, the way index.html ships them, and
 * make the container find them the way `querySelectorAll('button')` would.
 * @param {Record<string, any>} container - The segmented container.
 * @param {string} attribute - Data attribute carrying each value.
 * @param {string[]} values - One button per value.
 * @param {string} [active] - Value that starts active.
 * @returns {Record<string, any>[]} The buttons.
 */
function fillToggle(container, attribute, values, active) {
  const buttons = values.map((value) => makeToggleButton(`${container.id}-${value}`, attribute, value, value === active));

  for (const button of buttons) {
    container.appendChild(button);
  }

  container.querySelectorAll = () => container.children;
  return buttons;
}

/**
 * Click the button of a segmented control that carries a value.
 * @param {Record<string, any>} container - The segmented container.
 * @param {string} attribute - Data attribute carrying each value.
 * @param {string} value - Value to choose.
 * @returns {void}
 */
export function choose(container, attribute, value) {
  const button = container.children.find((candidate) => candidate.getAttribute(attribute) === value);
  fire(button, 'click');
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

  // The statically authored segmented controls. The type pills and the preset
  // row are built by app.js from its data tables, so they start empty.
  const layoutButtons = fillToggle(elementMap.vdLayout, 'data-style', ['clean', 'dense'], 'clean');
  fillToggle(elementMap.vdMode, 'data-mode', ['page', 'batch'], 'page');
  fillToggle(elementMap.vdInclude, 'data-include', ['combo', 'types', 'vendors', 'all'], 'combo');
  fillToggle(elementMap.vdLabels, 'data-labels', ['none', 'json', 'fields', 'words'], 'json');
  const formatButtons = fillToggle(elementMap.vdFormat, 'data-format', ['pdf', 'png', 'both', 'json'], 'pdf');
  fillToggle(elementMap.vdPdfMode, 'data-pdf-mode', ['text', 'image'], 'text');
  elementMap.vdFormatJson = formatButtons[3];
  elementMap.vdDocType.querySelectorAll = () => elementMap.vdDocType.children;
  elementMap.vdDegradePreset.querySelectorAll = () => elementMap.vdDegradePreset.children;

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
  elementMap.vdGenerate.textContent = 'New document';
  elementMap.vdDownloadJson.textContent = 'Download JSON only';
  elementMap.vdPreviewScan.textContent = 'Preview scan';
  elementMap.vdExport.textContent = 'Download';
  elementMap.vdBatchStop.textContent = 'Stop and keep what is done';
  elementMap.vdPair.checked = false;

  // index.html ships these with a `hidden` attribute; the mock has no markup to
  // read it from, so the initial state is mirrored here.
  elementMap.vdProgress.hidden = true;
  elementMap.vdBatchStatus.hidden = true;
  elementMap.vdBatchStop.hidden = true;
  elementMap.vdBatchOptions.hidden = true;
  elementMap.vdFormatJson.hidden = true;
  elementMap.vdPairLabel.hidden = true;
  elementMap.vdBatchCount.value = '2';
  // The paper stands in for a laid-out A4 page so the box collector has real
  // geometry to normalise against.
  elementMap.vdPaper.offsetWidth = 794;
  elementMap.vdPaper.offsetHeight = 1123;
  elementMap.vdPaper.rect = { left: 0, top: 0, width: 794, height: 1123 };

  const pdf = createFakeJsPdf();
  // A postage-stamp capture: the degradation pixel pass is a real loop over
  // every byte, and running it over a 1588 x 2246 page in a UI test would spend
  // seconds proving something the degrade tests already prove properly.
  const canvas = createFakeHtml2Canvas({ width: 80, height: 113 });
  const zip = createFakeJsZip();
  const scratchCanvases = [];
  const createFakeElement = globalThis.document.createElement;

  globalThis.document.createElement = (tag) => {
    if (tag !== 'canvas') {
      return createFakeElement(tag);
    }

    const scratch = createFakeCanvas(0, 0);
    scratchCanvases.push(scratch);
    return scratch;
  };

  globalThis.window.jspdf = { jsPDF: pdf.JsPdf };
  globalThis.window.html2canvas = canvas.html2canvas;
  globalThis.window.JSZip = zip.JsZip;

  return { ...shared, canvas, dialog, layoutButtons, pdf, scratchCanvases, zip };
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
