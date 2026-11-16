/**
 * Export paths: single-document PDF and PNG, plus the batch ZIP.
 *
 * The three vendored libraries are reached through injected accessors, so the
 * module runs under Node in tests with fakes. A missing UMD global is reported
 * with a clear message.
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

/** How long a batch may hold the main thread before handing it back. */
const YIELD_INTERVAL_MS = 50;

/**
 * @param {BatchFormat} format - Selected output format.
 * @returns {boolean} Whether the format writes a PDF.
 */
export function formatWritesPdf(format) {
  return format === "pdf" || format === "both";
}

/**
 * @param {BatchFormat} format - Selected output format.
 * @returns {boolean} Whether the format writes a PNG (or its JPEG scan).
 */
export function formatWritesPng(format) {
  return format === "png" || format === "both";
}

/**
 * @param {string} dataUrl - Base64 data URL.
 * @returns {string} The base64 payload after the comma, as JSZip expects it.
 */
function base64Payload(dataUrl) {
  return dataUrl.split(",")[1];
}

/**
 * Hand a blob or data URL to the browser as a download.
 *
 * The anchor is attached before the click. The URL is revoked on a timer, not
 * immediately, because the download is cancelled if the object URL disappears
 * in the same tick as the click.
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
 * The clean capture is returned alongside the degraded one, so pair mode can
 * write both from a single render.
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

  // degradeCanvas falls back to the global document when deps carries none.
  const canvas = degradeCanvas(clean, plan, { documentObj: deps.documentObj });
  const { dataUrl, extension } = encodeCanvas(canvas, plan.applied);
  return { canvas, clean, dataUrl, extension };
}

/**
 * Wrap a rasterised page into a single-page A4 PDF with a scanned-document look.
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
 * The extension follows the encoding, not the button: a lossy scan preset
 * writes a JPEG.
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
  const seedRange = 900_000;

  for (const vendorId of vendorIds) {
    for (const docTypeId of docTypeIds) {
      const usedSeeds = new Set();

      for (let index = 0; index < perCombination; index += 1) {
        if (usedSeeds.size >= seedRange) {
          throw new RangeError(`Cannot generate more than ${seedRange} unique documents per vendor and type.`);
        }

        let seed = Math.floor(seedSource() * seedRange) + 1_000;

        // A repeated seed would produce the same filename. The seed is probed
        // forward through the seed range rather than redrawn, because the random
        // source may be deterministic or constant in tests and scripted runs.
        for (let offset = 0; usedSeeds.has(seed) && offset < usedSeeds.size; offset += 1) {
          seed = seed === 900_999 ? 1_000 : seed + 1;
        }

        usedSeeds.add(seed);
        plan.push({
          vendorId,
          docTypeId,
          seed,
          // Invoice samples use the dense layout about 40% of the time.
          style: docTypeId === "invoice" && styleSource() < 0.4 ? "dense" : "clean"
        });
      }
    }
  }

  return plan;
}

/**
 * Approximate compressed size of one document, per artefact, in bytes. The
 * estimate is shown before a large batch is generated and zipped in the browser.
 */
const BYTES_PER_DOCUMENT = {
  png: 900_000,
  // Degraded PNGs are estimated at about twice the clean size.
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

  if (formatWritesPng(format)) {
    perDocument += imageBytes;

    if (degraded && pair) {
      perDocument += BYTES_PER_DOCUMENT.png;
    }
  }

  if (formatWritesPdf(format)) {
    perDocument += pdfMode === "image" ? BYTES_PER_DOCUMENT.pdfImage : BYTES_PER_DOCUMENT.pdfText;
  }

  if (groundTruth || format === "json") {
    // Counted twice: each sidecar is written as its own file and as a line of
    // manifest.jsonl.
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
 * Capture the page once and write whichever raster-backed files the batch wants.
 *
 * The image and the PDF come from one capture.
 * @param {ArtifactsJsZipArchive} zip - Archive being filled.
 * @param {string} base - Archive path of the document, without extension.
 * @param {{
 *   degradation: DegradePlan | null,
 *   deps: ExportDeps,
 *   pair: boolean,
 *   paper: HTMLElement,
 *   wantsImagePdf: boolean,
 *   wantsPng: boolean
 * }} options - What to capture and which files to write from it.
 * @returns {Promise<boolean>} Whether the undegraded `.clean.png` was written beside the image.
 */
async function writeRasterFiles(zip, base, { degradation, deps, pair, paper, wantsImagePdf, wantsPng }) {
  const raster = await renderRaster(paper, deps, degradation);
  let wroteClean = false;

  if (wantsPng) {
    zip.file(`${base}.${raster.extension}`, base64Payload(raster.dataUrl), { base64: true });

    if (pair && degradation) {
      // Pair mode writes one seed as two images that differ only in scan quality.
      zip.file(`${base}.clean.png`, base64Payload(raster.clean.toDataURL("image/png")), { base64: true });
      wroteClean = true;
    }
  }

  if (wantsImagePdf) {
    zip.file(`${base}.pdf`, canvasToPdf(raster, deps).output("blob"));
  }

  return wroteClean;
}

/**
 * Generate a batch of documents and hand back a foldered ZIP.
 *
 * Text PDFs skip raster capture, since jsPDF writes from the model. `json` skips
 * both file renderers, but `renderPreview` still runs for every item.
 *
 * When annotations are enabled, each document gets a sidecar next to it, and
 * the archive root also gets `manifest.jsonl` and `README.txt`.
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
 *   readme?: { boxes: boolean, degradation: string, words: boolean },
 *   renderPreview: (item: { docTypeId: string, seed: number, style: string, vendorId: string }) => DocumentModel,
 *   shouldStop?: () => boolean
 * }} options - Batch inputs.
 * @returns {Promise<{ blob: Blob, count: number, stopped: boolean }>} The archive, how many documents it holds, and whether it was cut short.
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
  renderPreview,
  shouldStop = () => false
}) {
  const JsZip = deps.getJsZip();
  const zip = new JsZip();
  const wantsPng = formatWritesPng(format);
  const wantsPdf = formatWritesPdf(format);
  const wantsCanvas = wantsPng || (wantsPdf && pdfMode === "image");
  // Merged over the defaults, so README fields the caller omits keep their
  // default values.
  const dataset = {
    boxes: false,
    degradation: "clean",
    words: false,
    ...readme
  };
  /** @type {Record<string, any>[]} */
  const manifest = [];
  let done = 0;
  let wrotePair = false;
  let stopped = false;
  let sliceStartedAt = Date.now();

  for (const item of plan) {
    if (shouldStop()) {
      stopped = true;
      break;
    }

    const model = renderPreview(item);
    // The folder uses the variant the model resolved, which can differ from the
    // planned type. An odd-seed debit note goes in debitnote/.
    const base = `${item.vendorId}/${model.docVariantId}/${model.filenameBase}`;
    const degradation = degrade ? degrade(model) : null;

    if (wantsPdf && pdfMode === "text") {
      zip.file(`${base}.pdf`, renderPdf(model, deps.getJsPdf()).output("blob"));
    }

    if (wantsCanvas) {
      // Sequential: one shared paper element is reused for every capture.
      const wroteClean = await writeRasterFiles(zip, base, {
        degradation,
        deps,
        pair,
        paper,
        wantsImagePdf: wantsPdf && pdfMode === "image",
        wantsPng
      });

      if (wroteClean) {
        wrotePair = true;
      }
    }

    if (annotate) {
      // Runs after the capture, so the sidecar describes the paper the PNG was
      // taken from.
      const payload = annotate(model, degradation);
      manifest.push(payload);
      zip.file(`${base}.json`, annotationsToJson(payload));
    }

    done += 1;
    onProgress({ done, total: plan.length, phase: "generating" });

    // Yield to the main thread about every YIELD_INTERVAL_MS so that clicks, such
    // as Stop, are processed. Canvas formats yield inside `renderRaster`. Text
    // PDFs and JSON do not, so this check is needed for them. Yields are
    // time-sliced, not made per document.
    if (Date.now() - sliceStartedAt >= YIELD_INTERVAL_MS) {
      await new Promise((resolve) => {
        setTimeout(resolve, 0);
      });
      sliceStartedAt = Date.now();
    }
  }

  if (annotate) {
    zip.file("manifest.jsonl", annotationsToJsonl(manifest));
    zip.file(
      "README.txt",
      datasetReadme({
        boxes: dataset.boxes,
        count: done,
        degradation: dataset.degradation,
        format,
        generatedAt: new Date().toISOString(),
        pair: wrotePair,
        pdfMode: wantsPdf ? pdfMode : "n/a",
        planned: plan.length,
        words: dataset.words
      })
    );
  }

  const blob = await zip.generateAsync(
    { type: "blob", compression: "DEFLATE", compressionOptions: { level: 6 } },
    (metadata) => {
      onProgress({ done, total: done, phase: `zipping ${Math.round(metadata.percent)}%` });
    }
  );

  return { blob, count: done, stopped };
}
