/**
 * Bind click-to-toggle accordion behavior for tokenizer concept cards.
 *
 * @param {HTMLElement} container
 * @returns {void}
 */
export function initAccordion(container) {
  container.addEventListener("click", (event) => {
    const trigger = /** @type {Element} */ (event.target).closest(".card-trigger");
    if (!trigger) {
      return;
    }

    // Every trigger in index.html sits directly inside its .card.
    const card = /** @type {Element} */ (trigger.closest(".card"));
    const isOpen = card.classList.toggle("open");
    trigger.setAttribute("aria-expanded", String(isOpen));
  });
}
