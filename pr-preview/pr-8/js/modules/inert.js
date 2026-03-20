/** Mark an element as inert, saving its previous aria-hidden state. */
export function makeElementInert(element) {
  if (element.inert) {
    return;
  }

  element.dataset.prevAriaHidden = element.getAttribute('aria-hidden') ?? '';
  element.setAttribute('aria-hidden', 'true');
  element.inert = true;
}

/** Restore an element from inert state, reinstating its previous aria-hidden value. */
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

/** Toggle inert state on a list of background elements (e.g. when an overlay is open). */
export function setBackgroundContentInert(elements, isInert) {
  const updateInteractivity = isInert ? makeElementInert : restoreElementInteractivity;
  elements.forEach(updateInteractivity);
}
