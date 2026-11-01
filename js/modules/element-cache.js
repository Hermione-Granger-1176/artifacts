/**
 * Look up each ID once and return the elements in a plain object keyed by ID.
 * @param {string[]} ids - Element IDs to look up.
 * @param {Document} [documentObj=document] - Document to query.
 * @returns {Object<string, HTMLElement|null>} Object mapping each id to its element, or null when no element has that id.
 */
export function cacheElements(ids, documentObj = document) {
  return Object.fromEntries(
    ids.map((id) => [id, documentObj.getElementById(id)])
  );
}
