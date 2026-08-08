/**
 * A tiny DOM stand-in for the paper renderer and box annotator tests.
 *
 * The renderer touches createElement, className, textContent, setAttribute,
 * appendChild, replaceChildren, and style.setProperty. The box annotator adds
 * querySelectorAll, getBoundingClientRect, childNodes, and a Range. That is
 * still a small enough surface that plain objects beat pulling in jsdom, and it
 * keeps the tests honest about exactly which DOM features the modules rely on.
 *
 * Geometry is faked deterministically by `layOut` rather than measured: nodes
 * are stacked down the page in document order. It is not a browser's layout,
 * and it is not meant to be. What it exercises is the arithmetic, the walk, and
 * the normalisation. Whether the real numbers land on the real ink is settled
 * in `tests/browser/`, against a real page.
 */

/** DOM node type for a text node. */
const TEXT_NODE = 3;

/**
 * Build a fake element node.
 * @param {string} tag - Tag name.
 * @returns {Record<string, any>} The node.
 */
export function createFakeElement(tag) {
  const properties = {};
  /** @type {Record<string, string>} */
  const attributes = {};

  return {
    tagName: tag.toLowerCase(),
    className: '',
    textContent: '',
    children: [],
    attributes,
    offsetWidth: 0,
    offsetHeight: 0,
    rect: { left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 },
    style: {
      properties,
      setProperty(name, value) {
        properties[name] = value;
      },
      getPropertyValue(name) {
        return properties[name] ?? '';
      }
    },
    setAttribute(name, value) {
      attributes[name] = String(value);
    },
    getAttribute(name) {
      return Object.hasOwn(attributes, name) ? attributes[name] : null;
    },
    getBoundingClientRect() {
      return this.rect;
    },
    // A node either carries text or carries children in this renderer, never
    // both, so a text node is synthesised on demand rather than stored.
    get childNodes() {
      if (this.children.length) {
        return this.children;
      }

      return this.textContent
        ? [{ nodeType: TEXT_NODE, textContent: this.textContent, parentElement: this }]
        : [];
    },
    querySelectorAll(selector) {
      if (selector !== '[data-field]') {
        throw new Error(`fake querySelectorAll only supports [data-field], got ${selector}`);
      }

      return flatten(this)
        .slice(1)
        .filter((node) => node.getAttribute?.('data-field') !== null);
    },
    appendChild(child) {
      this.children.push(child);
      return child;
    },
    replaceChildren(...nodes) {
      this.children = nodes;
    }
  };
}

/**
 * Build a fake document whose createElement returns fake elements.
 * @returns {Record<string, any>} The document.
 */
export function createFakeDocument() {
  return {
    createElement: (tag) => createFakeElement(tag),
    createRange: () => createFakeRange()
  };
}

/**
 * A Range stand-in that reports geometry for a slice of a text node.
 *
 * Character widths are uniform, so a word's rect is its share of the owning
 * element's box. Crude, and enough to prove the annotator slices the right
 * substrings and normalises each one against the page.
 * @returns {Record<string, any>} The range.
 */
function createFakeRange() {
  let node = null;
  let start = 0;
  let end = 0;

  return {
    setStart(textNode, offset) {
      node = textNode;
      start = offset;
    },
    setEnd(textNode, offset) {
      node = textNode;
      end = offset;
    },
    getClientRects() {
      const owner = node?.parentElement;
      const length = String(node?.textContent ?? '').length;

      if (!owner || !length) {
        return [];
      }

      const perChar = owner.rect.width / length;
      const left = owner.rect.left + start * perChar;
      const width = (end - start) * perChar;

      return [
        {
          left,
          top: owner.rect.top,
          right: left + width,
          bottom: owner.rect.top + owner.rect.height,
          width,
          height: owner.rect.height
        }
      ];
    }
  };
}

/**
 * Walk a fake node tree depth-first.
 * @param {Record<string, any>} node - Root node.
 * @returns {Record<string, any>[]} Every node including the root.
 */
function flatten(node) {
  return [node, ...node.children.flatMap((child) => flatten(child))];
}

/**
 * Give every node in a tree a plausible rect.
 *
 * Text-bearing nodes are stacked down the page in document order at a fixed
 * line height; containers span from their first descendant to their last.
 * @param {Record<string, any>} root - Tree to lay out.
 * @param {{ lineHeight?: number, pageHeight?: number, pageWidth?: number }} [options={}] - Page geometry.
 * @returns {Record<string, any>} The same root, measured.
 */
export function layOut(root, { lineHeight = 14, pageHeight = 1123, pageWidth = 794 } = {}) {
  let cursor = 0;

  /**
   * @param {Record<string, any>} node - Node to measure.
   * @returns {{ bottom: number, left: number, right: number, top: number }} Its box.
   */
  function measure(node) {
    if (!node.children.length) {
      const top = cursor;
      cursor += lineHeight;
      const width = Math.min(pageWidth, Math.max(1, String(node.textContent).length * 6));
      node.rect = { left: 0, top, right: width, bottom: top + lineHeight, width, height: lineHeight };
      return node.rect;
    }

    const boxes = node.children.map((child) => measure(child));
    const left = Math.min(...boxes.map((box) => box.left));
    const top = Math.min(...boxes.map((box) => box.top));
    const right = Math.max(...boxes.map((box) => box.right));
    const bottom = Math.max(...boxes.map((box) => box.bottom));
    node.rect = { left, top, right, bottom, width: right - left, height: bottom - top };
    return node.rect;
  }

  measure(root);
  root.rect = { left: 0, top: 0, right: pageWidth, bottom: pageHeight, width: pageWidth, height: pageHeight };
  root.offsetWidth = pageWidth;
  root.offsetHeight = pageHeight;
  return root;
}

/**
 * Collect every node carrying a class.
 * @param {Record<string, any>} node - Root node.
 * @param {string} className - Class to match, as a whole word.
 * @returns {Record<string, any>[]} Matching nodes.
 */
export function findByClass(node, className) {
  return flatten(node).filter((candidate) =>
    String(candidate.className).split(/\s+/).includes(className)
  );
}

/**
 * Collect every node with a given tag name.
 * @param {Record<string, any>} node - Root node.
 * @param {string} tag - Tag name to match.
 * @returns {Record<string, any>[]} Matching nodes.
 */
export function findByTag(node, tag) {
  return flatten(node).filter((candidate) => candidate.tagName === tag);
}

/**
 * Collect every node tagged with a ground-truth field.
 * @param {Record<string, any>} node - Root node.
 * @returns {Record<string, any>[]} Matching nodes, in document order.
 */
export function findTagged(node) {
  return flatten(node).filter((candidate) => candidate.getAttribute?.('data-field') !== null);
}

/**
 * Concatenate all text in a subtree, in document order.
 * @param {Record<string, any>} node - Root node.
 * @returns {string} Space-joined text.
 */
export function textOf(node) {
  return flatten(node)
    .map((candidate) => candidate.textContent)
    .filter(Boolean)
    .join(' ');
}
