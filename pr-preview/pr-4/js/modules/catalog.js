export function hydrateArtifacts(rawArtifacts) {
  return rawArtifacts.map((item) => ({
    ...item,
    searchText: getSearchableText(item)
  }));
}

export function getSearchableText(item) {
  const description = item.description || '';
  const tags = Array.isArray(item.tags) ? item.tags.join(' ') : '';
  const tools = Array.isArray(item.tools) ? item.tools.join(' ') : '';
  return `${item.name} ${description} ${tags} ${tools} ${item.id}`.toLowerCase();
}

export function splitListParam(rawValue) {
  if (!rawValue) {
    return [];
  }

  return rawValue.split(',').map((value) => value.trim()).filter(Boolean);
}

export function normalizeSelection(values, allowedValues) {
  const allowedSet = new Set(allowedValues);
  const unique = [];

  values.forEach((value) => {
    if (allowedSet.has(value) && !unique.includes(value)) {
      unique.push(value);
    }
  });

  return allowedValues.filter((value) => unique.includes(value));
}

export function sortValuesByDisplayOrder(values, displayOrder) {
  const configured = Array.isArray(displayOrder) ? displayOrder : [];
  const known = configured.filter((value) => values.includes(value));
  const unknown = values.filter((value) => !configured.includes(value)).sort();
  return [...known, ...unknown];
}

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
