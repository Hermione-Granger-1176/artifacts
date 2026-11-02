import { normalizeSelection, splitListParam } from './catalog.js';

// The gallery data has no creation dates (every app shares one import commit),
// so the order is by name: 'az' (the default) or 'za'.
export const DEFAULT_GALLERY_STATE = { page: 1, sort: 'az', q: '' };

/**
 * Normalize a search query for matching. Matching is case-insensitive, and
 * surrounding whitespace never changes the results, so " chart " and "Chart"
 * are the same search and a box of spaces is no search at all.
 * @param {string} value - Raw query text.
 * @returns {string} Trimmed, lower-case query.
 */
export function normalizeSearchQuery(value) {
  return value.trim().toLowerCase();
}

/**
 * Parse URL search params into normalized gallery state.
 * @param {{
 *   search: string,
 *   allTools: string[],
 *   allTags: string[],
 *   defaults?: { page: number, sort: string, q: string }
 * }} options - URL search input and allowed gallery values.
 * @returns {{
 *   page: number,
 *   q: string,
 *   sort: string,
 *   tools: string[],
 *   tags: string[],
 *   rawQuery: string
 * }} Normalized gallery state.
 */
export function readGalleryStateFromSearch({
  search,
  allTools,
  allTags,
  defaults = DEFAULT_GALLERY_STATE
}) {
  const params = new URLSearchParams(search);
  return {
    page: Math.max(1, Number.parseInt(params.get('page') || '', 10) || defaults.page),
    q: normalizeSearchQuery(params.get('q') || defaults.q),
    // A pre-rename `sort=oldest` link listed A to Z, which is now the default.
    sort: params.get('sort') === 'za' ? 'za' : defaults.sort,
    tools: normalizeSelection(splitListParam(params.get('tool')), allTools),
    tags: normalizeSelection(splitListParam(params.get('tag')), allTags),
    rawQuery: params.get('q') || ''
  };
}

/**
 * Serialize gallery state into a URL path with query string.
 * @param {{
 *   pathname: string,
 *   page: number,
 *   sort: string,
 *   q: string,
 *   tools: string[],
 *   tags: string[],
 *   defaults?: { page: number, sort: string, q: string }
 * }} options - Current gallery state values.
 * @returns {string} URL path with any non-default query parameters.
 */
export function buildGalleryUrl({
  pathname,
  page,
  sort,
  q,
  tools,
  tags,
  defaults = DEFAULT_GALLERY_STATE
}) {
  const params = new URLSearchParams();
  if (page > 1) {
    params.set('page', String(page));
  }
  if (tools.length > 0) {
    params.set('tool', tools.join(','));
  }
  if (tags.length > 0) {
    params.set('tag', tags.join(','));
  }
  if (sort !== defaults.sort) {
    params.set('sort', sort);
  }
  if (q) {
    params.set('q', q);
  }

  const queryString = params.toString();
  return queryString ? `${pathname}?${queryString}` : pathname;
}
