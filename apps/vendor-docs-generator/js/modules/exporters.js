/**
 * Export paths: single-document PDF and PNG, plus the batch ZIP.
 *
 * The three vendored libraries are reached through injected accessors rather
 * than touched directly, so the whole module runs under Node in tests with
 * lightweight fakes, and so a missing UMD global fails with a clear message
 * instead of a `TypeError` deep inside a click handler.
 *
 * @module exporters
 */

import { annotationsToJson, annotationsToJsonl, datasetReadme } from "./annotations.js";
import { degradeCanvas, encodeCanvas } from "./degrade.js";
import { renderPdf } from "./pdf-render.js";

/**
 * @typedef {import("./document-model.js").DocumentModel} DocumentModel
 * @typedef {import("./degrade.js").DegradePlan} DegradePlan
 * @typedef {{
 *   documentObj?: Document,
 *   getHtml2Canvas: () => ArtifactsHtml2Canvas,
 *   getJsPdf: () => ArtifactsJsPdfConstructor,
 *   getJsZip: () => ArtifactsJsZipConstructor,
 *   windowObj?: Window & typeof globalThis
 * }} ExportDeps
 * @typedef {{
 *   canvas: HTMLCanvasElement,
 *   clean: HTMLCanvasElement,
 *   dataUrl: string,
 *   extension: string
 * }} Raster
 * @typedef {"both" | "json" | "pdf" | "png"} BatchFormat
 * @typedef {"text" | "image"} PdfMode
 */

const DOWNLOAD_CLEANUP_MS = 1500;

/**
 * Hand a blob or data URL to the browser as a download.
 *
 * The anchor is attached to the document before clicking and revoked on a
 * timer rather than immediately: Safari and Firefox both cancel the download
 * if the object URL disappears in the same tick as the click.
 * @param {Blob | string} source - Blob, or an already-formed data URL.
 * @param {string} filename - Name to save as.
 * @param {{ documentObj?: Document, windowObj?: Window & typeof globalThis }} [options={}] - Injection points.
 * @returns {void}
 */
export function triggerDownload(source, filename, { documentObj = document, windowObj = window } = {}) {
  const isBlob = typeof source !== "string";
  const url = isBlob ? windowObj.URL.createObjectURL(source) : source;
  const anchor = documentObj.createElement("a");

  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  anchor.hidden = true;
  documentObj.body.appendChild(anchor);
  anchor.click();

  windowObj.setTimeout(() => {
    anchor.remove();

    if (isBlob) {
      windowObj.URL.revokeObjectURL(url);
    }
  }, DOWNLOAD_CLEANUP_MS);
}

/**
 * Rasterise the paper element at print-ish density.
 * @param {HTMLElement} paper - Element to capture.
 * @param {ExportDeps} deps - Injected library accessors.
 * @returns {Promise<HTMLCanvasElement>} The rendered canvas.
 */
export async function capturePaper(paper, deps) {
  const html2canvas = deps.getHtml2Canvas();
  return html2canvas(paper, {
    backgroundColor: "#ffffff",
    logging: false,
    scale: 2,
    useCORS: true
  });
}

/**
 * Rasterise the page and put it through the scan pipeline, if one is asked for.
 *
 * The clean capture is kept alongside the degraded one rather than discarded,
 * because pair mode writes both from a single render. Rendering the page twice
 * to get them would double the slowest step in the whole batch.
 * @param {HTMLElement} paper - Element to capture.
 * @param {ExportDeps} deps - Injected library accessors.
 * @param {DegradePlan | null} [plan=null] - Degradation to apply, or null for clean.
 * @returns {Promise<Raster>} The image to write, and the clean capture behind it.
 */
export async function renderRaster(paper, deps, plan = null) {
  const clean = await capturePaper(paper, deps);

  if (!plan) {
    return { canvas: clean, clean, dataUrl: clean.toDataURL("image/png"), extension: "png" };
  }

  const canvas = degradeCanvas(clean, plan, { documentObj: deps.documentObj ?? document });
  const { dataUrl, extension } = encodeCanvas(canvas, plan.applied);
  return { canvas, clean, dataUrl, extension };
}

/**
 * Wrap a rasterised page into a single-page A4 PDF, producing the "scanned
 * document" look that image-based extraction pipelines need to be tested against.
 * @param {Raster} raster - Rasterised page.
 * @param {ExportDeps} deps - Injected library accessors.
 * @returns {ArtifactsJsPdfDocument} A PDF holding the image.
 */
export function canvasToPdf(raster, deps) {
  const JsPdf = deps.getJsPdf();
  const doc = new JsPdf("p", "pt", "a4");
  const width = doc.internal.pageSize.getWidth();
  const format = raster.extension === "jpg" ? "JPEG" : "PNG";
  doc.addImage(raster.dataUrl, format, 0, 0, width, raster.canvas.height * (width / raster.canvas.width));
  return doc;
}

/**
 * Build the PDF for a document in the requested mode.
 * @param {DocumentModel} model - Document to export.
 * @param {PdfMode} mode - `text` for a real text layer, `image` for a raster page.
 * @param {HTMLElement} paper - Rendered paper element, used by the image mode.
 * @param {ExportDeps} deps - Injected library accessors.
 * @param {DegradePlan | null} [plan=null] - Degradation to apply to the raster mode.
 * @returns {Promise<ArtifactsJsPdfDocument>} The finished PDF document.
 */
export async function buildPdf(model, mode, paper, deps, plan = null) {
  if (mode === "text") {
    return renderPdf(model, deps.getJsPdf());
  }

  return canvasToPdf(await renderRaster(paper, deps, plan), deps);
}

/**
 * Export the on-screen document as a PDF download.
 * @param {DocumentModel} model - Document to export.
 * @param {PdfMode} mode - PDF mode.
 * @param {HTMLElement} paper - Rendered paper element.
 * @param {ExportDeps} deps - Injected library accessors.
 * @param {DegradePlan | null} [plan=null] - Degradation to apply to the raster mode.
 * @returns {Promise<void>} Resolves once the download has been triggered.
 */
export async function downloadPdf(model, mode, paper, deps, plan = null) {
  const doc = await buildPdf(model, mode, paper, deps, plan);
  doc.save(`${model.filenameBase}.pdf`);
}

/**
 * Export the on-screen document as an image download.
 *
 * The extension follows the encoding rather than the button: a lossy scan
 * preset writes a JPEG, because that is the compression a real scanner applied
 * and calling the result a PNG would be a lie about the file.
 * @param {DocumentModel} model - Document to export.
 * @param {HTMLElement} paper - Rendered paper element.
 * @param {ExportDeps} deps - Injected library accessors.
 * @param {{ pair?: boolean, plan?: DegradePlan | null }} [options={}] - Scan options.
 * @returns {Promise<void>} Resolves once the download has been triggered.
 */
export async function downloadImage(model, paper, deps, { pair = false, plan = null } = {}) {
  const raster = await renderRaster(paper, deps, plan);
  triggerDownload(raster.dataUrl, `${model.filenameBase}.${raster.extension}`, deps);

  if (pair && plan) {
    triggerDownload(raster.clean.toDataURL("image/png"), `${model.filenameBase}.clean.png`, deps);
  }
}

/**
 * Export a document's ground truth as a JSON download.
 * @param {Record<string, any>} annotations - Payload from `buildAnnotations`.
 * @param {string} filenameBase - Filename stem, matching the page's other exports.
 * @param {ExportDeps} deps - Injected library accessors and DOM injection points.
 * @returns {void}
 */
export function downloadJson(annotations, filenameBase, deps) {
  const blob = new Blob([annotationsToJson(annotations)], { type: "application/json" });
  triggerDownload(blob, `${filenameBase}.json`, deps);
}

/**
 * Expand the batch selection into the full list of documents to generate.
 * @param {{
 *   docTypeIds: string[],
 *   perCombination: number,
 *   seedSource?: () => number,
 *   styleSource?: () => number,
 *   vendorIds: string[]
 * }} options - Batch selection.
 * @returns {{ docTypeId: string, seed: number, style: string, vendorId: string }[]} Work items.
 */
export function planBatch({
  docTypeIds,
  perCombination,
  seedSource = Math.random,
  styleSource = Math.random,
  vendorIds
}) {
  const plan = [];

  for (const vendorId of vendorIds) {
    for (const docTypeId of docTypeIds) {
      for (let index = 0; index < perCombination; index += 1) {
        plan.push({
          vendorId,
          docTypeId,
          seed: Math.floor(seedSource() * 900_000) + 1_000,
          // Mix dense invoices into roughly 40% of the invoice samples so a
          // batch exercises both layouts without needing two runs.
          style: docTypeId === "invoice" && styleSource() < 0.4 ? "dense" : "clean"
        });
      }
    }
  }

  return plan;
}

/**
 * Rough compressed size of one document, per artefact, in bytes.
 *
 * Measured from real runs and deliberately generous. The point is not accuracy
 * to the byte, it is that a 500-page PNG batch is generated and zipped entirely
 * in the browser, and someone will ask for one. A number beside the button is a
 * far better experience than a tab that stops responding.
 */
const BYTES_PER_DOCUMENT = {
  png: 900_000,
  // Grain is close to incompressible, so a degraded page stored losslessly is
  // roughly twice the size of the clean one it came from.
  pngNoisy: 1_800_000,
  jpg: 420_000,
  pdfText: 16_000,
  pdfImage: 1_000_000,
  json: 1_400,
  jsonRegions: 5_000,
  jsonWords: 30_000
};

/**
 * Estimate the compressed size of a batch before it runs.
 * @param {{
 *   boxes?: boolean,
 *   count: number,
 *   degraded?: boolean,
 *   format: BatchFormat,
 *   groundTruth?: boolean,
 *   lossy?: boolean,
 *   pair?: boolean,
 *   pdfMode: PdfMode,
 *   words?: boolean
 * }} options - The settings the batch would run under.
 * @returns {number} Estimated archive size in bytes.
 */
export function estimateBatchBytes({
  boxes = false,
  count,
  degraded = false,
  format,
  groundTruth = false,
  lossy = false,
  pair = false,
  pdfMode,
  words = false
}) {
  let perDocument = 0;
  const imageBytes = lossy ? BYTES_PER_DOCUMENT.jpg : degraded ? BYTES_PER_DOCUMENT.pngNoisy : BYTES_PER_DOCUMENT.png;

  if (format === "png" || format === "both") {
    perDocument += imageBytes;

    if (degraded && pair) {
      perDocument += BYTES_PER_DOCUMENT.png;
    }
  }

  if (format === "pdf" || format === "both") {
    perDocument += pdfMode === "image" ? BYTES_PER_DOCUMENT.pdfImage : BYTES_PER_DOCUMENT.pdfText;
  }

  if (groundTruth || format === "json") {
    // Counted twice on purpose: every sidecar is written both as its own file
    // and as a line of manifest.jsonl.
    const perSidecar =
      BYTES_PER_DOCUMENT.json +
      (boxes ? BYTES_PER_DOCUMENT.jsonRegions : 0) +
      (boxes && words ? BYTES_PER_DOCUMENT.jsonWords : 0);
    perDocument += perSidecar * 2;
  }

  return count * perDocument;
}

/**
 * Render a byte count the way a download prompt would.
 * @param {number} bytes - Size in bytes.
 * @returns {string} Human-readable size, for example `1.4 MB`.
 */
export function formatBytes(bytes) {
  if (bytes < 1_000_000) {
    return `${Math.max(1, Math.round(bytes / 1_000))} KB`;
  }

  if (bytes < 1_000_000_000) {
    return `${(bytes / 1_000_000).toFixed(bytes < 10_000_000 ? 1 : 0)} MB`;
  }

  return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
}

/**
 * Generate a batch of documents and hand back a foldered ZIP.
 *
 * Text PDFs skip the DOM entirely, which is why they are so much faster than
 * the raster paths: nothing is rendered or rasterised, jsPDF writes straight
 * from the model. `json` is faster still, because it skips both renderers, and
 * it is the right format for anyone iterating on an evaluation script rather
 * than on the pages themselves.
 *
 * When ground truth is on, each document gets a sidecar next to it and the run
 * also writes `manifest.jsonl` and `README.txt` at the archive root. The
 * manifest exists because tooling that streams a dataset wants one file to
 * read, not five hundred to glob; the README exists so a ZIP found in a
 * downloads folder months later still explains its own schema and settings.
 * @param {{
 *   annotate?: (model: DocumentModel, degradation: DegradePlan | null) => Record<string, any>,
 *   degrade?: (model: DocumentModel) => DegradePlan | null,
 *   deps: ExportDeps,
 *   format: BatchFormat,
 *   onProgress?: (progress: { done: number, phase: string, total: number }) => void,
 *   pair?: boolean,
 *   paper: HTMLElement,
 *   pdfMode: PdfMode,
 *   plan: ReturnType<typeof planBatch>,
 *   readme?: { boxes: boolean, degradation: string, pair: boolean, words: boolean },
 *   renderPreview: (item: { docTypeId: string, seed: number, style: string, vendorId: string }) => DocumentModel
 * }} options - Batch inputs.
 * @returns {Promise<{ blob: Blob, count: number }>} The archive and how many documents it holds.
 */
export async function runBatch({
  annotate,
  degrade,
  deps,
  format,
  onProgress = () => {},
  pair = false,
  paper,
  pdfMode,
  plan,
  readme,
  renderPreview
}) {
  // Merged rather than defaulted, so a caller that names only some of the
  // README fields does not end up printing "undefined" into the archive.
  const dataset = { boxes: false, degradation: "clean", pair: false, words: false, ...readme };
  const JsZip = deps.getJsZip();
  const zip = new JsZip();
  const wantsPng = format === "png" || format === "both";
  const wantsPdf = format === "pdf" || format === "both";
  const wantsCanvas = wantsPng || (wantsPdf && pdfMode === "image");
  /** @type {Record<string, any>[]} */
  const manifest = [];
  let done = 0;

  for (const item of plan) {
    const model = renderPreview(item);
    const base = `${item.vendorId}/${item.docTypeId}/${model.filenameBase}`;
    const degradation = degrade ? degrade(model) : null;

    if (wantsPdf && pdfMode === "text") {
      zip.file(`${base}.pdf`, renderPdf(model, deps.getJsPdf()).output("blob"));
    }

    if (wantsCanvas) {
      // Sequential on purpose: one shared paper element is reused for every
      // capture, so the renders cannot overlap.
      const raster = await renderRaster(paper, deps, degradation);

      if (wantsPng) {
        zip.file(`${base}.${raster.extension}`, raster.dataUrl.split(",")[1], { base64: true });

        if (pair && degradation) {
          // The whole point of pair mode: one seed, two images, differing only
          // in scan quality, so accuracy can be plotted against it.
          zip.file(`${base}.clean.png`, raster.clean.toDataURL("image/png").split(",")[1], { base64: true });
        }
      }

      if (wantsPdf && pdfMode === "image") {
        zip.file(`${base}.pdf`, canvasToPdf(raster, deps).output("blob"));
      }
    }

    if (annotate) {
      // Measured after any capture, so the sidecar describes the same paper the
      // PNG was taken from rather than a page that has since been re-rendered.
      const payload = annotate(model, degradation);
      manifest.push(payload);
      zip.file(`${base}.json`, annotationsToJson(payload));
    }

    done += 1;
    onProgress({ done, total: plan.length, phase: "generating" });
  }

  if (annotate) {
    zip.file("manifest.jsonl", annotationsToJsonl(manifest));
    zip.file(
      "README.txt",
      datasetReadme({
        boxes: dataset.boxes,
        count: plan.length,
        degradation: dataset.degradation,
        format,
        generatedAt: new Date().toISOString(),
        pair: dataset.pair,
        pdfMode: wantsPdf ? pdfMode : "n/a",
        words: dataset.words
      })
    );
  }

  const blob = await zip.generateAsync(
    { type: "blob", compression: "DEFLATE", compressionOptions: { level: 6 } },
    (metadata) => {
      onProgress({ done: plan.length, total: plan.length, phase: `zipping ${Math.round(metadata.percent)}%` });
    }
  );

  return { blob, count: plan.length };
}
