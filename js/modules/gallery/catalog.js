/**
 * @typedef {{
 *   id: string,
 *   name: string,
 *   description?: string | null,
 *   tags: string[],
 *   tools: string[],
 *   url: string,
 *   thumbnail?: string | null,
 *   searchText?: string
 * }} ArtifactRecord
 */

/**
 * Attach derived search text to generated artifact records.
 * @param {ArtifactRecord[]} rawArtifacts - Raw artifact records from generated data.
 * @returns {(ArtifactRecord & { searchText: string })[]} Hydrated artifact records.
 */
export function hydrateArtifacts(rawArtifacts) {
  return rawArtifacts.map((item) => ({
    ...item,
    searchText: getSearchableText(item)
  }));
}

/**
 * Build lowercase search text from one artifact record.
 * @param {ArtifactRecord} item - Artifact record with name, description, tags, tools, and id.
 * @returns {string} Lowercase combined search text.
 */
function getSearchableText(item) {
  const description = item.description || '';
  const tags = Array.isArray(item.tags) ? item.tags.join(' ') : '';
  const tools = Array.isArray(item.tools) ? item.tools.join(' ') : '';
  return `${item.name} ${description} ${tags} ${tools} ${item.id}`.toLowerCase();
}

/**
 * Split a comma-separated URL parameter into trimmed values.
 * @param {string|null} rawValue - Comma-separated string from a URL query parameter.
 * @returns {string[]} Trimmed non-empty values.
 */
export function splitListParam(rawValue) {
  if (!rawValue) {
    return [];
  }

  return rawValue.split(',').map((value) => value.trim()).filter(Boolean);
}

/**
 * Filter and deduplicate values, preserving the display order of allowedValues.
 * @param {string[]} values - User-selected values (may contain duplicates or unknowns).
 * @param {string[]} allowedValues - Canonical list of valid values in display order.
 * @returns {string[]} Normalized selected values in display order.
 */
export function normalizeSelection(values, allowedValues) {
  const selectedValues = new Set(values);

  return allowedValues.filter((value) => selectedValues.has(value));
}

/**
 * Sort values with configured display-order entries first, then remaining values alphabetically.
 * @param {string[]} values - Values to sort.
 * @param {string[]|undefined} displayOrder - Preferred ordering (may be absent).
 * @returns {string[]} Sorted values.
 */
export function sortValuesByDisplayOrder(values, displayOrder) {
  const configured = Array.isArray(displayOrder) ? displayOrder : [];
  const valueSet = new Set(values);
  const configuredSet = new Set(configured);
  const known = configured.filter((value) => valueSet.has(value));
  const unknown = values.filter((value) => !configuredSet.has(value)).sort();
  return [...known, ...unknown];
}

// localeCompare builds a collator on every call; one shared collator orders ids the same way.
const ID_COLLATOR = new Intl.Collator();

/**
 * @param {ArtifactRecord[]} artifacts - Hydrated artifact records.
 * @param {{ currentQuery: string, currentSort: string, currentTags: string[], currentTools: string[] }} options - Active filter and sort state.
 * @returns {ArtifactRecord[]} Filtered and sorted records.
 */
export function filterAndSortArtifacts(artifacts, options) {
  const {
    currentQuery,
    currentSort,
    currentTags,
    currentTools
  } = options;
  /** @type {Record<'newest' | 'oldest', (left: ArtifactRecord, right: ArtifactRecord) => number>} */
  const comparators = {
    newest: (left, right) => ID_COLLATOR.compare(right.id, left.id),
    oldest: (left, right) => ID_COLLATOR.compare(left.id, right.id)
  };
  const comparator = currentSort === "newest" ? comparators.newest : comparators.oldest;
  const toolSet = new Set(currentTools);
  const tagSet = new Set(currentTags);

  return artifacts
    .filter((item) => {
      if (toolSet.size > 0 && !item.tools.some((tool) => toolSet.has(tool))) {
        return false;
      }

      if (tagSet.size > 0 && !item.tags.some((tag) => tagSet.has(tag))) {
        return false;
      }

      if (currentQuery && !(item.searchText ?? "").includes(currentQuery)) {
        return false;
      }

      return true;
    })
    .sort(comparator);
}

/** Slots in the pagination row. A longer page list collapses into exactly this many, so the row keeps its width. */
const PAGE_SLOT_COUNT = 7;

/**
 * Build the page number sequence for the pagination row. Up to seven pages are
 * all listed. Beyond that the row is always seven slots: the first page, the
 * last page, and one or two ellipses around the current page, so Prev and
 * Next stay where they are as the reader turns pages.
 * @param {number} current - Current page (1-based).
 * @param {number} total - Total number of pages.
 * @returns {(number|string)[]} Page numbers and '...' ellipsis markers.
 */
export function getPageNumbers(current, total) {
  if (total <= PAGE_SLOT_COUNT) {
    return Array.from({ length: total }, (_, index) => index + 1);
  }

  // Slots left for numbers beside the first page, the last page, and the ellipses.
  const nearEdge = PAGE_SLOT_COUNT - 2;
  if (current < nearEdge) {
    return [...Array.from({ length: nearEdge }, (_, index) => index + 1), '...', total];
  }

  if (current > total - nearEdge + 1) {
    return [1, '...', ...Array.from({ length: nearEdge }, (_, index) => total - nearEdge + 1 + index)];
  }

  return [1, '...', current - 1, current, current + 1, '...', total];
}
