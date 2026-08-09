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

import { project } from "./degrade.js";

/**
 * @typedef {import("./degrade.js").Matrix3} Matrix3
 * @typedef {[x: number, y: number, width: number, height: number]} NormalisedBox
 * @typedef {[number, number, number, number, number, number, number, number]} Quad
 * @typedef {{ box: NormalisedBox, quad?: Quad, text: string }} WordBox
 * @typedef {{ box: NormalisedBox, field: string, quad?: Quad, text: string, words?: WordBox[] }} Region
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
 * Union normalised boxes into the smallest box containing all of them.
 * @param {NormalisedBox[]} boxes - Boxes to merge.
 * @returns {NormalisedBox} Bounding box.
 */
function unionBoxes(boxes) {
  const factor = 10 ** PRECISION;
  const left = Math.floor(Math.min(...boxes.map(([x]) => x)) * factor) / factor;
  const top = Math.floor(Math.min(...boxes.map(([, y]) => y)) * factor) / factor;
  const right = Math.ceil(Math.max(...boxes.map(([x, , width]) => x + width)) * factor) / factor;
  const bottom =
    Math.ceil(Math.max(...boxes.map(([, y, , height]) => y + height)) * factor) / factor;
  return [round(left), round(top), round(right - left), round(bottom - top)];
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
      if (region.words.length) {
        // Chromium can report a text Range that extends slightly beyond its
        // element's layout box for some font metrics. A labelled region must
        // contain the ink-level word boxes on every browser version.
        region.box = unionBoxes([region.box, ...region.words.map((word) => word.box)]);
      }
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

/**
 * Whether a transform would leave every box exactly where it is.
 * @param {Matrix3} matrix - Candidate transform.
 * @returns {boolean} True for the identity.
 */
function isIdentity(matrix) {
  return matrix.every((row, y) => row.every((value, x) => value === (x === y ? 1 : 0)));
}

/**
 * Move one box through a transform.
 *
 * The result carries both shapes on purpose. `box` stays an axis-aligned
 * `[x, y, width, height]` so an evaluation script written against a clean run
 * keeps working unchanged against a degraded one; `quad` carries the four
 * corners the ink actually landed on, which is what a rotated page really looks
 * like and what a polygon-aware consumer wants. Reporting only the quad would
 * break every existing reader; reporting only the box would silently claim a
 * tilted value is upright.
 * @param {NormalisedBox} box - Box before the transform.
 * @param {Matrix3} matrix - Transform in normalised page coordinates.
 * @returns {{ box: NormalisedBox, quad: Quad }} Bounding box and exact corners.
 */
function warpBox([x, y, width, height], matrix) {
  const corners = [
    [x, y],
    [x + width, y],
    [x + width, y + height],
    [x, y + height]
  ].map(([pointX, pointY]) => project(matrix, pointX, pointY));
  const xs = corners.map((corner) => corner[0]);
  const ys = corners.map((corner) => corner[1]);
  const left = Math.min(...xs);
  const top = Math.min(...ys);

  return {
    box: [round(left), round(top), round(Math.max(...xs) - left), round(Math.max(...ys) - top)],
    quad: /** @type {Quad} */ (corners.flat().map(round))
  };
}

/**
 * Move every box on a page through a transform.
 *
 * Called with whatever geometry the degradation pass applied, so the labels
 * describe the image that was actually written rather than the clean render it
 * started from. This is the join between phases 2 and 3: skew, rotation, and
 * keystone move the ink, and without this the boxes would keep pointing at
 * where the ink used to be.
 * @param {BoxAnnotations | null} boxes - Boxes measured on the clean page.
 * @param {Matrix3} matrix - Transform in normalised page coordinates.
 * @returns {BoxAnnotations | null} Transformed boxes, or the input untouched.
 */
export function transformBoxes(boxes, matrix) {
  if (!boxes || isIdentity(matrix)) {
    return boxes;
  }

  return {
    page: boxes.page,
    regions: boxes.regions.map((region) => {
      const moved = { ...region, ...warpBox(region.box, matrix) };

      if (region.words) {
        moved.words = region.words.map((word) => ({ ...word, ...warpBox(word.box, matrix) }));
      }

      return moved;
    })
  };
}
