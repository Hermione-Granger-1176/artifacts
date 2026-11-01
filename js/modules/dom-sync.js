/**
 * Shared helpers for updating existing DOM nodes in place. Skipping writes
 * when the value is unchanged avoids needless mutations and style
 * invalidation on every input tick.
 * @module dom-sync
 */

/**
 * Set an element's text only when it differs from the current text.
 *
 * @param {Element} element
 * @param {string} text
 * @returns {void}
 */
export function setText(element, text) {
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
