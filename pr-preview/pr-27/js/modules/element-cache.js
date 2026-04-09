/**
 * Cache DOM elements by ID.
 * @param {string[]} ids - Element IDs to look up.
 * @param {Document} [documentObj=document] - Document to query.
 * @returns {Object<string, HTMLElement|null>} Map of id to element (or null if not found).
 */
export function cacheElements(ids, documentObj = document) {
  return Object.fromEntries(
    ids.map((id) => [id, documentObj.getElementById(id)])
  );
}
