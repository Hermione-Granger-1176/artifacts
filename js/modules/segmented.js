/**
 * Shared segmented-control wiring for artifact apps.
 * @module segmented
 */

/**
 * Wire a segmented toggle. Clicking a button inside `container` makes it the
 * only `.active` button, sets `aria-pressed` on every button to match, and
 * calls `onSelect(button)`. On init, `aria-pressed` is also synced from the
 * markup's `.active` classes.
 * @param {HTMLElement} container - Element wrapping the toggle buttons.
 * @param {(button: HTMLButtonElement) => void} onSelect - Called with the newly active button element.
 * @returns {HTMLButtonElement[]} The buttons found inside the container.
 */
export function initSegmented(container, onSelect) {
  const buttons = Array.from(container.querySelectorAll("button"));

  const syncPressed = () => {
    for (const button of buttons) {
      button.setAttribute(
        "aria-pressed",
        button.classList.contains("active") ? "true" : "false"
      );
    }
  };

  syncPressed();

  for (const button of buttons) {
    button.addEventListener("click", () => {
      for (const other of buttons) {
        other.classList.toggle("active", other === button);
      }
      syncPressed();
      onSelect(button);
    });
  }

  return buttons;
}
