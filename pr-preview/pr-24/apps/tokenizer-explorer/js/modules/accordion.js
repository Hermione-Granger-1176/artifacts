/**
 * Bind click-to-toggle accordion behavior for tokenizer concept cards.
 *
 * @param {HTMLElement} container
 * @returns {void}
 */
export function initAccordion(container) {
  container.addEventListener("click", (event) => {
    const trigger = event.target.closest(".card-trigger");
    if (!trigger) {
      return;
    }

    const card = trigger.closest(".card");
    if (!card) {
      return;
    }

    const isOpen = card.classList.toggle("open");
    trigger.setAttribute("aria-expanded", String(isOpen));
  });
}
