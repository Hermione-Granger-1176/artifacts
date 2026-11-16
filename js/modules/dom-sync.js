/**
 * Shared helpers for updating existing DOM nodes in place. Writes are skipped
 * when the value is unchanged.
 * @module dom-sync
 */

/** Node.TEXT_NODE value, defined locally. The module does not depend on the global Node. */
const TEXT_NODE = 3;

/**
 * Set an element's text only when it differs from the current text.
 *
 * @param {Element} element
 * @param {string} text
 * @returns {void}
 */
export function setText(element, text) {
  // A lone text node is rewritten in place instead of replaced through textContent.
  const node = element.firstChild;
  if (text !== "" && node && node === element.lastChild && node.nodeType === TEXT_NODE) {
    const textNode = /** @type {Text} */ (node);
    if (textNode.data !== text) {
      textNode.data = text;
    }
    return;
  }
  if (element.textContent !== text) {
    element.textContent = text;
  }
}

/**
 * Set an attribute only when it differs from the current value.
 *
 * @param {Element} element
 * @param {string} name
 * @param {string} value
 * @returns {void}
 */
export function setAttr(element, name, value) {
  if (element.getAttribute(name) !== value) {
    element.setAttribute(name, value);
  }
}

/** Elements whose first value has already been written. */
const settledElements = new WeakSet();

/**
 * Writes an element's first value with its CSS transition disabled. The
 * element's own inline transition, if any, is restored two frames later, once
 * that value has been styled. Later changes animate as usual. Call it before
 * each write; only the first call per element does anything.
 *
 * @param {HTMLElement} element
 * @returns {void}
 */
export function skipFirstTransition(element) {
  if (settledElements.has(element)) {
    return;
  }
  settledElements.add(element);
  const inlineTransition = element.style.transition;
  element.style.transition = "none";
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      element.style.transition = inlineTransition;
    });
  });
}

/**
 * Create an element, optionally setting its class, text, attributes, and
 * children. `text` is assigned as `textContent`, never parsed as HTML.
 *
 * @param {string} tag
 * @param {{ className?: string, text?: string, attrs?: Record<string, string> }} [props]
 * @param {Array<Node>} [children]
 * @returns {HTMLElement}
 */
export function createElement(tag, { className, text, attrs } = {}, children = []) {
  const element = document.createElement(tag);
  if (className) {
    element.className = className;
  }
  if (text !== undefined) {
    element.textContent = text;
  }
  for (const [name, value] of Object.entries(attrs ?? {})) {
    element.setAttribute(name, value);
  }
  if (children.length > 0) {
    element.append(...children);
  }
  return element;
}
