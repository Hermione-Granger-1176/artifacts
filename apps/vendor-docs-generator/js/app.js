/**
 * Vendor document generator: UI wiring.
 *
 * Holds the small amount of mutable state the workbench needs (which vendor,
 * which document type, which invoice layout, and the current seed), and hands
 * everything else to the model, renderer, and exporter modules.
 *
 * @module app
 */

import { initializeMatureApp } from "../../../js/modules/app-runtime.js";
import { initAppShell, renderAppShell } from "../../../js/modules/app-shell.js";
import { initSegmented } from "../../../js/modules/segmented.js";

import { buildDocument } from "./modules/document-model.js";
import {
  downloadPdf,
  downloadPng,
  planBatch,
  runBatch,
  triggerDownload
} from "./modules/exporters.js";
import { renderPaper } from "./modules/paper-render.js";
import { DOCUMENT_TYPES, VENDORS, findDocumentType, findVendor } from "./modules/vendors.js";
import { rollSeed } from "./modules/random.js";

renderAppShell();

/**
 * @param {string} id - Element id.
 * @returns {HTMLElement} The element.
 */
const byId = (id) => /** @type {HTMLElement} */ (document.getElementById(id));

/**
 * @param {string} id - Element id.
 * @returns {HTMLInputElement} The input.
 */
const inputById = (id) => /** @type {HTMLInputElement} */ (document.getElementById(id));

/**
 * @param {string} id - Element id.
 * @returns {HTMLSelectElement} The select.
 */
const selectById = (id) => /** @type {HTMLSelectElement} */ (document.getElementById(id));

/**
 * @param {string} id - Element id.
 * @returns {HTMLButtonElement} The button.
 */
const buttonById = (id) => /** @type {HTMLButtonElement} */ (document.getElementById(id));

/**
 * Resolve a vendored UMD global, failing loudly when the script did not load.
 * @template T
 * @param {string} name - Library name, used in the error message.
 * @param {() => T | undefined} resolve - Accessor for the global.
 * @returns {T} The resolved global.
 */
function requireGlobal(name, resolve) {
  const value = resolve();

  if (!value) {
    throw new Error(`${name} did not load. Reload the page and try the export again.`);
  }

  return value;
}

/** A4 at 96dpi, matching --vd-page-width / --vd-page-height in app.css. */
const PAPER_WIDTH = 794;
const PAPER_HEIGHT = 1123;
/** Padding on .vd-paper-frame, from var(--space-4) on all four sides. */
const FRAME_PADDING = 32;
/** Floor on the fit scale, so a very short window still shows a legible page. */
const MIN_FIT_SCALE = 0.25;

/** @type {import("./modules/exporters.js").ExportDeps} */
const exportDeps = {
  getJsPdf: () => requireGlobal("jsPDF", () => window.jspdf?.jsPDF),
  getHtml2Canvas: () => requireGlobal("html2canvas", () => window.html2canvas),
  getJsZip: () => requireGlobal("JSZip", () => window.JSZip)
};

initializeMatureApp({
  run: ({ runtime }) => {
    initAppShell();

    const vendorSelect = selectById("vdVendor");
    const typeSelect = selectById("vdDocType");
    const pdfModeSelect = selectById("vdPdfMode");
    const batchFormatSelect = selectById("vdBatchFormat");
    const batchCount = inputById("vdBatchCount");
    const batchCountOut = byId("vdBatchCountOut");
    const allTypes = inputById("vdAllTypes");
    const allVendors = inputById("vdAllVendors");
    const paper = byId("vdPaper");
    const paperScale = byId("vdPaperScale");
    const paperFrame = byId("vdPaperFrame");
    const layoutToggle = byId("vdLayout");
    const layoutNote = byId("vdLayoutNote");
    const zoomLevel = byId("vdZoomLevel");
    const fullscreen = /** @type {HTMLDialogElement} */ (byId("vdFullscreen"));
    const fullscreenBody = byId("vdFullscreenBody");
    const fullCaption = byId("vdFullCaption");
    const chipVendor = byId("vdChipVendor");
    const chipType = byId("vdChipType");
    const chipSeed = byId("vdChipSeed");
    const progress = byId("vdProgress");
    const progressFill = byId("vdProgressFill");
    const batchStatus = byId("vdBatchStatus");

    const state = {
      docTypeId: DOCUMENT_TYPES[0].id,
      seed: rollSeed(),
      style: "clean",
      vendorId: VENDORS[0].id
    };

    /** @type {ReturnType<typeof buildDocument>} */
    let currentModel;

    for (const vendor of VENDORS) {
      const option = document.createElement("option");
      option.value = vendor.id;
      option.textContent = vendor.name;
      vendorSelect.appendChild(option);
    }

    for (const type of DOCUMENT_TYPES) {
      const option = document.createElement("option");
      option.value = type.id;
      option.textContent = type.label;
      typeSelect.appendChild(option);
    }

    vendorSelect.value = state.vendorId;
    typeSelect.value = state.docTypeId;

    const layoutButtons = /** @type {HTMLButtonElement[]} */ (
      Array.from(layoutToggle.querySelectorAll("button"))
    );

    /**
     * The dense layout is an invoice-only treatment; grey it out elsewhere so
     * the control never claims to do something it will not do.
     * @returns {void}
     */
    function syncLayoutAvailability() {
      const isInvoice = state.docTypeId === "invoice";
      layoutToggle.classList.toggle("is-disabled", !isInvoice);
      layoutNote.textContent = isInvoice
        ? "Dense is the line-level tax invoice, built from the same seed."
        : "The dense layout only applies to invoices.";

      for (const button of layoutButtons) {
        button.disabled = !isInvoice;
      }
    }

    /**
     * Scale the preview so the whole page fits the frame in both directions.
     *
     * Fitting on width alone left the page taller than its container, which
     * meant a scrollbar inside a panel that was already inside the scrolling
     * document. Fitting the smaller of the two ratios means the preview never
     * scrolls; reading the page at 100% is what the full-size overlay is for.
     * @returns {void}
     */
    function syncFitScale() {
      if (fullscreen.open) {
        return;
      }

      // An unmeasured frame (detached, or a test double) is treated as exactly
      // big enough, so the preview starts at 1 rather than guessing small.
      const frameWidth = paperFrame.clientWidth || PAPER_WIDTH + FRAME_PADDING;
      const frameHeight = paperFrame.clientHeight || PAPER_HEIGHT + FRAME_PADDING;
      const availableWidth = frameWidth - FRAME_PADDING;
      const availableHeight = frameHeight - FRAME_PADDING;
      const scale = Math.max(
        MIN_FIT_SCALE,
        Math.min(1, availableWidth / PAPER_WIDTH, availableHeight / PAPER_HEIGHT)
      );

      paperScale.style.setProperty("--vd-zoom", String(scale));
      zoomLevel.textContent = `${Math.round(scale * 100)}%`;
    }

    /**
     * Move the live paper into the full-size overlay and open it.
     *
     * The element itself moves rather than being cloned, so the renderer and
     * the exporters keep pointing at one page no matter which mode is showing.
     * @returns {void}
     */
    function openFullscreen() {
      fullCaption.textContent = `${chipVendor.textContent} - ${chipType.textContent}`;
      fullscreenBody.appendChild(paperScale);
      paperScale.style.setProperty("--vd-zoom", "1");
      fullscreen.showModal();
    }

    /**
     * Return the paper to the inline frame and restore the fitted scale.
     * @returns {void}
     */
    function closeFullscreen() {
      paperFrame.appendChild(paperScale);
      syncFitScale();
    }

    /**
     * Render the current selection onto the paper and refresh the chips.
     * @returns {void}
     */
    function draw() {
      const isInvoice = state.docTypeId === "invoice";
      currentModel = buildDocument({
        docTypeId: state.docTypeId,
        seed: state.seed,
        style: isInvoice ? state.style : "clean",
        vendorId: state.vendorId
      });

      renderPaper(paper, currentModel);
      chipVendor.textContent = findVendor(state.vendorId).name;
      chipType.textContent = currentModel.dense
        ? `${findDocumentType(state.docTypeId).label} (dense)`
        : findDocumentType(state.docTypeId).label;
      chipSeed.textContent = `seed ${state.seed}`;
      syncFitScale();
    }

    /**
     * Run a task with the preview pinned to actual size.
     *
     * The fit-width view scales the paper with a CSS transform, and
     * html2canvas would bake that scale into the capture. Neutralising it for
     * the duration of an export keeps every raster sample a true 794px page.
     * @template T
     * @param {() => Promise<T>} task - Work to run at actual size.
     * @returns {Promise<T>} Whatever the task resolves to.
     */
    async function atActualSize(task) {
      paperScale.style.setProperty("--vd-zoom", "1");

      try {
        return await task();
      } finally {
        syncFitScale();
      }
    }

    /**
     * Disable a button and swap its label while an async task runs.
     * @param {HTMLButtonElement} button - Button driving the task.
     * @param {string} busyLabel - Label to show while busy.
     * @param {() => Promise<void>} task - Work to run.
     * @returns {Promise<void>} Resolves once the button has been restored.
     */
    async function withBusyButton(button, busyLabel, task) {
      const originalLabel = button.textContent ?? "";
      button.disabled = true;
      button.textContent = busyLabel;

      try {
        await task();
      } catch (error) {
        runtime.reportError(error, "document export");
        batchStatus.textContent = error instanceof Error ? error.message : "Export failed.";
      } finally {
        button.disabled = false;
        button.textContent = originalLabel;
      }
    }

    /**
     * Move the batch progress meter.
     * @param {number} fraction - Completion between 0 and 1.
     * @returns {void}
     */
    function setProgress(fraction) {
      const percent = Math.round(Math.min(1, Math.max(0, fraction)) * 100);
      progressFill.style.width = `${percent}%`;
      progress.setAttribute("aria-valuenow", String(percent));
      // An empty track is just a grey slab sitting under the button, so the
      // meter only exists while there is progress to report.
      progress.hidden = false;
    }

    vendorSelect.addEventListener("change", () => {
      state.vendorId = vendorSelect.value;
      draw();
    });

    typeSelect.addEventListener("change", () => {
      state.docTypeId = typeSelect.value;
      syncLayoutAvailability();
      draw();
    });

    initSegmented(layoutToggle, (/** @type {HTMLButtonElement} */ button) => {
      state.style = button.getAttribute("data-style") ?? "clean";
      draw();
    });

    buttonById("vdFullOpen").addEventListener("click", openFullscreen);
    buttonById("vdFullClose").addEventListener("click", () => fullscreen.close());
    // Also fires for the Escape key, which is the dialog's own affordance.
    fullscreen.addEventListener("close", closeFullscreen);

    window.addEventListener("resize", syncFitScale, { passive: true });

    buttonById("vdGenerate").addEventListener("click", () => {
      state.seed = rollSeed();
      draw();
    });

    batchCount.addEventListener("input", () => {
      batchCountOut.textContent = batchCount.value;
    });

    const downloadPdfButton = buttonById("vdDownloadPdf");
    downloadPdfButton.addEventListener("click", () => {
      void withBusyButton(downloadPdfButton, "Rendering...", () =>
        atActualSize(() =>
          downloadPdf(
            currentModel,
            /** @type {import("./modules/exporters.js").PdfMode} */ (pdfModeSelect.value),
            paper,
            exportDeps
          )
        )
      );
    });

    const downloadPngButton = buttonById("vdDownloadPng");
    downloadPngButton.addEventListener("click", () => {
      void withBusyButton(downloadPngButton, "Rendering...", () =>
        atActualSize(() => downloadPng(currentModel, paper, exportDeps))
      );
    });

    const batchButton = buttonById("vdBatch");
    batchButton.addEventListener("click", () => {
      void withBusyButton(batchButton, "Generating...", async () => {
        const plan = planBatch({
          vendorIds: allVendors.checked ? VENDORS.map((vendor) => vendor.id) : [state.vendorId],
          docTypeIds: allTypes.checked ? DOCUMENT_TYPES.map((type) => type.id) : [state.docTypeId],
          perCombination: Number(batchCount.value)
        });

        setProgress(0);
        batchStatus.textContent = `Generating ${plan.length} documents...`;
        const startedAt = Date.now();

        const { blob, count } = await atActualSize(() =>
          runBatch({
            deps: exportDeps,
            format: /** @type {import("./modules/exporters.js").BatchFormat} */ (batchFormatSelect.value),
            paper,
            pdfMode: /** @type {import("./modules/exporters.js").PdfMode} */ (pdfModeSelect.value),
            plan,
            onProgress: ({ done, total, phase }) => {
              setProgress(done / total);
              batchStatus.textContent = `${phase} ${done} of ${total}`;
            },
            renderPreview: (item) => {
              const model = buildDocument(item);
              renderPaper(paper, model);
              return model;
            }
          })
        );

        const stamp = new Date().toISOString().slice(0, 10);
        triggerDownload(blob, `vendor_docs_${stamp}_${count}docs.zip`);
        const seconds = ((Date.now() - startedAt) / 1000).toFixed(1);
        batchStatus.textContent = `Done. ${count} documents in ${seconds}s.`;
        progress.hidden = true;
        draw();
      });
    });

    syncLayoutAvailability();
    draw();
  }
});
