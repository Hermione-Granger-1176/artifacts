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

import { renderPdf } from "./pdf-render.js";

/**
 * @typedef {import("./document-model.js").DocumentModel} DocumentModel
 * @typedef {{
 *   documentObj?: Document,
 *   getHtml2Canvas: () => ArtifactsHtml2Canvas,
 *   getJsPdf: () => ArtifactsJsPdfConstructor,
 *   getJsZip: () => ArtifactsJsZipConstructor,
 *   windowObj?: Window & typeof globalThis
 * }} ExportDeps
 * @typedef {"pdf" | "png" | "both"} BatchFormat
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
 * Wrap a canvas into a single-page A4 PDF, producing the "scanned document"
 * look that image-based extraction pipelines need to be tested against.
 * @param {HTMLCanvasElement} canvas - Rasterised page.
 * @param {ExportDeps} deps - Injected library accessors.
 * @returns {ArtifactsJsPdfDocument} A PDF holding the image.
 */
export function canvasToPdf(canvas, deps) {
  const JsPdf = deps.getJsPdf();
  const doc = new JsPdf("p", "pt", "a4");
  const width = doc.internal.pageSize.getWidth();
  doc.addImage(canvas.toDataURL("image/png"), "PNG", 0, 0, width, canvas.height * (width / canvas.width));
  return doc;
}

/**
 * Build the PDF for a document in the requested mode.
 * @param {DocumentModel} model - Document to export.
 * @param {PdfMode} mode - `text` for a real text layer, `image` for a raster page.
 * @param {HTMLElement} paper - Rendered paper element, used by the image mode.
 * @param {ExportDeps} deps - Injected library accessors.
 * @returns {Promise<ArtifactsJsPdfDocument>} The finished PDF document.
 */
export async function buildPdf(model, mode, paper, deps) {
  if (mode === "text") {
    return renderPdf(model, deps.getJsPdf());
  }

  return canvasToPdf(await capturePaper(paper, deps), deps);
}

/**
 * Export the on-screen document as a PDF download.
 * @param {DocumentModel} model - Document to export.
 * @param {PdfMode} mode - PDF mode.
 * @param {HTMLElement} paper - Rendered paper element.
 * @param {ExportDeps} deps - Injected library accessors.
 * @returns {Promise<void>} Resolves once the download has been triggered.
 */
export async function downloadPdf(model, mode, paper, deps) {
  const doc = await buildPdf(model, mode, paper, deps);
  doc.save(`${model.filenameBase}.pdf`);
}

/**
 * Export the on-screen document as a PNG download.
 * @param {DocumentModel} model - Document to export.
 * @param {HTMLElement} paper - Rendered paper element.
 * @param {ExportDeps} deps - Injected library accessors.
 * @returns {Promise<void>} Resolves once the download has been triggered.
 */
export async function downloadPng(model, paper, deps) {
  const canvas = await capturePaper(paper, deps);
  triggerDownload(canvas.toDataURL("image/png"), `${model.filenameBase}.png`, deps);
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
 * Generate a batch of documents and hand back a foldered ZIP.
 *
 * Text PDFs skip the DOM entirely, which is why they are so much faster than
 * the raster paths: nothing is rendered or rasterised, jsPDF writes straight
 * from the model.
 * @param {{
 *   deps: ExportDeps,
 *   format: BatchFormat,
 *   onProgress?: (progress: { done: number, phase: string, total: number }) => void,
 *   paper: HTMLElement,
 *   pdfMode: PdfMode,
 *   plan: ReturnType<typeof planBatch>,
 *   renderPreview: (item: { docTypeId: string, seed: number, style: string, vendorId: string }) => DocumentModel
 * }} options - Batch inputs.
 * @returns {Promise<{ blob: Blob, count: number }>} The archive and how many documents it holds.
 */
export async function runBatch({ deps, format, onProgress = () => {}, paper, pdfMode, plan, renderPreview }) {
  const JsZip = deps.getJsZip();
  const zip = new JsZip();
  const wantsPng = format === "png" || format === "both";
  const wantsPdf = format === "pdf" || format === "both";
  const wantsCanvas = wantsPng || (wantsPdf && pdfMode === "image");
  let done = 0;

  for (const item of plan) {
    const model = renderPreview(item);
    const base = `${item.vendorId}/${item.docTypeId}/${model.filenameBase}`;

    if (wantsPdf && pdfMode === "text") {
      zip.file(`${base}.pdf`, renderPdf(model, deps.getJsPdf()).output("blob"));
    }

    if (wantsCanvas) {
      // Sequential on purpose: one shared paper element is reused for every
      // capture, so the renders cannot overlap.
      const canvas = await capturePaper(paper, deps);

      if (wantsPng) {
        zip.file(`${base}.png`, canvas.toDataURL("image/png").split(",")[1], { base64: true });
      }

      if (wantsPdf && pdfMode === "image") {
        zip.file(`${base}.pdf`, canvasToPdf(canvas, deps).output("blob"));
      }
    }

    done += 1;
    onProgress({ done, total: plan.length, phase: "generating" });
  }

  const blob = await zip.generateAsync(
    { type: "blob", compression: "DEFLATE", compressionOptions: { level: 6 } },
    (metadata) => {
      onProgress({ done: plan.length, total: plan.length, phase: `zipping ${Math.round(metadata.percent)}%` });
    }
  );

  return { blob, count: plan.length };
}
