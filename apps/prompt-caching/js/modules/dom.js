/* Tiny DOM helpers shared by the interactive demos. Kept free of inline style
 * strings: dynamic styling is applied through the CSSOM (`element.style.*`),
 * which the strict `style-src 'self'` CSP permits, unlike `style="…"` markup. */

export function byId(id) {
  return document.getElementById(id);
}

export function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
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
