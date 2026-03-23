/**
 * Mark an element as inert and preserve its prior ``aria-hidden`` state.
 * @param {HTMLElement} element - Element to disable for interaction.
 * @returns {void}
 */
export function makeElementInert(element) {
  if (element.inert) {
    return;
  }

  element.dataset.prevAriaHidden = element.getAttribute('aria-hidden') ?? '';
  element.setAttribute('aria-hidden', 'true');
  element.inert = true;
}

/**
 * Restore an element from inert state.
 * @param {HTMLElement} element - Element to restore for interaction.
 * @returns {void}
 */
export function restoreElementInteractivity(element) {
  if (!element.inert) {
    return;
  }

  if (element.dataset.prevAriaHidden === '') {
    element.removeAttribute('aria-hidden');
  } else {
    element.setAttribute('aria-hidden', element.dataset.prevAriaHidden);
  }

  delete element.dataset.prevAriaHidden;
  element.inert = false;
}

/**
 * Toggle inert state on a list of background elements.
 * @param {HTMLElement[]} elements - Background elements to update.
 * @param {boolean} isInert - Whether the elements should be inert.
 * @returns {void}
 */
export function setBackgroundContentInert(elements, isInert) {
  const updateInteractivity = isInert ? makeElementInert : restoreElementInteractivity;
  elements.forEach(updateInteractivity);
}
