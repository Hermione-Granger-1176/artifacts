/**
 * Shared HTML escaping utilities for safe content and attribute insertion.
 * @module html-escape
 */

/**
 * Escape text for safe HTML content insertion.
 * @param {string|number|null|undefined} unsafe - Raw value to escape.
 * @returns {string} Escaped string safe for HTML templates.
 */
export function escapeHtml(unsafe) {
  if (unsafe == null) {
    return '';
  }

  return String(unsafe)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Escape a string for safe use in an HTML attribute value.
 * @param {string} value - Raw string to escape.
 * @returns {string} Escaped string safe for attribute contexts.
 */
export function escapeAttribute(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
