/**
 * Vendor document generator: UI wiring.
 *
 * Holds the small amount of mutable state the workbench needs (which vendor,
 * which document type, which invoice layout, the current seed, and the output
 * choices: scope, format, labels, and batch size), and hands everything else
 * to the model, renderer, and exporter modules.
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

/**
 * The Labels ladder, as the three switches it stands for. Each rung includes
 * everything below it, which is why one segmented control can replace three
 * checkboxes: "words" without "boxes" or "boxes" without "labels" is not a
 * state the page can ever be in.
 * @type {Record<string, { boxes: boolean, truth: boolean, words: boolean }>}
 */
const LABEL_LEVELS = {
  none: { boxes: false, truth: false, words: false },
  json: { boxes: false, truth: true, words: false },
  fields: { boxes: true, truth: true, words: false },
  words: { boxes: true, truth: true, words: true }
};

/**
 * The Include control, as the two cross-product switches it stands for.
 * @type {Record<string, { types: boolean, vendors: boolean }>}
 */
const INCLUDE_SCOPES = {
  combo: { types: false, vendors: false },
  types: { types: true, vendors: false },
  vendors: { types: false, vendors: true },
  all: { types: true, vendors: true }
};

/** What the status line says in batch mode before anything has run. */
const IDLE_BATCH_STATUS = "One ZIP, foldered as vendor / type.";

/** @type {import("./modules/exporters.js").ExportDeps} */
const exportDeps = {
  getJsPdf: () => requireGlobal("jsPDF", () => window.jspdf?.jsPDF),
  getHtml2Canvas: () => requireGlobal("html2canvas", () => window.html2canvas),
  getJsZip: () => requireGlobal("JSZip", () => window.JSZip)
};

/**
 * Wire a segmented control whose buttons carry one data attribute each, and
 * return a setter so state changed elsewhere can move the highlight.
 *
 * `initSegmented` only reacts to clicks. The Labels ladder, the preset row, and
 * the format control are also moved by code (a JSON batch lifts Labels off
 * None, a knob makes the preset custom), and `.active` is the source of truth
 * for the pressed state, so the setter writes both rather than leaving the two
 * to drift apart.
 * @param {HTMLElement} container - Element wrapping the buttons.
 * @param {string} attribute - Data attribute holding each button's value.
 * @param {(value: string) => void} onSelect - Called with the chosen value.
 * @returns {{ buttons: HTMLButtonElement[], set: (value: string) => void }} The buttons and a setter.
 */
function wireSegment(container, attribute, onSelect) {
  const buttons = initSegmented(container, (/** @type {HTMLButtonElement} */ button) =>
    onSelect(button.getAttribute(attribute) ?? "")
  );

  return {
    buttons,
    set: (value) => {
      for (const button of buttons) {
        const active = button.getAttribute(attribute) === value;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
      }
    }
  };
}

/**
 * Fill a segmented container with one button per item.
 * @param {HTMLElement} container - Empty segmented container.
 * @param {string} attribute - Data attribute to hold each value.
 * @param {ReadonlyArray<{ id: string, label: string, short: string }>} items - What to offer.
 * @returns {void}
 */
function fillSegment(container, attribute, items) {
  for (const item of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute(attribute, item.id);
    button.textContent = item.short;
    button.title = item.label;
    container.appendChild(button);
  }
}

initializeMatureApp({
  run: ({ runtime }) => {
    initAppShell();

    const vendorSelect = selectById("vdVendor");
    const vendorSwatch = byId("vdVendorSwatch");
    const typeSelect = selectById("vdDocTypeSelect");
    const batchOptions = byId("vdBatchOptions");
    const batchCount = inputById("vdBatchCount");
    const batchCountOut = byId("vdBatchCountOut");
    const formatJsonButton = buttonById("vdFormatJson");
    const downloadJsonButton = buttonById("vdDownloadJson");
    const pdfModeField = byId("vdPdfModeField");
    const labelsNote = byId("vdLabelsNote");
    const estimate = byId("vdEstimate");
    const degradeNote = byId("vdDegradeNote");
    const knobPanel = byId("vdKnobs");
    const pairToggle = inputById("vdPair");
    const pairLabel = byId("vdPairLabel");
    const paper = byId("vdPaper");
    const paperScale = byId("vdPaperScale");
    const paperFrame = byId("vdPaperFrame");
    const layoutToggle = byId("vdLayout");
    const zoomLevel = byId("vdZoomLevel");
    const fullscreen = /** @type {HTMLDialogElement} */ (byId("vdFullscreen"));
    const fullscreenBody = byId("vdFullscreenBody");
    const fullCaption = byId("vdFullCaption");
    const captionVendor = byId("vdCaptionVendor");
    const captionType = byId("vdCaptionType");
    const captionScan = byId("vdCaptionScan");
    const chipSeed = byId("vdChipSeed");
    const progress = byId("vdProgress");
    const progressFill = byId("vdProgressFill");
    const batchStatus = byId("vdBatchStatus");
    const exportButton = buttonById("vdExport");

    const state = {
      docTypeId: DOCUMENT_TYPES[0].id,
      /** @type {Partial<import("./modules/degrade.js").DegradeSettings>} */
      degradeOverrides: {},
      degradePreset: DEGRADE_PRESETS[0].id,
      /** @type {import("./modules/exporters.js").BatchFormat} */
      format: "pdf",
      include: "combo",
      labels: "json",
      mode: "page",
      /** @type {import("./modules/exporters.js").PdfMode} */
      pdfMode: "text",
      seed: rollSeed(),
      style: "clean",
      vendorId: VENDORS[0].id
    };

    /** @type {ReturnType<typeof buildDocument>} */
    let currentModel;

    /**
     * The three switches the Labels ladder stands for.
     * @returns {{ boxes: boolean, truth: boolean, words: boolean }} Ground truth, field boxes, word boxes.
     */
    function labelFlags() {
      return LABEL_LEVELS[state.labels];
    }

    /**
     * Whether the batch crosses every type, every vendor, or both.
     * @returns {{ types: boolean, vendors: boolean }} The cross-product switches.
     */
    function includeScope() {
      return INCLUDE_SCOPES[state.include];
    }

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

    /**
     * Set the status line, and hide it while it has nothing to say.
     * @param {string} text - Message, or an empty string to clear it.
     * @returns {void}
     */
    function setStatus(text) {
      batchStatus.textContent = text;
      batchStatus.hidden = text === "";
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
        // the sidecar would otherwise name a preset that was not used.
        state.degradeOverrides = { ...currentSettings(), [knob.key]: Number(input.value) };
        state.degradePreset = "custom";
        syncDegrade();
      });
    }

    for (const vendor of VENDORS) {
      const option = document.createElement("option");
      option.value = vendor.id;
      option.textContent = vendor.name;
      vendorSelect.appendChild(option);
    }

    // The type pills and this dropdown are one control in two shapes: the CSS
    // shows the pills while they fit and the dropdown when they would not.
    for (const type of DOCUMENT_TYPES) {
      const option = document.createElement("option");
      option.value = type.id;
      option.textContent = type.label;
      typeSelect.appendChild(option);
    }

    vendorSelect.value = state.vendorId;
    typeSelect.value = state.docTypeId;

    fillSegment(byId("vdDocType"), "data-type", DOCUMENT_TYPES);
    fillSegment(byId("vdDegradePreset"), "data-preset", DEGRADE_PRESETS);

    const typePills = wireSegment(byId("vdDocType"), "data-type", (typeId) => {
      setDocType(typeId);
    });
    const presetRow = wireSegment(byId("vdDegradePreset"), "data-preset", (presetId) => {
      state.degradePreset = presetId;
      // A named preset owns every setting, so choosing one drops the custom
      // overrides rather than layering on top of them.
      state.degradeOverrides = {};
      syncDegrade();
    });
    const layoutSegment = wireSegment(layoutToggle, "data-style", (style) => {
      state.style = style;
      draw();
    });
    const modeSegment = wireSegment(byId("vdMode"), "data-mode", (mode) => {
      state.mode = mode;
      setStatus(mode === "batch" ? IDLE_BATCH_STATUS : "");
      syncOutput();
    });
    const includeSegment = wireSegment(byId("vdInclude"), "data-include", (include) => {
      state.include = include;
      syncOutput();
    });
    const labelsSegment = wireSegment(byId("vdLabels"), "data-labels", (labels) => {
      state.labels = labels;
      syncOutput();
    });
    const formatSegment = wireSegment(byId("vdFormat"), "data-format", (format) => {
      state.format = /** @type {import("./modules/exporters.js").BatchFormat} */ (format);
      syncOutput();
    });
    const pdfModeSegment = wireSegment(byId("vdPdfMode"), "data-pdf-mode", (pdfMode) => {
      state.pdfMode = /** @type {import("./modules/exporters.js").PdfMode} */ (pdfMode);
      syncOutput();
    });

    /**
     * Switch the document type from either shape of the control.
     * @param {string} typeId - Document type id.
     * @returns {void}
     */
    function setDocType(typeId) {
      state.docTypeId = typeId;
      typeSelect.value = typeId;
      typePills.set(typeId);
      syncLayoutAvailability();
      draw();
    }

    /**
     * The dense layout is an invoice-only treatment; grey it out elsewhere so
     * the control never claims to do something it will not do.
     * @returns {void}
     */
    function syncLayoutAvailability() {
      const isInvoice = state.docTypeId === "invoice";
      layoutToggle.classList.toggle("is-disabled", !isInvoice);
      layoutToggle.setAttribute(
        "title",
        isInvoice
          ? "Dense is the line-level tax invoice, built from the same seed."
          : "The dense layout only applies to invoices."
      );

      for (const button of layoutSegment.buttons) {
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
      fullCaption.textContent = `${captionVendor.textContent} - ${captionType.textContent}`;
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
     * Render the current selection onto the paper and refresh the caption.
     * @returns {void}
     */
    function draw() {
      const isInvoice = state.docTypeId === "invoice";
      const documentType = findDocumentType(state.docTypeId);
      const vendor = findVendor(state.vendorId);
      currentModel = buildDocument({
        docTypeId: state.docTypeId,
        seed: state.seed,
        style: isInvoice ? state.style : "clean",
        vendorId: state.vendorId
      });

      renderPaper(paper, currentModel);
      // CSSOM rather than an inline style attribute, like the paper's own
      // vendor colours: the self-only CSP would drop the attribute.
      vendorSwatch.style.setProperty("--vd-accent", vendor.accent);
      captionVendor.textContent = vendor.name;
      captionType.textContent = currentModel.dense
        ? `${documentType.label} (dense)`
        : documentType.label;
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
        setStatus(error instanceof Error ? error.message : "Export failed.");
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
      const { boxes: withBoxes, words } = labelFlags();
      const measured = withBoxes ? collectBoxes(paper, { words }) : null;
      const boxes = degradation ? transformBoxes(measured, degradation.transform) : measured;
      return buildAnnotations(model, boxes, degradation);
    }

    /**
     * Keep the scan controls, their readouts, and the note in step.
     * @returns {void}
     */
    function syncDegrade() {
      const settings = currentSettings();

      for (const knob of knobs) {
        const value = Number(settings[/** @type {keyof typeof settings} */ (knob.key)]);
        knob.input.value = String(value);
        knob.output.textContent = `${value}${knob.unit}`;
      }

      presetRow.set(state.degradePreset);
      captionScan.textContent = presetLabel();
      degradeNote.textContent =
        state.degradePreset === "custom"
          ? "Custom settings, still driven by the document seed, so the page stays reproducible."
          : findPreset(state.degradePreset).note;
      syncOutput();
    }

    /**
     * Say what the Labels ladder will produce for the format picked.
     *
     * The text-layer PDF is called out because it is the one export boxes do
     * not describe, and every payload repeats it in `boxes_apply_to`, so nobody
     * has to remember which export the coordinates belong to.
     * @returns {string} The note.
     */
    function labelsNoteText() {
      const { boxes, truth, words } = labelFlags();

      if (!truth) {
        return "Exports are pages only. No labels are written.";
      }

      const writesPdf = state.format === "pdf" || state.format === "both";
      if (boxes && writesPdf && state.pdfMode === "text") {
        return "Boxes are measured on the rendered page, so they match the PNG and the rasterised PDF, not the text-layer PDF.";
      }

      if (words) {
        return "Each labelled value carries its box, and so does every word (slower).";
      }

      return boxes
        ? "Each labelled value also carries its box, in normalised page coordinates."
        : "Every page ships with a JSON sidecar naming what each printed value is.";
    }

    /**
     * Describe the files one page export writes.
     * @param {boolean} degraded - Whether the scan settings change the page.
     * @returns {string} For example `PDF + PNG + JSON`.
     */
    function pageFileList(degraded) {
      const wantsPng = state.format === "png" || state.format === "both";
      return [
        (state.format === "pdf" || state.format === "both") && "PDF",
        wantsPng && (pairToggle.checked && degraded ? "PNG + clean PNG" : "PNG"),
        labelFlags().truth && "JSON"
      ]
        .filter(Boolean)
        .join(" + ");
    }

    /**
     * Keep the output panel consistent with its state, and say what it will do.
     *
     * One pass over everything the scope, format, labels, and scan choices
     * decide between: which rows exist, what the primary button says, and what
     * the size estimate is. Written as a function of state rather than as a set
     * of handlers poking at each other, so a change from any control, or from
     * code, lands the panel in the same place.
     * @returns {void}
     */
    function syncOutput() {
      const batch = state.mode === "batch";
      const settings = currentSettings();
      const degraded = !isClean(settings);
      const { boxes, truth, words } = labelFlags();

      // JSON is only a batch format. Leaving batch with it selected falls back
      // to PDF rather than leaving page mode on a format it cannot write.
      if (!batch && state.format === "json") {
        state.format = "pdf";
      }

      // A JSON batch is labels and nothing else, so it cannot sit on None.
      if (state.format === "json" && state.labels === "none") {
        state.labels = "json";
      }

      modeSegment.set(state.mode);
      includeSegment.set(state.include);
      labelsSegment.set(state.labels);
      formatSegment.set(state.format);
      pdfModeSegment.set(state.pdfMode);

      batchOptions.hidden = !batch;
      formatJsonButton.hidden = !batch;
      downloadJsonButton.hidden = batch;
      // None is the first rung, and the one a JSON batch cannot stand on.
      labelsSegment.buttons[0].disabled = state.format === "json";
      pdfModeField.hidden = state.format !== "pdf" && state.format !== "both";
      // Pair mode writes the clean original beside a degraded PNG, so it means
      // nothing for a clean page or an export with no PNG in it.
      pairLabel.hidden = !degraded || (state.format !== "png" && state.format !== "both");
      labelsNote.textContent = labelsNoteText();

      const perCombination = Number(batchCount.value);
      const count = batch
        ? perCombination *
          (includeScope().vendors ? VENDORS.length : 1) *
          (includeScope().types ? DOCUMENT_TYPES.length : 1)
        : 1;
      const bytes = estimateBatchBytes({
        boxes,
        count,
        degraded,
        format: state.format,
        groundTruth: truth,
        lossy: degraded && settings.jpeg < 1,
        pair: pairToggle.checked,
        pdfMode: state.pdfMode,
        words
      });

      estimate.textContent = batch
        ? `${count} documents, roughly ${formatBytes(bytes)}.`
        : `${pageFileList(degraded)}, roughly ${formatBytes(bytes)}.`;

      // A run in flight owns the button's label, and restores it when it ends.
      if (!exportButton.disabled) {
        exportButton.textContent = batch ? "Generate ZIP" : "Download";
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
      // An empty track is just a grey slab sitting above the button, so the
      // meter only exists while there is progress to report.
      progress.hidden = false;
    }

    vendorSelect.addEventListener("change", () => {
      state.vendorId = vendorSelect.value;
      draw();
    });

    typeSelect.addEventListener("change", () => {
      setDocType(typeSelect.value);
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
      syncOutput();
    });

    pairToggle.addEventListener("change", syncOutput);

    /**
     * Write the sidecar alongside a page export, when labelling is on.
     * @returns {void}
     */
    function alsoDownloadGroundTruth() {
      if (labelFlags().truth) {
        downloadJson(annotate(currentModel), currentModel.filenameBase, exportDeps);
      }
    }

    /**
     * Export the page on screen in whichever formats are selected.
     *
     * One click is one export: the PDF, the PNG, or both, then a single sidecar
     * describing the page. The sidecar used to follow each download button, so
     * asking for both formats wrote it twice.
     * @returns {Promise<void>} Resolves once everything has been handed to the browser.
     */
    function exportPage() {
      return atActualSize(async () => {
        if (state.format === "pdf" || state.format === "both") {
          await downloadPdf(currentModel, state.pdfMode, paper, exportDeps, degradationFor(currentModel));
        }

        if (state.format === "png" || state.format === "both") {
          await downloadImage(currentModel, paper, exportDeps, {
            pair: pairToggle.checked,
            plan: degradationFor(currentModel)
          });
        }

        alsoDownloadGroundTruth();
      });
    }

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
        image.alt = `Scan preview of the generated ${captionType.textContent}`;
        fullCaption.textContent = `${captionVendor.textContent} - ${presetLabel()}`;
        fullscreenBody.replaceChildren(image);
        fullscreen.showModal();
      });
    });

    downloadJsonButton.addEventListener("click", () => {
      void withBusyButton(downloadJsonButton, "Measuring...", async () =>
        atActualSize(async () => {
          downloadJson(annotate(currentModel), currentModel.filenameBase, exportDeps);
        })
      );
    });

    const batchStopButton = buttonById("vdBatchStop");
    // Read by `runBatch` between documents. A plain flag rather than an
    // AbortController because there is nothing to abort: the run is a loop, and
    // stopping it means finishing the archive early rather than discarding it.
    let stopRequested = false;

    batchStopButton.addEventListener("click", () => {
      stopRequested = true;
      batchStopButton.disabled = true;
      setStatus("Stopping after the current document...");
    });

    /**
     * Run the batch the panel describes and hand over the ZIP.
     * @returns {Promise<void>} Resolves once the archive has been offered for download.
     */
    async function exportBatch() {
      stopRequested = false;
      batchStopButton.disabled = false;
      batchStopButton.hidden = false;

      const scope = includeScope();
      const plan = planBatch({
        vendorIds: scope.vendors ? VENDORS.map((vendor) => vendor.id) : [state.vendorId],
        docTypeIds: scope.types ? DOCUMENT_TYPES.map((type) => type.id) : [state.docTypeId],
        perCombination: Number(batchCount.value)
      });

      setProgress(0);
      setStatus(`Generating ${plan.length} documents...`);
      const startedAt = Date.now();
      const flags = labelFlags();

      try {
        const { blob, count, stopped } = await atActualSize(() =>
          runBatch({
            shouldStop: () => stopRequested,
            annotate: flags.truth ? annotate : undefined,
            degrade: degradationFor,
            deps: exportDeps,
            format: state.format,
            pair: pairToggle.checked,
            paper,
            pdfMode: state.pdfMode,
            plan,
            readme: {
              boxes: flags.boxes,
              degradation: state.degradePreset,
              words: flags.words
            },
            onProgress: ({ done, total, phase }) => {
              setProgress(done / total);
              setStatus(`${phase} ${done} of ${total}`);
            },
            renderPreview: (item) => {
              const model = buildDocument(item);
              renderPaper(paper, model);
              return model;
            }
          })
        );

        const seconds = ((Date.now() - startedAt) / 1000).toFixed(1);

        // Stopping before the first document finished leaves an archive holding
        // nothing but a README describing an empty run, which is a worse thing
        // to hand someone than no file at all.
        if (count === 0) {
          setStatus("Stopped before the first document. Nothing downloaded.");
        } else {
          const stamp = new Date().toISOString().slice(0, 10);
          const suffix = stopped ? "docs_partial" : "docs";
          triggerDownload(blob, `vendor_docs_${stamp}_${count}${suffix}.zip`);
          setStatus(
            stopped
              ? `Stopped. ${count} of ${plan.length} documents in ${seconds}s.`
              : `Done. ${count} documents in ${seconds}s.`
          );
        }
      } finally {
        batchStopButton.hidden = true;
        progress.hidden = true;
        draw();
      }
    }

    // One primary button for the whole panel: what it does is the scope above.
    exportButton.addEventListener("click", () => {
      const batch = state.mode === "batch";
      void withBusyButton(exportButton, batch ? "Generating..." : "Rendering...", () =>
        batch ? exportBatch() : exportPage()
      ).then(syncOutput);
    });

    syncLayoutAvailability();
    typePills.set(state.docTypeId);
    layoutSegment.set(state.style);
    syncDegrade();
    draw();
  }
});
