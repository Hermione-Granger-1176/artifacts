/** @param {Object[]} rawArtifacts - Raw artifact records from generated data. */
export function hydrateArtifacts(rawArtifacts) {
  return rawArtifacts.map((item) => ({
    ...item,
    searchText: getSearchableText(item)
  }));
}

/** @param {Object} item - Artifact record with name, description, tags, tools, and id. */
export function getSearchableText(item) {
  const description = item.description || '';
  const tags = Array.isArray(item.tags) ? item.tags.join(' ') : '';
  const tools = Array.isArray(item.tools) ? item.tools.join(' ') : '';
  return `${item.name} ${description} ${tags} ${tools} ${item.id}`.toLowerCase();
}

/** @param {string|null} rawValue - Comma-separated string from a URL query parameter. */
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
 */
export function normalizeSelection(values, allowedValues) {
  const allowedSet = new Set(allowedValues);
  const uniqueSet = new Set(values.filter((value) => allowedSet.has(value)));

  return allowedValues.filter((value) => uniqueSet.has(value));
}

/**
 * Sort values with configured display-order entries first, then remaining values alphabetically.
 * @param {string[]} values - Values to sort.
 * @param {string[]|undefined} displayOrder - Preferred ordering (may be absent).
 */
export function sortValuesByDisplayOrder(values, displayOrder) {
  const configured = Array.isArray(displayOrder) ? displayOrder : [];
  const known = configured.filter((value) => values.includes(value));
  const unknown = values.filter((value) => !configured.includes(value)).sort();
  return [...known, ...unknown];
}

/**
 * Filter artifacts by search text, tool, and tag selections, then sort by the chosen order.
 * @param {Object[]} artifacts - Hydrated artifact records with searchText.
 * @param {Object} options - Filter/sort state with currentFilter, currentSort, currentTags, currentTools.
 */
export function filterAndSortArtifacts(artifacts, options) {
  const {
    currentFilter,
    currentSort,
    currentTags,
    currentTools
  } = options;
  const comparators = {
    newest: (left, right) => right.id.localeCompare(left.id),
    oldest: (left, right) => left.id.localeCompare(right.id)
  };
  const comparator = comparators[currentSort] || comparators.oldest;

  return artifacts
    .filter((item) => {
      if (currentTools.length > 0 && !item.tools.some((tool) => currentTools.includes(tool))) {
        return false;
      }

      if (currentTags.length > 0 && !item.tags.some((tag) => currentTags.includes(tag))) {
        return false;
      }

      if (currentFilter && !item.searchText.includes(currentFilter)) {
        return false;
      }

      return true;
    })
    .sort(comparator);
}

/**
 * Build a collapsed page number sequence with ellipses for long ranges.
 * @param {number} current - Current page (1-based).
 * @param {number} total - Total number of pages.
 * @returns {(number|string)[]} Page numbers and '...' ellipsis markers.
 */
export function getPageNumbers(current, total) {
  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => index + 1);
  }

  const pages = [];
  const addPage = (page) => {
    if (!pages.includes(page)) {
      pages.push(page);
    }
  };

  addPage(1);
  addPage(2);
  for (let page = current - 1; page <= current + 1; page += 1) {
    if (page >= 1 && page <= total) {
      addPage(page);
    }
  }
  addPage(total - 1);
  addPage(total);

  pages.sort((left, right) => left - right);

  const result = [];
  let previousPage = null;

  for (const page of pages) {
    if (previousPage !== null && page - previousPage > 1) {
      result.push('...');
    }

    result.push(page);
    previousPage = page;
  }

  return result;
}
