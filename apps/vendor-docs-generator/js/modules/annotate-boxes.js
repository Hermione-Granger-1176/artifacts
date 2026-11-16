/**
 * Reads the rendered page back and reports where each labelled value sits.
 *
 * The paper renderer stamps `data-field` onto every node that carries a
 * ground-truth value, so this module is a measurement pass and nothing more: it
 * walks those nodes, takes their rects, and expresses each one relative to the
 * page. No layout knowledge lives here, so a new block type in the renderer
 * needs no change in this file.
 *
 * Coordinates are normalised to the 0..1 page box rather than reported in
 * pixels. A consumer multiplies by the size of the image it has. The preview's
 * fit-to-frame transform and the export's capture scale do not change the values.
 *
 * These boxes are measured on the HTML page, so they describe the PNG and the
 * rasterised PDF. They do not describe the text-layer PDF, which jsPDF lays out
 * independently in its own coordinate system. `boxes_apply_to` records this on
 * every payload.
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

/** Decimal places kept per coordinate. */
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
  return [
    round((rect.left - page.left) / page.width),
    round((rect.top - page.top) / page.height),
    round(rect.width / page.width),
    round(rect.height / page.height)
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
  const children = Array.from(node.childNodes);
  return children.flatMap((child) =>
    child.nodeType === TEXT_NODE ? [child] : textNodesIn(child)
  );
}

/**
 * Measure each whitespace-separated word inside one labelled element.
 *
 * Each word is measured with a `Range` over its text node, so the text is not
 * wrapped in extra elements.
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
    const text = /** @type {string} */ (textNode.textContent);
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
 * document order. Each printed place keeps its own box.
 *
 * A page that is not rendered (detached, `display: none`, or inside a hidden
 * frame) measures 0 x 0, and so does every node on it. The function throws in
 * that case instead of returning boxes.
 * @param {HTMLElement} paper - The rendered `.vd-paper` element.
 * @param {{ doc?: Document, words?: boolean }} [options={}] - Measurement options.
 * @returns {BoxAnnotations} Page dimensions and one region per labelled node.
 * @throws {Error} When the page has no rendered size.
 */
export function collectBoxes(paper, { doc = document, words = false } = {}) {
  const page = paper.getBoundingClientRect();

  if (!(page.width > 0 && page.height > 0)) {
    throw new Error(
      "The document preview is not on screen, so its label boxes cannot be measured. Show the preview and export again."
    );
  }

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
      text: /** @type {string} */ (element.textContent).trim(),
      box: normalise(rect, page)
    };

    if (words) {
      region.words = wordBoxes(element, page, doc);
      if (region.words.length) {
        // Extend the region to contain every word box. A text Range can extend
        // past the element's layout box.
        region.box = unionBoxes([region.box, ...region.words.map((word) => word.box)]);
      }
    }

    regions.push(region);
  }

  return {
    // The page is reported at its layout size, not at the preview's scale.
    // `offsetWidth` ignores CSS transforms.
    page: {
      width: paper.offsetWidth,
      height: paper.offsetHeight,
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
 * The result has two shapes. `box` is the axis-aligned `[x, y, width, height]`
 * bounding box of the transformed corners. `quad` holds those four corners in
 * the order top-left, top-right, bottom-right, bottom-left of the input box.
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
 * Called with the geometry the degradation pass applied, so the boxes describe
 * the written image rather than the clean render. Skew, rotation, and keystone
 * move the ink.
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
