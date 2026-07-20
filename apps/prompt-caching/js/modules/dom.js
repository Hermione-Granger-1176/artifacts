/* Tiny DOM helpers shared by the interactive demos. Kept free of inline style
 * strings: dynamic styling is applied through the CSSOM (`element.style.*`),
 * which the strict `style-src 'self'` CSP permits, unlike `style="…"` markup. */

/**
 * Look up an element by id. The interactive demos only run against their own
 * markup, where every queried id is present, so the result is treated as
 * non-null. Callers that touch subtype-specific members (an input value, a
 * canvas context) cast the result to the concrete element type.
 * @param {string} id - Element id to resolve.
 * @returns {HTMLElement} The resolved element.
 */
export function byId(id) {
  return /** @type {HTMLElement} */ (document.getElementById(id));
}

/**
 * @param {string} tag - Element tag name.
 * @param {string} [className] - Optional class name.
 * @param {string} [text] - Optional text content.
 * @returns {HTMLElement} The created element.
 */
export function makeEl(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text !== "") {
    node.textContent = text;
  }
  return node;
}

/** @param {Element} node - Element to empty. */
export function clear(node) {
  node.replaceChildren();
}

/* Segmented-control wiring now lives in the shared module so every artifact app
 * (and its aria-pressed sync) draws from one source. Re-exported here so the
 * prompt-caching demos keep importing it from their local dom module. */
export { initSegmented } from "../../../../js/modules/segmented.js";
