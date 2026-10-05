import { getPageNumbers } from './catalog.js';
import { escapeHtml } from '../html-escape.js';
import { ICONS } from './icons.js';

export { escapeHtml };

const CARD_COLORS = [
  'var(--card-color-1)', 'var(--card-color-2)', 'var(--card-color-3)',
  'var(--card-color-4)', 'var(--card-color-5)', 'var(--card-color-6)',
  'var(--card-color-7)', 'var(--card-color-8)', 'var(--card-color-9)',
  'var(--card-color-10)', 'var(--card-color-11)', 'var(--card-color-12)'
];
const FILTER_NOTE_COLORS = [
  'var(--color-note-1)',
  'var(--color-note-2)',
  'var(--color-note-3)',
  'var(--color-note-4)',
  'var(--color-note-5)',
  'var(--color-note-6)'
];
const ATTACHMENT_STYLES = ['tape-pair', 'tape-center', 'corners', 'clip', 'tape-diagonal'];
const TAPE_COLOR_COUNT = 6;
const BASE_ROTATIONS = ['-1.4deg', '0.6deg', '-0.4deg', '1.2deg', '-0.9deg', '1.5deg', '0.3deg', '-1.1deg', '0.8deg', '-0.5deg', '1.3deg', '-0.7deg'];
const HOVER_ROTATIONS = ['-0.35deg', '0.2deg', '-0.12deg', '0.4deg', '-0.25deg', '0.45deg', '0.1deg', '-0.3deg', '0.25deg', '-0.15deg', '0.36deg', '-0.2deg'];

/**
 * Return the card background color for a given index.
 * @param {number} index - Card position.
 * @returns {string} The card background color.
 */
function getCardColor(index) {
  return CARD_COLORS[index % CARD_COLORS.length];
}

/**
 * Hash a string to a stable unsigned 32-bit integer (FNV-1a).
 * @param {string} value - Text to hash.
 * @returns {number} Deterministic hash.
 */
function hashString(value) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

/**
 * Pick the scrapbook attachment style and tape colour for a card from its id,
 * so a given artifact always looks attached the same way.
 * @param {string} id - Artifact id.
 * @returns {{ attach: string, tape: number }} Attachment style name and 1-based tape colour.
 */
function getAttachmentData(id) {
  const hash = hashString(id);
  return {
    attach: ATTACHMENT_STYLES[hash % ATTACHMENT_STYLES.length],
    tape: (Math.floor(hash / ATTACHMENT_STYLES.length) % TAPE_COLOR_COUNT) + 1
  };
}

/**
 * Return base and hover rotation values for a card at the given index.
 * @param {number} index - Card position.
 * @returns {{ noteRotate: string, noteHoverRotate: string }} Rotation data.
 */
function getRotationData(index) {
  const rotationIndex = index % BASE_ROTATIONS.length;
  return { noteRotate: BASE_ROTATIONS[rotationIndex], noteHoverRotate: HOVER_ROTATIONS[rotationIndex] };
}

/** Global color map: each tag/tool name gets one color, shared across filter notes and detail capsules. */
const labelColorMap = new Map();
/** @type {string[] | null} */
let shuffledColors = null;

/** Return the lazily-initialized Fisher-Yates shuffled filter color palette. */
function getShuffledFilterColors() {
  if (!shuffledColors) {
    shuffledColors = [...FILTER_NOTE_COLORS];
    for (let index = shuffledColors.length - 1; index > 0; index -= 1) {
      const targetIndex = Math.floor(Math.random() * (index + 1));
      [shuffledColors[index], shuffledColors[targetIndex]] = [
        shuffledColors[targetIndex],
        shuffledColors[index]
      ];
    }
  }

  return shuffledColors;
}

/**
 * Build an HTML string for a single filter chip button.
 * @param {{
 *   active?: boolean,
 *   className: string,
 *   color: string,
 *   datasetName: string,
 *   datasetValue: string,
 *   label: string,
 *   rotate?: string | null,
 *   surface: string
 * }} options - Filter control options.
 * @returns {string} Filter chip button HTML.
 */
function createFilterControlButton({
  active = false,
  className,
  color,
  datasetName,
  datasetValue,
  label,
  rotate = null,
  surface
}) {
  const rotateAttr = rotate !== null ? ` data-rotate="${rotate}"` : '';

  return `<button class="${className}${active ? ' is-active' : ''}" data-filter-surface="${surface}" ${datasetName}="${escapeHtml(datasetValue)}" data-chip-color="${escapeHtml(color)}"${rotateAttr} type="button" aria-controls="artifacts-grid" aria-pressed="${active}">${escapeHtml(label)}</button>`;
}

/**
 * Look up the assigned color for a tool or tag label.
 * @param {string} name - Tool or tag label.
 * @returns {string} The assigned CSS color value.
 */
function getLabelColor(name) {
  return labelColorMap.get(name) || 'var(--color-capsule-default)';
}

/**
 * Build an HTML snippet list of up to three capsule items.
 * @param {string[] | undefined} items - Capsule label values.
 * @param {string} className - Container class name.
 * @param {string} [emptyValue] - Markup to use when the list is empty.
 * @returns {string} The snippet HTML.
 */
function buildSnippetList(items, className, emptyValue = '') {
  if (!Array.isArray(items) || items.length === 0) {
    return emptyValue;
  }

  return `
    <div class="${className}">
      ${items
        .slice(0, 3)
        .map((item) => `<span class="${className}-item" data-capsule-bg="${escapeHtml(getLabelColor(item))}">${escapeHtml(item)}</span>`)
        .join('')}
    </div>
  `;
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

  const shuffled = getShuffledFilterColors();
  /** @param {number} index */
  const toolColor = (index) => shuffled[(index + 1) % shuffled.length];
  const tagColorOffset = tools.length + 1;
  /** @param {number} index */
  const tagColor = (index) => shuffled[(tagColorOffset + index) % shuffled.length];

  const hasActiveTools = activeTools.length > 0;
  const hasActiveTags = activeTags.length > 0;

  /**
   * Build one desk column: an "All" note, then one note per value. Each value
   * also claims its color in the shared label color map.
   * @param {{
   *   noteValue: string,
   *   values: string[],
   *   activeValues: string[],
   *   datasetName: string,
   *   colorFor: (index: number) => string,
   *   labelFor: (value: string) => string
   * }} group - Filter group to render.
   * @returns {string[]} Desk note button HTML.
   */
  const buildDeskNotes = ({ noteValue, values, activeValues, datasetName, colorFor, labelFor }) => [
    createFilterControlButton({
      active: activeValues.length === 0,
      className: 'desk-note',
      color: shuffled[0],
      datasetName: 'data-filter-note',
      datasetValue: noteValue,
      label: 'All',
      rotate: (rand() * 6 - 3).toFixed(1),
      surface: 'desk'
    }),
    ...values.map((value, index) => {
      const color = colorFor(index);
      labelColorMap.set(value, color);
      return createFilterControlButton({
        active: activeValues.includes(value),
        className: 'desk-note',
        color,
        datasetName,
        datasetValue: value,
        label: labelFor(value),
        rotate: (rand() * 8 - 4).toFixed(1),
        surface: 'desk'
      });
    })
  ];

  /**
   * Build one mobile chip row: an "All" chip, then one chip per value.
   * @param {{
   *   noteValue: string,
   *   allLabel: string,
   *   values: string[],
   *   activeValues: string[],
   *   datasetName: string,
   *   colorFor: (index: number) => string,
   *   labelFor: (value: string) => string
   * }} group - Filter group to render.
   * @returns {string[]} Mobile chip button HTML.
   */
  const buildMobileChips = ({ noteValue, allLabel, values, activeValues, datasetName, colorFor, labelFor }) => [
    createFilterControlButton({
      active: activeValues.length === 0,
      className: 'mobile-filter-chip',
      color: shuffled[0],
      datasetName: 'data-filter-note',
      datasetValue: noteValue,
      label: allLabel,
      surface: 'mobile'
    }),
    ...values.map((value, index) => createFilterControlButton({
      active: activeValues.includes(value),
      className: 'mobile-filter-chip',
      color: colorFor(index),
      datasetName,
      datasetValue: value,
      label: labelFor(value),
      surface: 'mobile'
    }))
  ];

  const toolGroup = {
    noteValue: 'all-tools',
    values: tools,
    activeValues: activeTools,
    datasetName: 'data-filter-tool',
    colorFor: toolColor,
    labelFor: toolLabel
  };
  const tagGroup = {
    noteValue: 'all-tags',
    values: tags,
    activeValues: activeTags,
    datasetName: 'data-filter-tag',
    colorFor: tagColor,
    labelFor: tagLabel
  };

  // Desk notes draw from the rotation PRNG in order, so tools render before tags.
  const leftNotes = buildDeskNotes(toolGroup);
  const rightNotes = buildDeskNotes(tagGroup);
  const mobileTools = buildMobileChips({ ...toolGroup, allLabel: 'All tools' });
  const mobileTags = buildMobileChips({ ...tagGroup, allLabel: 'All tags' });

  return `
    <div class="desk-notes-left">${leftNotes.join('')}</div>
    <div class="desk-notes-right">${rightNotes.join('')}</div>
    <div class="mobile-filter-stack">
      <section class="mobile-filter-group" aria-label="Tool filters">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">Tools</span>
          <span class="mobile-filter-summary" data-filter-summary="tools">${hasActiveTools ? `${activeTools.length} active` : 'All tools'}</span>
        </div>
        <div class="mobile-filter-chip-row">${mobileTools.join('')}</div>
      </section>
      <section class="mobile-filter-group" aria-label="Tag filters">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">Tags</span>
          <span class="mobile-filter-summary" data-filter-summary="tags">${hasActiveTags ? `${activeTags.length} active` : 'All tags'}</span>
        </div>
        <div class="mobile-filter-chip-row">${mobileTags.join('')}</div>
      </section>
    </div>
  `;
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

/**
 * Swap a failed card thumbnail image for the shared placeholder treatment.
 * Registered as a capture-phase delegated listener because img error events do not bubble.
 * @param {Event} event - Error event dispatched by a broken image.
 * @returns {void}
 */
export function handleThumbnailError(event) {
  const target = /** @type {Element | null} */ (event.target);
  if (!target || target.tagName !== 'IMG' || !target.classList.contains('card-thumbnail')) {
    return;
  }

  const frame = target.closest('.card-photo-frame');
  const parent = frame?.parentNode;
  if (!frame || !parent) {
    return;
  }

  const placeholder = frame.ownerDocument.createElement('div');
  placeholder.className = 'card-thumbnail-placeholder';
  parent.replaceChild(placeholder, frame);
}

/**
 * Attach the delegated broken-thumbnail fallback listener to a grid container.
 * The capture phase is required because image error events do not bubble.
 * @param {HTMLElement} grid - Artifact grid container.
 * @returns {void}
 */
export function registerThumbnailFallback(grid) {
  grid.addEventListener('error', handleThumbnailError, true);
}

/**
 * Build the HTML for a single artifact card in the grid.
 * @param {{ id: string, name: string, thumbnail?: string | null }} item - Artifact record.
 * @param {boolean} isExpanded - Whether the card is expanded.
 * @param {number} index - Card position.
 * @returns {string} The card HTML.
 */
function createCard(item, isExpanded, index) {
  const cardColor = getCardColor(index);
  const thumbnailHtml = item.thumbnail
    ? `
      <div class="card-photo-frame">
        <img class="card-thumbnail" src="${escapeHtml(item.thumbnail)}" alt="${escapeHtml(item.name)}" loading="lazy">
      </div>
    `
    : '<div class="card-thumbnail-placeholder"></div>';

  const rotation = getRotationData(index);
  const attachment = getAttachmentData(item.id);
  return `
    <button class="artifact-card ${isExpanded ? 'expanded' : ''}" data-id="${escapeHtml(item.id)}" data-card-color="${escapeHtml(cardColor)}" data-attach="${attachment.attach}" data-tape="${attachment.tape}" data-note-rotate="${escapeHtml(rotation.noteRotate)}" data-note-hover-rotate="${escapeHtml(rotation.noteHoverRotate)}" type="button"
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
 * Cards alternate between the left and right page of the spread, and each page
 * carries its own page number.
 * @param {Array<{
 *   id: string,
 *   name: string,
 *   thumbnail?: string|null
 * }>} items - Artifacts visible on the current page.
 * @param {string|null} expandedId - Artifact ID currently expanded in the overlay.
 * @param {number} [pageNumber=1] - Gallery page being rendered; page numbers are two per spread.
 * @returns {string} Book page HTML for the current artifact grid.
 */
export function buildGridHtml(items, expandedId, pageNumber = 1) {
  const cards = items.map((item, index) => createCard(item, expandedId === item.id, index));
  const leftCards = cards.filter((_, index) => index % 2 === 0);
  const rightCards = cards.filter((_, index) => index % 2 !== 0);
  const leftNumber = (pageNumber - 1) * 2 + 1;

  /**
   * @param {'left'|'right'} side - Page side.
   * @param {string[]} sideCards - Card HTML for this side.
   * @param {number} number - Printed page number.
   * @returns {string} One page slice.
   */
  const buildPage = (side, sideCards, number) => `
    <section class="artifact-page-slice artifact-page-${side}${sideCards.length === 0 ? ' is-empty' : ''}" aria-label="${side === 'left' ? 'Left' : 'Right'} book page">
      ${sideCards.join('')}
      <span class="page-number" aria-hidden="true">${number}</span>
    </section>`;

  return `${buildPage('left', leftCards, leftNumber)}${buildPage('right', rightCards, leftNumber + 1)}
  `;
}

/**
 * Apply CSS custom properties from data attributes to elements in a container.
 * Called after innerHTML assignment to avoid inline style attributes for CSP compliance.
 * @param {HTMLElement} container - Parent element to walk.
 * @returns {void}
 */
export function applyDynamicStyles(container) {
  container.querySelectorAll('[data-chip-color]').forEach((element) => {
    const el = /** @type {HTMLElement} */ (element);
    const color = el.dataset.chipColor || '';
    el.style.setProperty('--chip-color', color);
    el.style.setProperty('--note-color', color);
    if (el.dataset.rotate) {
      el.style.setProperty('--rotate', `${el.dataset.rotate}deg`);
    }
  });

  container.querySelectorAll('[data-capsule-bg]').forEach((element) => {
    const el = /** @type {HTMLElement} */ (element);
    el.style.setProperty('--capsule-bg', el.dataset.capsuleBg || '');
  });

  container.querySelectorAll('[data-card-color]').forEach((element) => {
    const el = /** @type {HTMLElement} */ (element);
    el.style.setProperty('--card-bg-color', el.dataset.cardColor || '');
    el.style.setProperty('--note-rotate', el.dataset.noteRotate || '');
    el.style.setProperty('--note-hover-rotate', el.dataset.noteHoverRotate || '');
  });
}

/**
 * Render pagination controls into the given container element.
 * Previous and Next carry `data-page-step` so they stay relative to the latest
 * requested page, even when several are pressed while a page turn is running.
 * @param {HTMLElement} container - Pagination container.
 * @param {number} currentPage - Active page number.
 * @param {number} totalPages - Total available pages.
 * @returns {void}
 */
export function renderPagination(container, currentPage, totalPages) {
  if (totalPages <= 1) {
    container.innerHTML = '';
    delete container.dataset.renderKey;
    return;
  }

  const renderKey = `${currentPage}/${totalPages}`;
  if (container.dataset.renderKey === renderKey) {
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
  html += `<button class="page-btn page-btn-nav" data-page="${currentPage - 1}" data-page-step="-1" type="button" ${onFirst ? 'disabled' : ''} aria-label="Previous page"><span class="page-btn-paper"></span>${ICONS.chevronLeft}<span class="page-btn-label">Prev</span></button>`;
  html += pageButtons;
  html += `<button class="page-btn page-btn-nav" data-page="${currentPage + 1}" data-page-step="1" type="button" ${onLast ? 'disabled' : ''} aria-label="Next page"><span class="page-btn-paper"></span><span class="page-btn-label">Next</span>${ICONS.chevronRight}</button>`;
  html += `<button class="page-btn page-btn-nav" data-page="${totalPages}" type="button" ${onLast ? 'disabled' : ''} aria-label="Last page"><span class="page-btn-paper"></span>${ICONS.chevronLast}</button>`;
  container.innerHTML = html;
  container.dataset.renderKey = renderKey;
}
