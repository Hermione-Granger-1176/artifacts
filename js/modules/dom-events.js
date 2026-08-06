/**
 * DOM event target safety helpers shared by delegated event handlers.
 * @module dom-events
 */

/**
 * Safely call Element.closest() from a delegated event target.
 * @param {{ target?: EventTarget | null } | null | undefined} event - Event-like object.
 * @param {string} selector - CSS selector for the ancestor lookup.
 * @returns {Element | null} The closest matching element, when available.
 */
export function closest(event, selector) {
  if (!event) {
    return null;
  }

  const target = /** @type {{ closest?: (value: string) => Element | null } | null | undefined} */ (
    event.target
  );
  if (typeof target?.closest !== 'function') {
    return null;
  }

  return target.closest(selector);
}
