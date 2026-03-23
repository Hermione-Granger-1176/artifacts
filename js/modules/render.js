import { getPageNumbers } from './catalog.js';
import { ICONS } from './icons.js';

const CARD_COLORS = [
  'var(--card-color-1)', 'var(--card-color-2)', 'var(--card-color-3)',
  'var(--card-color-4)', 'var(--card-color-5)', 'var(--card-color-6)',
  'var(--card-color-7)', 'var(--card-color-8)', 'var(--card-color-9)',
  'var(--card-color-10)', 'var(--card-color-11)', 'var(--card-color-12)'
];
const BASE_ROTATIONS = ['-1.4deg', '0.6deg', '-0.4deg', '1.2deg', '-0.9deg', '1.5deg', '0.3deg', '-1.1deg', '0.8deg', '-0.5deg', '1.3deg', '-0.7deg'];
const HOVER_ROTATIONS = ['-0.35deg', '0.2deg', '-0.12deg', '0.4deg', '-0.25deg', '0.45deg', '0.1deg', '-0.3deg', '0.25deg', '-0.15deg', '0.36deg', '-0.2deg'];

function getCardColor(index) {
  return CARD_COLORS[index % CARD_COLORS.length];
}

function getRotationStyle(index) {
  const rotationIndex = index % BASE_ROTATIONS.length;
  return `--note-rotate:${BASE_ROTATIONS[rotationIndex]}; --note-hover-rotate:${HOVER_ROTATIONS[rotationIndex]};`;
}

/** Global color map — each tag/tool name gets one color, shared across filter notes and detail capsules. */
const labelColorMap = new Map();
let shuffledColors = null;

function getLabelColor(name) {
  return labelColorMap.get(name) || '#e8c8a0';
}

function buildSnippetList(items, className, emptyValue = '') {
  if (!Array.isArray(items) || items.length === 0) {
    return emptyValue;
  }

  return `
    <div class="${className}">
      ${items
        .slice(0, 3)
        .map((item) => `<span class="${className}-item" style="--capsule-bg: ${getLabelColor(item)}">${escapeHtml(item)}</span>`)
        .join('')}
    </div>
  `;
}

/**
 * Escape text for safe HTML insertion.
 * @param {string|null|undefined} unsafe - Raw string to escape for safe HTML insertion.
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
 * Build HTML for scattered filter notes resting on the desk.
 * @param {{
 *   tools: string[],
 *   tags: string[],
 *   activeTools: string[],
 *   activeTags: string[],
 *   toolLabel: (v: string) => string,
 *   tagLabel: (v: string) => string
 * }} options - Filter-note source values and active state.
 * @returns {string} Filter notes HTML.
 */
export function buildFilterNotes({ tools, tags, activeTools, activeTags, toolLabel, tagLabel }) {
  // Deterministic PRNG for slight rotation on each note
  let seed = 1;
  const rand = () => {
    const x = Math.sin(seed++) * 10000;
    return x - Math.floor(x);
  };

  const noteColors = ['#f5e6a3', '#e8a0a0', '#a0c8e8', '#a0e8c8', '#e8c8a0', '#e8a0e8'];

  // Shuffle once per page load and cache for the session.
  // Individual note rotations still use the seeded helper below for stable per-render jitter.
  if (!shuffledColors) {
    shuffledColors = [...noteColors];
    for (let i = shuffledColors.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffledColors[i], shuffledColors[j]] = [shuffledColors[j], shuffledColors[i]];
    }
  }
  const shuffled = shuffledColors;

  const hasActiveTools = activeTools.length > 0;
  const hasActiveTags = activeTags.length > 0;

  function createDeskNoteButton({ active = false, datasetName, datasetValue, label, color, rotate }) {
    return `<button class="desk-note${active ? ' is-active' : ''}" ${datasetName}="${escapeHtml(datasetValue)}" type="button" aria-controls="artifacts-grid" aria-pressed="${active}" style="--note-color: ${color}; --rotate: ${rotate}deg;">${escapeHtml(label)}</button>`;
  }

  const leftNotes = [
    `<button class="desk-note${hasActiveTools ? '' : ' is-active'}" data-filter-note="all-tools" type="button" aria-controls="artifacts-grid" aria-pressed="${String(!hasActiveTools)}" aria-label="All tools" style="--note-color: ${shuffled[0]}; --rotate: ${(rand() * 6 - 3).toFixed(1)}deg;">All</button>`,
    ...tools.map((tool, index) => {
      const color = shuffled[(index + 1) % shuffled.length];
      labelColorMap.set(tool, color);
      return createDeskNoteButton({
        active: activeTools.includes(tool),
        color,
        datasetName: 'data-filter-tool',
        datasetValue: tool,
        label: toolLabel(tool),
        rotate: (rand() * 8 - 4).toFixed(1)
      });
    })
  ];

  const tagColorOffset = tools.length + 1;
  const rightNotes = [
    `<button class="desk-note${hasActiveTags ? '' : ' is-active'}" data-filter-note="all-tags" type="button" aria-controls="artifacts-grid" aria-pressed="${String(!hasActiveTags)}" aria-label="All tags" style="--note-color: ${shuffled[0]}; --rotate: ${(rand() * 6 - 3).toFixed(1)}deg;">All</button>`,
    ...tags.map((tag, index) => {
      const color = shuffled[(tagColorOffset + index) % shuffled.length];
      labelColorMap.set(tag, color);
      return createDeskNoteButton({
        active: activeTags.includes(tag),
        color,
        datasetName: 'data-filter-tag',
        datasetValue: tag,
        label: tagLabel(tag),
        rotate: (rand() * 8 - 4).toFixed(1)
      });
    })
  ];

  return `<div class="desk-notes-left">${leftNotes.join('')}</div><div class="desk-notes-right">${rightNotes.join('')}</div>`;
}

/**
 * Build the inner HTML for the detail overlay panel.
 * @param {{
 *   description?: string|null,
 *   name: string,
 *   tags?: string[],
 *   thumbnail?: string|null,
 *   tools?: string[],
 *   url: string
 * }} item - Artifact metadata for the active detail card.
 * @returns {string} Detail overlay HTML.
 */
export function createDetailContent(item) {
  const heroMedia = item.thumbnail
    ? `<img class="detail-media" src="${escapeHtml(item.thumbnail)}" alt="${escapeHtml(item.name)} preview">`
    : '<div class="detail-media-placeholder"></div>';

  const description = item.description || 'Open the artifact to explore the interactive experience.';
  const detailTags = buildSnippetList(item.tags, 'detail-meta-tags');
  const detailTools = buildSnippetList(item.tools, 'detail-meta-tools');

  return `
    <button class="detail-close" type="button" data-close-detail aria-label="Close details">
      ${ICONS.close}
    </button>
    <div class="detail-media-wrap">
      ${heroMedia}
    </div>
    <div class="detail-content">
      <h2 id="detail-title" class="detail-title">${escapeHtml(item.name)}</h2>
      <p id="detail-description" class="detail-description">${escapeHtml(description)}</p>
      ${detailTags || detailTools ? `<div class="detail-meta">${detailTags}${detailTools}</div>` : ''}
      <a class="detail-open-link" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer"
        aria-label="Open artifact in a new tab">
        Open artifact <span class="visually-hidden">(opens in a new tab)</span> ${ICONS.open}
      </a>
    </div>
  `;
}

/** Build the HTML for a single artifact card in the grid. */
function createCard(item, isExpanded, index) {
  const cardColor = getCardColor(index);
  const thumbnailHtml = item.thumbnail
    ? `
      <div class="card-photo-frame">
        <img class="card-thumbnail" src="${escapeHtml(item.thumbnail)}" alt="${escapeHtml(item.name)}" loading="lazy">
      </div>
    `
    : '<div class="card-thumbnail-placeholder"></div>';

  return `
    <button class="artifact-card ${isExpanded ? 'expanded' : ''}" data-id="${escapeHtml(item.id)}" style="--card-bg-color: ${cardColor}; ${getRotationStyle(index)}" type="button"
      aria-label="View details for ${escapeHtml(item.name)}" aria-expanded="${isExpanded}" aria-haspopup="dialog">
      <div class="card-note">
        <div class="card-thumbnail-area">
          ${thumbnailHtml}
        </div>
        <div class="card-overlay card-note-body">
          <div class="card-name">${escapeHtml(item.name)}</div>
        </div>
      </div>
    </button>
  `;
}

/**
 * Build the combined HTML for all artifact cards on the current page.
 * @param {Array<{
 *   id: string,
 *   name: string,
 *   thumbnail?: string|null
 * }>} items - Artifacts visible on the current page.
 * @param {string|null} expandedId - Artifact ID currently expanded in the overlay.
 * @returns {string} Book page HTML for the current artifact grid.
 */
export function buildGridHtml(items, expandedId) {
  const leftItems = [];
  const rightItems = [];

  items.forEach((item, index) => {
    // Alternating items visually balances the page heights
    if (index % 2 === 0) {
      leftItems.push(createCard(item, expandedId === item.id, index));
    } else {
      rightItems.push(createCard(item, expandedId === item.id, index));
    }
  });

  return `
    <section class="artifact-page-slice artifact-page-left" aria-label="Left book page">
      ${leftItems.join('')}
    </section>
    <section class="artifact-page-slice artifact-page-right" aria-label="Right book page">
      ${rightItems.join('')}
    </section>
  `;
}

/**
 * Render pagination controls into the given container element.
 * @param {HTMLElement} container - Pagination container.
 * @param {number} currentPage - Active page number.
 * @param {number} totalPages - Total available pages.
 * @returns {void}
 */
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
      return '<span class="page-ellipsis" aria-hidden="true"><span class="page-ellipsis-dots">&hellip;</span></span>';
    }

    const isActive = page === currentPage;
    const activeClass = isActive ? 'active' : '';
    const ariaCurrent = isActive ? 'aria-current="page"' : '';
    return `<button class="page-btn ${activeClass}" data-page="${page}" type="button" ${ariaCurrent} aria-label="Page ${page}"><span class="page-btn-paper"></span><span class="page-btn-number">${page}</span></button>`;
  }).join('');

  let html = '';
  html += `<button class="page-btn page-btn-nav" data-page="1" type="button" ${onFirst ? 'disabled' : ''} aria-label="First page"><span class="page-btn-paper"></span>${ICONS.chevronFirst}</button>`;
  html += `<button class="page-btn page-btn-nav" data-page="${currentPage - 1}" type="button" ${onFirst ? 'disabled' : ''} aria-label="Previous page"><span class="page-btn-paper"></span>${ICONS.chevronLeft}</button>`;
  html += pageButtons;
  html += `<button class="page-btn page-btn-nav" data-page="${currentPage + 1}" type="button" ${onLast ? 'disabled' : ''} aria-label="Next page"><span class="page-btn-paper"></span>${ICONS.chevronRight}</button>`;
  html += `<button class="page-btn page-btn-nav" data-page="${totalPages}" type="button" ${onLast ? 'disabled' : ''} aria-label="Last page"><span class="page-btn-paper"></span>${ICONS.chevronLast}</button>`;
  container.innerHTML = html;
}
