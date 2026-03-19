import { getPageNumbers } from './catalog.js';
import { ICONS } from './icons.js';

export function escapeHtml(unsafe) {
  if (!unsafe) {
    return '';
  }

  return unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export function buildFilterPanelHtml({ key, values, labelFormatter }) {
  return values
    .map(
      (value) => `
        <label class="filter-dropdown-item" role="option" aria-selected="false">
          <input class="filter-dropdown-checkbox" type="checkbox" value="${escapeHtml(value)}" data-filter-group="${key}">
          <span>${escapeHtml(labelFormatter(value))}</span>
        </label>
      `
    )
    .join('');
}

export function getFilterSummary(selectedValues, control) {
  if (selectedValues.length === 0) {
    return control.emptyLabel;
  }

  if (selectedValues.length === 1) {
    return control.labelFormatter(selectedValues[0]);
  }

  return `${selectedValues.length} ${control.pluralLabel}`;
}

export function updateFilterDropdownUI(control, selectedValues) {
  control.label.textContent = getFilterSummary(selectedValues, control);

  control.panel.querySelectorAll('.filter-dropdown-checkbox').forEach((checkbox) => {
    const isChecked = selectedValues.includes(checkbox.value);
    checkbox.checked = isChecked;
    const option = checkbox.closest('.filter-dropdown-item');
    option.setAttribute('aria-selected', String(isChecked));
    option.classList.toggle('is-selected', isChecked);
  });
}

export function createDetailContent(item) {
  const heroMedia = item.thumbnail
    ? `<img class="detail-media" src="${escapeHtml(item.thumbnail)}" alt="${escapeHtml(item.name)} preview">`
    : '<div class="detail-media-placeholder">&#9881;</div>';

  const description = item.description || 'Open the artifact to explore the interactive experience.';

  return `
    <div class="detail-hero">
      ${heroMedia}
      <div class="detail-hero-blur"></div>
      <div class="detail-hero-gradient"></div>
      <button class="detail-close" type="button" data-close-detail aria-label="Close details">
        ${ICONS.close}
      </button>
      <div class="detail-content">
        <h2 id="detail-title" class="detail-title">${escapeHtml(item.name)}</h2>
        <p class="detail-description">${escapeHtml(description)}</p>
      </div>
      <a class="detail-open-icon" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" aria-label="Open artifact in a new tab">
        ${ICONS.open}
      </a>
    </div>
  `;
}

function createCard(item, isExpanded) {
  const thumbnailHtml = item.thumbnail
    ? `<img class="card-thumbnail" src="${escapeHtml(item.thumbnail)}" alt="${escapeHtml(item.name)}" loading="lazy">`
    : '<div class="card-thumbnail-placeholder">&#9881;</div>';

  return `
    <article class="artifact-card ${isExpanded ? 'expanded' : ''}" data-id="${escapeHtml(item.id)}" tabindex="0" role="button"
      aria-label="View details for ${escapeHtml(item.name)}" aria-expanded="${isExpanded}" aria-haspopup="dialog">
      ${thumbnailHtml}
      <div class="card-overlay">
        <div class="card-overlay-row">
          <div class="card-name">${escapeHtml(item.name)}</div>
          <span class="card-open-indicator" aria-hidden="true">${ICONS.expand}</span>
        </div>
      </div>
    </article>
  `;
}

export function buildGridHtml(items, expandedId) {
  return items.map((item) => createCard(item, expandedId === item.id)).join('');
}

export function renderPagination(container, currentPage, totalPages) {
  if (totalPages <= 1) {
    container.innerHTML = '';
    return;
  }

  const pages = getPageNumbers(currentPage, totalPages);
  const onFirst = currentPage === 1;
  const onLast = currentPage === totalPages;
  const pageButtons = pages.map((page) => {
    if (page === '...') {
      return '<span class="page-ellipsis">&hellip;</span>';
    }

    const isActive = page === currentPage;
    return `<button class="page-btn ${isActive ? 'active' : ''}" data-page="${page}" ${isActive ? 'aria-current="page"' : ''} aria-label="Page ${page}">${page}</button>`;
  }).join('');

  let html = '';
  html += `<button class="page-btn" data-page="1" ${onFirst ? 'disabled' : ''} aria-label="First page">${ICONS.chevronFirst}</button>`;
  html += `<button class="page-btn" data-page="${currentPage - 1}" ${onFirst ? 'disabled' : ''} aria-label="Previous page">${ICONS.chevronLeft}</button>`;
  html += pageButtons;
  html += `<button class="page-btn" data-page="${currentPage + 1}" ${onLast ? 'disabled' : ''} aria-label="Next page">${ICONS.chevronRight}</button>`;
  html += `<button class="page-btn" data-page="${totalPages}" ${onLast ? 'disabled' : ''} aria-label="Last page">${ICONS.chevronLast}</button>`;
  container.innerHTML = html;
}
