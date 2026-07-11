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

export function cssVar(name) {
  return getComputedStyle(document.body).getPropertyValue(name).trim();
}

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

export function clear(node) {
  node.replaceChildren();
}

/* Wire a segmented toggle: clicking a <button> inside `container` makes it the
 * lone `.active` button and calls `onSelect(button)`. Returns the buttons. */
export function initSegmented(container, onSelect) {
  const buttons = Array.from(container.querySelectorAll("button"));
  for (const btn of buttons) {
    btn.addEventListener("click", () => {
      for (const other of buttons) {
        other.classList.toggle("active", other === btn);
      }
      onSelect(btn);
    });
  }
  return buttons;
}
