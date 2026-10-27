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
 * Escape a string for a double-quoted HTML attribute value. It leaves single
 * quotes alone, so do not use it in single-quoted or unquoted attributes.
 * @param {string} value - Raw string to escape.
 * @returns {string} Escaped string for double-quoted attribute values.
 */
export function escapeAttribute(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
