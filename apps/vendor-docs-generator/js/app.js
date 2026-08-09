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

import { collectBoxes, transformBoxes } from "./modules/annotate-boxes.js";
import { buildAnnotations } from "./modules/annotations.js";
import {
  DEGRADE_KNOBS,
  DEGRADE_PRESETS,
  degradeCanvas,
  encodeCanvas,
  findPreset,
  isClean,
  planDegradation,
  resolveSettings
} from "./modules/degrade.js";
import { buildDocument } from "./modules/document-model.js";
import {
  capturePaper,
  downloadImage,
  downloadJson,
  downloadPdf,
  estimateBatchBytes,
  formatBytes,
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
    const groundTruth = inputById("vdGroundTruth");
    const boxesToggle = inputById("vdBoxes");
    const wordBoxes = inputById("vdWordBoxes");
    const wordBoxesLabel = byId("vdWordBoxesLabel");
    const groundTruthNote = byId("vdGroundTruthNote");
    const batchEstimate = byId("vdBatchEstimate");
    const degradePreset = selectById("vdDegradePreset");
    const degradeNote = byId("vdDegradeNote");
    const knobPanel = byId("vdKnobs");
    const pairToggle = inputById("vdPair");
    const pairLabel = byId("vdPairLabel");
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
      /** @type {Partial<import("./modules/degrade.js").DegradeSettings>} */
      degradeOverrides: {},
      degradePreset: DEGRADE_PRESETS[0].id,
      seed: rollSeed(),
      style: "clean",
      vendorId: VENDORS[0].id
    };

    /** @type {ReturnType<typeof buildDocument>} */
    let currentModel;

    for (const preset of [...DEGRADE_PRESETS, { id: "custom", label: "Custom" }]) {
      const option = document.createElement("option");
      option.value = preset.id;
      option.textContent = preset.label;
      degradePreset.appendChild(option);
    }

    degradePreset.value = state.degradePreset;

    /**
     * Every setting the current preset and knob positions add up to.
     * @returns {import("./modules/degrade.js").DegradeSettings} Resolved settings.
     */
    function currentSettings() {
      return resolveSettings(state.degradePreset, state.degradeOverrides);
    }

    /**
     * Name the scan settings for a human.
     *
     * `findPreset` falls back to clean for an unknown id, which is right for
     * settings and wrong for a caption: "custom" is a real state, and labelling
     * it "Clean" would describe a page that is anything but.
     * @returns {string} Preset label, or "Custom".
     */
    function presetLabel() {
      return state.degradePreset === "custom" ? "Custom" : findPreset(state.degradePreset).label;
    }

    /** @type {{ input: HTMLInputElement, key: string, output: HTMLElement, unit: string }[]} */
    const knobs = [];

    // Built from DEGRADE_KNOBS rather than written into index.html, so the list
    // of exposed settings lives in one place and adding one is a single edit.
    for (const knob of DEGRADE_KNOBS) {
      const field = document.createElement("div");
      const head = document.createElement("div");
      const label = document.createElement("label");
      const output = document.createElement("output");
      const input = document.createElement("input");
      const inputId = `vdKnob-${knob.key}`;

      field.className = "control-field";
      head.className = "control-field-head";
      label.setAttribute("for", inputId);
      label.textContent = knob.label;
      output.setAttribute("for", inputId);
      input.id = inputId;
      input.className = "range-input";
      input.type = "range";
      input.min = String(knob.min);
      input.max = String(knob.max);
      input.step = String(knob.step);

      head.append(label, output);
      field.append(head, input);
      knobPanel.appendChild(field);
      knobs.push({ input, key: knob.key, output, unit: knob.unit });

      input.addEventListener("input", () => {
        // Touching a knob is what makes a run custom: the preset it started from
        // has stopped being an honest description of what will be rendered, and
        // the sidecar would otherwise claim a preset that was not used.
        state.degradeOverrides = { ...currentSettings(), [knob.key]: Number(input.value) };
        state.degradePreset = "custom";
        degradePreset.value = "custom";
        syncDegrade();
      });
    }

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
      fullscreenBody.replaceChildren(paperScale);
      paperScale.style.setProperty("--vd-zoom", "1");
      fullscreen.showModal();
    }

    /**
     * Return the paper to the inline frame and restore the fitted scale.
     *
     * Runs for the scan preview too, which puts an image in the overlay rather
     * than the live page; emptying the overlay first means one close path serves
     * both instead of two that can disagree.
     * @returns {void}
     */
    function closeFullscreen() {
      fullscreenBody.replaceChildren();
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
     * Plan the degradation for one document, or nothing if the run is clean.
     *
     * Planned against the layout page rather than the 2x capture: the transform
     * is normalised, so one plan serves both, and the JSON-only path can move
     * its boxes without rasterising anything.
     * @param {ReturnType<typeof buildDocument>} model - Document being exported.
     * @returns {import("./modules/degrade.js").DegradePlan | null} The plan.
     */
    function degradationFor(model) {
      const settings = currentSettings();

      if (isClean(settings)) {
        return null;
      }

      return planDegradation({
        height: PAPER_HEIGHT,
        preset: state.degradePreset,
        seed: model.seed,
        settings,
        width: PAPER_WIDTH
      });
    }

    /**
     * Build the ground-truth sidecar for a rendered document.
     *
     * Boxes are measured off the live paper element, so this has to be called
     * while that element still holds the document being described. They are then
     * moved through whatever geometry the scan preset applies, because a tilted
     * page has its ink somewhere other than where the DOM put it, and labels
     * pointing at the clean layout would be worse than no labels at all.
     * @param {ReturnType<typeof buildDocument>} model - Document on the paper.
     * @param {import("./modules/degrade.js").DegradePlan | null} [degradation] - Scan plan.
     * @returns {Record<string, any>} The sidecar payload.
     */
    function annotate(model, degradation = degradationFor(model)) {
      const measured = boxesToggle.checked
        ? collectBoxes(paper, { words: wordBoxes.checked })
        : null;
      const boxes = degradation ? transformBoxes(measured, degradation.transform) : measured;
      return buildAnnotations(model, boxes, degradation);
    }

    /**
     * Keep the scan controls, their readouts, and the note in step.
     * @returns {void}
     */
    function syncDegrade() {
      const settings = currentSettings();
      const clean = isClean(settings);

      for (const knob of knobs) {
        const value = Number(settings[/** @type {keyof typeof settings} */ (knob.key)]);
        knob.input.value = String(value);
        knob.output.textContent = `${value}${knob.unit}`;
      }

      // Pair mode writes the clean original beside the degraded page, which is
      // the same file twice when there is nothing to degrade.
      pairToggle.disabled = clean;
      pairLabel.classList.toggle("is-disabled", clean);
      degradeNote.textContent =
        state.degradePreset === "custom"
          ? "Custom settings, still driven by the document seed, so the page stays reproducible."
          : findPreset(state.degradePreset).note;
      syncEstimate();
    }

    /**
     * Keep the ground-truth controls consistent and say what they will produce.
     *
     * The box toggle is not disabled for a text-PDF batch, because the PNG of
     * the same run is still described correctly. It says so instead, and every
     * payload repeats it in `boxes_apply_to`, so nobody has to remember which
     * export the coordinates belong to.
     * @returns {void}
     */
    function syncGroundTruth() {
      const enabled = groundTruth.checked;
      boxesToggle.disabled = !enabled;
      wordBoxes.disabled = !enabled || !boxesToggle.checked;
      wordBoxesLabel.classList.toggle("is-disabled", wordBoxes.disabled);

      if (!enabled) {
        groundTruthNote.textContent = "Exports are pages only. No labels are written.";
        return;
      }

      if (boxesToggle.checked && batchFormatSelect.value === "pdf" && pdfModeSelect.value === "text") {
        groundTruthNote.textContent =
          "Boxes are measured on the rendered page, so they match the PNG and the rasterised PDF, not the text-layer PDF.";
        return;
      }

      groundTruthNote.textContent = boxesToggle.checked
        ? "Each labelled value also carries its box, in normalised page coordinates."
        : "Every page ships with a JSON sidecar naming what each printed value is.";
    }

    /**
     * Show what the current batch settings would download.
     * @returns {void}
     */
    function syncEstimate() {
      const perCombination = Number(batchCount.value);
      const count =
        perCombination *
        (allVendors.checked ? VENDORS.length : 1) *
        (allTypes.checked ? DOCUMENT_TYPES.length : 1);
      const settings = currentSettings();
      const degraded = !isClean(settings);
      const bytes = estimateBatchBytes({
        boxes: boxesToggle.checked,
        count,
        degraded,
        format: /** @type {import("./modules/exporters.js").BatchFormat} */ (batchFormatSelect.value),
        groundTruth: groundTruth.checked,
        lossy: degraded && settings.jpeg < 1,
        pair: pairToggle.checked,
        pdfMode: /** @type {import("./modules/exporters.js").PdfMode} */ (pdfModeSelect.value),
        words: wordBoxes.checked
      });

      batchEstimate.textContent = `${count} documents, roughly ${formatBytes(bytes)}.`;
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
      syncEstimate();
    });

    for (const control of [groundTruth, boxesToggle, wordBoxes]) {
      control.addEventListener("change", () => {
        syncGroundTruth();
        syncEstimate();
      });
    }

    for (const control of [batchFormatSelect, pdfModeSelect]) {
      control.addEventListener("change", () => {
        syncGroundTruth();
        syncEstimate();
      });
    }

    for (const control of [allTypes, allVendors, pairToggle]) {
      control.addEventListener("change", syncEstimate);
    }

    degradePreset.addEventListener("change", () => {
      state.degradePreset = degradePreset.value;
      // A named preset owns every setting, so choosing one drops the custom
      // overrides rather than layering on top of them.
      state.degradeOverrides = {};
      syncDegrade();
    });

    /**
     * Write the sidecar alongside a page export, when labelling is on.
     * @returns {void}
     */
    function alsoDownloadGroundTruth() {
      if (groundTruth.checked) {
        downloadJson(annotate(currentModel), currentModel.filenameBase, exportDeps);
      }
    }

    const downloadPdfButton = buttonById("vdDownloadPdf");
    downloadPdfButton.addEventListener("click", () => {
      void withBusyButton(downloadPdfButton, "Rendering...", () =>
        atActualSize(async () => {
          await downloadPdf(
            currentModel,
            /** @type {import("./modules/exporters.js").PdfMode} */ (pdfModeSelect.value),
            paper,
            exportDeps,
            degradationFor(currentModel)
          );
          alsoDownloadGroundTruth();
        })
      );
    });

    const downloadPngButton = buttonById("vdDownloadPng");
    downloadPngButton.addEventListener("click", () => {
      void withBusyButton(downloadPngButton, "Rendering...", () =>
        atActualSize(async () => {
          await downloadImage(currentModel, paper, exportDeps, {
            pair: pairToggle.checked,
            plan: degradationFor(currentModel)
          });
          alsoDownloadGroundTruth();
        })
      );
    });

    const previewScanButton = buttonById("vdPreviewScan");
    previewScanButton.addEventListener("click", () => {
      void withBusyButton(previewScanButton, "Rendering...", async () => {
        // Choosing between five scan presets from their descriptions alone is
        // guesswork, and the live page cannot show the effect: degradation
        // happens to the raster, and the boxes are measured off the DOM.
        const dataUrl = await atActualSize(async () => {
          const canvas = await capturePaper(paper, exportDeps);
          const degradation = degradationFor(currentModel);
          return degradation
            ? encodeCanvas(degradeCanvas(canvas, degradation), degradation.applied).dataUrl
            : canvas.toDataURL("image/png");
        });
        const image = document.createElement("img");
        image.className = "vd-scan-preview";
        image.src = dataUrl;
        image.alt = `Scan preview of the generated ${chipType.textContent}`;
        fullCaption.textContent = `${chipVendor.textContent} - ${presetLabel()}`;
        fullscreenBody.replaceChildren(image);
        fullscreen.showModal();
      });
    });

    const downloadJsonButton = buttonById("vdDownloadJson");
    downloadJsonButton.addEventListener("click", () => {
      void withBusyButton(downloadJsonButton, "Measuring...", async () =>
        atActualSize(async () => {
          downloadJson(annotate(currentModel), currentModel.filenameBase, exportDeps);
        })
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

        const labelled = groundTruth.checked || batchFormatSelect.value === "json";

        const { blob, count } = await atActualSize(() =>
          runBatch({
            annotate: labelled ? annotate : undefined,
            degrade: degradationFor,
            deps: exportDeps,
            format: /** @type {import("./modules/exporters.js").BatchFormat} */ (batchFormatSelect.value),
            pair: pairToggle.checked,
            paper,
            pdfMode: /** @type {import("./modules/exporters.js").PdfMode} */ (pdfModeSelect.value),
            plan,
            readme: {
              boxes: boxesToggle.checked,
              degradation: state.degradePreset,
              pair: pairToggle.checked && !isClean(currentSettings()),
              words: wordBoxes.checked
            },
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
    syncGroundTruth();
    syncDegrade();
    draw();
  }
});
