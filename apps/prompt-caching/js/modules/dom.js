/* Tiny DOM helpers shared by the interactive demos. Dynamic styles are set
 * through `element.style.*`; no inline `style="…"` markup is generated. */

/**
 * Look up an element by id. The id must exist in the page markup; the result
 * is not null-checked. Callers that touch subtype-specific members (an input
 * value, a canvas context) cast the result to the concrete element type.
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

/**
 * Adds hidden copies of every state to the live element's grid cell. The parent
 * carries `.reserve`, so the cell measures as the tallest state at the current width.
 * @param {HTMLElement} live - Element the demo updates, already inside a `.reserve` parent.
 * @param {HTMLElement[]} ghosts - One copy per state; each takes the live element's classes.
 * @returns {void}
 */
export function reserveSpace(live, ghosts) {
  const host = /** @type {HTMLElement} */ (live.parentNode);
  for (const ghost of ghosts) {
    ghost.classList.add("reserve-ghost");
    ghost.setAttribute("aria-hidden", "true");
    host.appendChild(ghost);
  }
}

/**
 * @param {string[]} texts - Candidate strings.
 * @returns {string} The longest one, which wraps onto the most lines.
 */
export function longestText(texts) {
  return texts.reduce((best, text) => (text.length > best.length ? text : best), "");
}

/* Re-exports the shared segmented-control wiring, including the aria-pressed sync. */
export { initSegmented } from "../../../../js/modules/segmented.js";
