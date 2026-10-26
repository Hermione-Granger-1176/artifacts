/**
 * Shared helpers for updating existing DOM nodes in place. Writing only when a
 * value changed keeps focus, hover, and layout stable between input ticks.
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
 * Create an element with a class name, attributes, and children.
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
