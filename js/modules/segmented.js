/**
 * Shared segmented-control wiring for artifact apps.
 * @module segmented
 */

/**
 * Wire a segmented toggle. Clicking a button inside `container` makes it the
 * lone `.active` button, syncs `aria-pressed` across the group, and calls
 * `onSelect(button)`. `aria-pressed` is synced once on init to match the
 * current active state, then again on every click, so `.active` stays the
 * source of truth and the ARIA state follows it for free.
 * @param {HTMLElement} container - Element wrapping the toggle buttons.
 * @param {Function} onSelect - Called with the newly active button element.
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
