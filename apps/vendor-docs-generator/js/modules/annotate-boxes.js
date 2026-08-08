/**
 * Reads the rendered page back and reports where each labelled value sits.
 *
 * The paper renderer stamps `data-field` onto every node that carries a
 * ground-truth value, so this module is a measurement pass and nothing more: it
 * walks those nodes, takes their rects, and expresses each one relative to the
 * page. No layout knowledge lives here, which is why a new block type in the
 * renderer needs no change in this file.
 *
 * Coordinates are normalised to the 0..1 page box rather than reported in
 * pixels. Normalised coordinates survive the preview's fit-to-frame transform,
 * the export's 2x capture scale, and any future change to the page dimensions,
 * so a consumer multiplies by whatever image size they actually have and never
 * has to know what those three happened to be.
 *
 * The honest caveat, recorded on every payload rather than buried here: these
 * boxes are measured on the HTML page, so they describe the PNG and the
 * rasterised PDF. They do not describe the text-layer PDF, which jsPDF lays out
 * independently in its own coordinate system.
 *
 * @module annotate-boxes
 */

/**
 * @typedef {[x: number, y: number, width: number, height: number]} NormalisedBox
 * @typedef {{ box: NormalisedBox, text: string }} WordBox
 * @typedef {{ box: NormalisedBox, field: string, text: string, words?: WordBox[] }} Region
 * @typedef {{
 *   page: { height: number, unit: "normalised", width: number },
 *   regions: Region[]
 * }} BoxAnnotations
 */

/** Where DOM-measured boxes are valid, recorded alongside the boxes themselves. */
export const BOXES_APPLY_TO = ["png", "pdf_raster"];

/** Decimal places kept per coordinate; four is sub-pixel on any plausible page. */
const PRECISION = 4;

/** DOM node type for a text node. */
const TEXT_NODE = 3;

/**
 * Round a coordinate to the stored precision.
 * @param {number} value - Raw normalised coordinate.
 * @returns {number} Rounded coordinate.
 */
function round(value) {
  const factor = 10 ** PRECISION;
  return Math.round(value * factor) / factor;
}

/**
 * Express a rect relative to the page box, as fractions of the page.
 * @param {{ height: number, left: number, top: number, width: number }} rect - Measured rect.
 * @param {{ height: number, left: number, top: number, width: number }} page - Page rect.
 * @returns {NormalisedBox} Box as `[x, y, width, height]` in 0..1 page units.
 */
function normalise(rect, page) {
  // A detached or zero-height page would otherwise divide by zero and fill the
  // payload with Infinity. Falling back to 1 keeps the numbers finite and makes
  // the degenerate case obvious instead of poisonous.
  const pageWidth = page.width || 1;
  const pageHeight = page.height || 1;

  return [
    round((rect.left - page.left) / pageWidth),
    round((rect.top - page.top) / pageHeight),
    round(rect.width / pageWidth),
    round(rect.height / pageHeight)
  ];
}

/**
 * Union a list of rects into the smallest box containing all of them.
 * @param {{ bottom: number, left: number, right: number, top: number }[]} rects - Rects to merge.
 * @returns {{ height: number, left: number, top: number, width: number }} Bounding rect.
 */
function unionRects(rects) {
  const left = Math.min(...rects.map((rect) => rect.left));
  const top = Math.min(...rects.map((rect) => rect.top));
  const right = Math.max(...rects.map((rect) => rect.right));
  const bottom = Math.max(...rects.map((rect) => rect.bottom));
  return { left, top, width: right - left, height: bottom - top };
}

/**
 * Collect the text nodes under an element, in document order.
 * @param {Node} node - Root to walk.
 * @returns {Node[]} Text nodes.
 */
function textNodesIn(node) {
  const children = Array.from(node.childNodes ?? []);

  if (!children.length) {
    return [];
  }

  return children.flatMap((child) =>
    child.nodeType === TEXT_NODE ? [child] : textNodesIn(child)
  );
}

/**
 * Measure each whitespace-separated word inside one labelled element.
 *
 * A `Range` over the text node is the only way to get per-word geometry without
 * wrapping every word in a span, which would change how the browser lays the
 * line out and so change the very thing being measured.
 * @param {Element} element - Labelled element.
 * @param {{ height: number, left: number, top: number, width: number }} page - Page rect.
 * @param {Document} doc - Owning document.
 * @returns {WordBox[]} One entry per word that produced a rect.
 */
function wordBoxes(element, page, doc) {
  const range = doc.createRange();
  /** @type {WordBox[]} */
  const words = [];

  for (const textNode of textNodesIn(element)) {
    const text = textNode.textContent ?? "";
    const pattern = /\S+/g;
    let match = pattern.exec(text);

    while (match !== null) {
      range.setStart(textNode, match.index);
      range.setEnd(textNode, match.index + match[0].length);
      const rects = Array.from(range.getClientRects());

      if (rects.length) {
        words.push({ text: match[0], box: normalise(unionRects(rects), page) });
      }

      match = pattern.exec(text);
    }
  }

  return words;
}

/**
 * Measure every labelled value on a rendered page.
 *
 * A field printed in more than one place produces more than one region, in
 * document order. That is deliberate: a two-line address genuinely occupies two
 * boxes, and merging them would claim a single box covering the gap between
 * them that no ink ever lands in.
 * @param {HTMLElement} paper - The rendered `.vd-paper` element.
 * @param {{ doc?: Document, words?: boolean }} [options={}] - Measurement options.
 * @returns {BoxAnnotations} Page dimensions and one region per labelled node.
 */
export function collectBoxes(paper, { doc = document, words = false } = {}) {
  const page = paper.getBoundingClientRect();
  /** @type {Region[]} */
  const regions = [];

  for (const element of Array.from(paper.querySelectorAll("[data-field]"))) {
    const field = element.getAttribute("data-field");

    if (!field) {
      continue;
    }

    const rect = element.getBoundingClientRect();
    /** @type {Region} */
    const region = {
      field,
      text: (element.textContent ?? "").trim(),
      box: normalise(rect, page)
    };

    if (words) {
      region.words = wordBoxes(element, page, doc);
    }

    regions.push(region);
  }

  return {
    // The page is reported at its own layout size, not at whatever scale the
    // preview happens to be showing. `offsetWidth` ignores CSS transforms,
    // which is exactly why it is read here and the rect is not.
    page: {
      width: paper.offsetWidth || Math.round(page.width),
      height: paper.offsetHeight || Math.round(page.height),
      unit: "normalised"
    },
    regions
  };
}
