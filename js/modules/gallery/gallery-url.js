import { normalizeSelection, splitListParam } from './catalog.js';

export const DEFAULT_GALLERY_STATE = { page: 1, sort: 'newest', q: '' };

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
    q: (params.get('q') || defaults.q).toLowerCase(),
    sort: params.get('sort') === 'oldest' ? 'oldest' : defaults.sort,
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
