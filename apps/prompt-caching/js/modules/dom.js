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

/**
 * Whether the visitor asked the system for reduced motion. Timed step-by-step
 * demos jump straight to their final state when it is set.
 * @returns {boolean} True when `prefers-reduced-motion: reduce` matches.
 */
export function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Reserve the largest box a changing element can ever need, so swapping its
 * content never moves what sits below it. Hidden copies of every state share the
 * live element's grid cell (its parent carries `.reserve`), so the cell
 * always measures as the tallest state at the current width.
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

/* Segmented-control wiring now lives in the shared module so every artifact app
 * (and its aria-pressed sync) draws from one source. Re-exported here so the
 * prompt-caching demos keep importing it from their local dom module. */
export { initSegmented } from "../../../../js/modules/segmented.js";
