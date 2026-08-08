/**
 * A tiny DOM stand-in for the paper renderer tests.
 *
 * The renderer only ever touches createElement, className, textContent,
 * appendChild, replaceChildren, and style.setProperty, so a handful of plain
 * objects is enough to assert on the tree it builds without pulling in jsdom.
 */

/**
 * Build a fake element node.
 * @param {string} tag - Tag name.
 * @returns {Record<string, any>} The node.
 */
export function createFakeElement(tag) {
  const properties = {};

  return {
    tagName: tag.toLowerCase(),
    className: '',
    textContent: '',
    children: [],
    style: {
      properties,
      setProperty(name, value) {
        properties[name] = value;
      },
      getPropertyValue(name) {
        return properties[name] ?? '';
      }
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
    createElement: (tag) => createFakeElement(tag)
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
