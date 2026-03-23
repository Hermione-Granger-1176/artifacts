import {
  filterAndSortArtifacts,
  hydrateArtifacts,
  normalizeSelection,
  sortValuesByDisplayOrder,
  splitListParam
} from './catalog.js';
import { getGalleryConfig, getTagLabel, getToolLabel } from './config.js';
import { createDetailOverlay } from './detail-overlay.js';
import { ICONS } from './icons.js';
import { setBackgroundContentInert } from './inert.js';
import { createMotionHelper } from './motion.js';
import { createBookScene } from './book-scene.js';
import {
  buildFilterNotes,
  buildGridHtml,
  renderPagination
} from './render.js';

const ITEMS_PER_PAGE = 4;
const THEME_COLORS = { dark: '#1e1a14', light: '#f5efe6' };
const DEFAULTS = { page: 1, sort: 'newest', q: '' };
const SCROLL_TOP_THRESHOLD = 300;
const DETAIL_CLOSE_DELAY = 360;
const ACTIVATION_KEYS = new Set(['Enter', ' ']);

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
export function readGalleryStateFromSearch({ search, allTools, allTags, defaults = DEFAULTS }) {
  const params = new URLSearchParams(search);
  return {
    page: Math.max(1, Number.parseInt(params.get('page'), 10) || defaults.page),
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
  defaults = DEFAULTS
}) {
  const params = new URLSearchParams();
  if (page > 1) {
    params.set('page', page);
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

/**
 * Return a required DOM element by ID.
 * @param {Document} documentObj - Document containing the gallery shell.
 * @param {string} id - Required element ID.
 * @returns {HTMLElement} Located DOM element.
 */
function requireElement(documentObj, id) {
  const element = documentObj.getElementById(id);
  if (!element) {
    throw new Error(`Missing required element: #${id}`);
  }
  return element;
}

/**
 * Toggle one filter value in a normalized selection list.
 * @param {string[]} selection - Current selected values.
 * @param {string} value - Value to add or remove.
 * @returns {string[]} Updated selection values.
 */
function toggleSelection(selection, value) {
  return selection.includes(value)
    ? selection.filter((entry) => entry !== value)
    : [...selection, value];
}

/**
 * Initialize the gallery application: resolve DOM elements, hydrate data, wire event
 * listeners, and render the initial view.
 * @param {{
 *   documentObj?: Document,
 *   runtime: {
 *     markReady: () => void,
 *     readStorage: (key: string, fallbackValue?: string|null) => string|null,
 *     reportError: (error: *, context: string, options?: { fatal?: boolean }) => void,
 *     setupGlobalErrorHandlers: () => void,
 *     writeStorage: (key: string, value: string) => boolean
 *   },
 *   windowObj?: Window
 * }} [options={}] - Injected document, runtime, and window dependencies.
 * @returns {void}
 */
export function initializeGalleryApp({ documentObj = document, runtime, windowObj = window } = {}) {
  if (!runtime) {
    throw new Error('A runtime instance is required to initialize the gallery');
  }

  const grid = requireElement(documentObj, 'artifacts-grid');
  const searchInput = requireElement(documentObj, 'search-input');
  const searchClear = requireElement(documentObj, 'search-clear');
  const sortToggle = requireElement(documentObj, 'sort-toggle');
  const filterReset = requireElement(documentObj, 'filter-reset');
  const themeToggle = requireElement(documentObj, 'theme-toggle');
  const noResults = requireElement(documentObj, 'no-results');
  const noResultsReset = requireElement(documentObj, 'no-results-reset');
  const paginationContainer = requireElement(documentObj, 'pagination');
  const scrollTopBtn = requireElement(documentObj, 'scroll-top');
  const detailOverlayEl = requireElement(documentObj, 'detail-overlay');
  const detailPanel = requireElement(documentObj, 'detail-panel');
  const filterNotesContainer = requireElement(documentObj, 'filter-notes');
  const galleryStatus = requireElement(documentObj, 'gallery-status');
  const htmlElement = documentObj.documentElement;

  const backgroundElements = [
    documentObj.querySelector('.header'),
    documentObj.querySelector('.container'),
    documentObj.querySelector('.footer'),
    scrollTopBtn
  ].filter(Boolean);

  const prefersReducedMotionQuery = windowObj.matchMedia('(prefers-reduced-motion: reduce)');
  const motion = createMotionHelper(prefersReducedMotionQuery, windowObj);
  const bookScene = createBookScene({ documentObj, windowObj, motion });
  const galleryConfig = getGalleryConfig(windowObj);
  const rawArtifacts = Array.isArray(windowObj.ARTIFACTS_DATA) ? windowObj.ARTIFACTS_DATA : [];
  const allArtifacts = hydrateArtifacts(rawArtifacts);
  const artifactById = new Map(allArtifacts.map((item) => [item.id, item]));
  const allTags = sortValuesByDisplayOrder(
    [...new Set(allArtifacts.flatMap((item) => item.tags))],
    galleryConfig.tagDisplayOrder
  );
  const allTools = sortValuesByDisplayOrder(
    [...new Set(allArtifacts.flatMap((item) => item.tools))],
    galleryConfig.toolDisplayOrder
  );

  const overlay = createDetailOverlay({
    detailOverlay: detailOverlayEl,
    detailPanel,
    grid,
    documentObj,
    windowObj,
    motion,
    setBackgroundContentInert,
    backgroundElements,
    detailCloseDelay: DETAIL_CLOSE_DELAY
  });

  let currentPage = DEFAULTS.page;
  let currentFilter = DEFAULTS.q;
  let currentSort = DEFAULTS.sort;
  let currentTools = [];
  let currentTags = [];
  let debounceTimer = null;
  let suppressPush = false;
  let pendingFocusTarget = null;
  const filterNoteHandlers = {
    filterNote: (value) => {
      const resetFilter = resetFiltersByNote[value];
      if (!resetFilter) {
        return null;
      }

      resetFilter();
      return { type: 'desk-note', dataset: 'filterNote', value };
    },
    filterTool: (value) => {
      currentTools = toggleSelection(currentTools, value);
      return { type: 'desk-note', dataset: 'filterTool', value };
    },
    filterTag: (value) => {
      currentTags = toggleSelection(currentTags, value);
      return { type: 'desk-note', dataset: 'filterTag', value };
    }
  };
  const resetFiltersByNote = {
    'all-tags': () => {
      currentTags = [];
    },
    'all-tools': () => {
      currentTools = [];
    }
  };

  filterReset.innerHTML = ICONS.reset;

  renderFilterNotes();
  readStateFromURL();

  const savedTheme = runtime.readStorage('theme', 'light') || 'light';
  applyTheme(savedTheme, false);
  updateScrollTopVisibility(false);

  syncUIToState();
  renderContent();
  documentObj.body.classList.remove('js-loading');
  void bookScene.startIntro();

  themeToggle.addEventListener('click', () => {
    const currentTheme = htmlElement.getAttribute('data-theme');
    applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
  });

  searchInput.addEventListener('input', (event) => {
    clearTimeout(debounceTimer);
    debounceTimer = windowObj.setTimeout(() => {
      currentFilter = event.target.value.toLowerCase();
      currentPage = 1;
      applyStateChange();
    }, 150);
  });

  searchClear.addEventListener('click', () => {
    searchInput.value = '';
    currentFilter = '';
    currentPage = 1;
    applyStateChange({ focusTarget: searchInput });
  });

  filterNotesContainer.addEventListener('click', (event) => {
    const tab = event.target.closest('.desk-note');
    if (!tab) {
      return;
    }

    const filterDatasetEntry = [
      ['filterNote', tab.dataset.filterNote],
      ['filterTool', tab.dataset.filterTool],
      ['filterTag', tab.dataset.filterTag]
    ].find(([, value]) => Boolean(value));
    if (!filterDatasetEntry) {
      return;
    }

    const [dataset, value] = filterDatasetEntry;
    const focusTarget = filterNoteHandlers[dataset]?.(value);
    if (!focusTarget) {
      return;
    }

    currentPage = 1;
    applyStateChange({ focusTarget });
  });

  sortToggle.addEventListener('click', () => {
    currentSort = currentSort === 'newest' ? 'oldest' : 'newest';
    currentPage = 1;
    applyStateChange();
  });

  filterReset.addEventListener('click', resetFilters);
  noResultsReset.addEventListener('click', resetFilters);

  detailOverlayEl.addEventListener('click', (event) => {
    if (event.target.closest('[data-close-detail]')) {
      overlay.close();
    }
  });

  grid.addEventListener('click', (event) => {
    const card = event.target.closest('.artifact-card');
    if (!card) {
      return;
    }

    overlay.toggle(card.dataset.id, card, artifactById);
  });

  grid.addEventListener('keydown', (event) => {
    if (!ACTIVATION_KEYS.has(event.key)) {
      return;
    }

    const card = event.target.closest('.artifact-card');
    if (!card) {
      return;
    }

    event.preventDefault();
    overlay.toggle(card.dataset.id, card, artifactById);
  });

  paginationContainer.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-page]');
    if (!button || button.disabled) {
      return;
    }

    const page = Number.parseInt(button.dataset.page, 10);
    if (!page || page === currentPage) {
      return;
    }

    const direction = page > currentPage ? 'next' : 'previous';
    currentPage = page;
    pendingFocusTarget = { type: 'page', value: String(page) };
    overlay.close({ restoreFocus: false, immediate: true });
    pushState();
    await bookScene.turnPage(() => {
      renderContent();
    }, { direction });
  });

  documentObj.addEventListener('keydown', (event) => {
    switch (event.key) {
      case 'Tab':
        overlay.trapFocus(event);
        return;

      case 'Escape':
        if (!overlay.getExpandedId()) {
          return;
        }

        event.preventDefault();
        overlay.close();
        return;

      case '/':
        if (overlay.getExpandedId() || isTextEntryElement(documentObj.activeElement)) {
          return;
        }

        event.preventDefault();
        searchInput.focus();
        return;

      default:
        return;
    }
  });

  windowObj.addEventListener('popstate', () => {
    overlay.close({ restoreFocus: false, immediate: true });
    suppressPush = true;
    readStateFromURL();
    syncUIToState();
    renderContent();
    suppressPush = false;
  });

  let scrollTicking = false;
  windowObj.addEventListener(
    'scroll',
    () => {
      if (scrollTicking) {
        return;
      }

      windowObj.requestAnimationFrame(() => {
        updateScrollTopVisibility(windowObj.scrollY > SCROLL_TOP_THRESHOLD);
        scrollTicking = false;
      });
      scrollTicking = true;
    },
    { passive: true }
  );

  scrollTopBtn.addEventListener('click', () => {
    motion.scrollToTop();
  });

  function applyTheme(theme, persist = true) {
    htmlElement.setAttribute('data-theme', theme);
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    themeToggle.setAttribute('aria-pressed', String(theme === 'dark'));
    themeToggle.setAttribute('aria-label', `Switch to ${nextTheme} theme`);
    themeToggle.setAttribute('title', `Switch to ${nextTheme} theme`);
    if (persist) {
      runtime.writeStorage('theme', theme);
    }

    const meta = documentObj.querySelector('meta[name="theme-color"]');
    if (meta) {
      meta.setAttribute('content', THEME_COLORS[theme] || THEME_COLORS.dark);
    }

    galleryStatus.textContent = `Theme switched to ${theme} mode.`;
  }

  function renderFilterNotes() {
    filterNotesContainer.innerHTML = buildFilterNotes({
      tools: allTools,
      tags: allTags,
      activeTools: currentTools,
      activeTags: currentTags,
      toolLabel: (value) => getToolLabel(galleryConfig, value),
      tagLabel: (value) => getTagLabel(galleryConfig, value)
    });
  }

  function readStateFromURL() {
    const nextState = readGalleryStateFromSearch({
      search: windowObj.location.search,
      allTools,
      allTags
    });
    currentPage = nextState.page;
    currentFilter = nextState.q;
    currentSort = nextState.sort;
    currentTools = nextState.tools;
    currentTags = nextState.tags;
    searchInput.value = nextState.rawQuery;
  }

  function buildStateUrl() {
    return buildGalleryUrl({
      pathname: windowObj.location.pathname,
      page: currentPage,
      sort: currentSort,
      q: currentFilter,
      tools: currentTools,
      tags: currentTags
    });
  }

  function pushState() {
    if (suppressPush) {
      return;
    }

    const nextUrl = buildStateUrl();
    const currentUrl = `${windowObj.location.pathname}${windowObj.location.search}`;
    if (nextUrl !== currentUrl) {
      windowObj.history.pushState(null, '', nextUrl);
    }
  }

  function syncUIToState() {
    if (searchInput.value.toLowerCase() !== currentFilter) {
      searchInput.value = currentFilter;
    }

    updateSearchClearVisibility();
    updateSortToggle();
    updateFilterResetVisibility();
    renderFilterNotes();
  }

  function updateSearchClearVisibility() {
    searchClear.classList.toggle('hidden', searchInput.value.length === 0);
  }

  function updateScrollTopVisibility(isVisible) {
    scrollTopBtn.classList.toggle('visible', isVisible);
    scrollTopBtn.setAttribute('aria-hidden', String(!isVisible));
    scrollTopBtn.tabIndex = isVisible ? 0 : -1;
  }

  function updateSortToggle() {
    const isOldest = currentSort === 'oldest';
    const label = `Sort by ${isOldest ? 'oldest' : 'newest'} first`;
    sortToggle.classList.toggle('is-oldest', isOldest);
    sortToggle.setAttribute('aria-label', label);
    sortToggle.setAttribute('title', label);
    sortToggle.setAttribute('aria-pressed', String(isOldest));
  }

  function updateFilterResetVisibility() {
    const hasActiveFilters = currentFilter !== '' || currentTools.length > 0 || currentTags.length > 0;
    filterReset.classList.toggle('hidden', !hasActiveFilters);
  }

  function applyStateChange({ focusTarget = null } = {}) {
    overlay.close({ restoreFocus: false, immediate: true });
    pendingFocusTarget = focusTarget;
    syncUIToState();
    pushState();
    renderContent();
  }

  function isTextEntryElement(element) {
    return Boolean(element && (
      element.tagName === 'INPUT'
      || element.tagName === 'TEXTAREA'
      || element.isContentEditable
    ));
  }

  function resetFilters() {
    currentFilter = '';
    currentTools = [];
    currentTags = [];
    currentPage = DEFAULTS.page;
    searchInput.value = '';
    applyStateChange({ focusTarget: searchInput });
  }

  function resolvePendingFocusTarget(target) {
    if (!target) {
      return null;
    }

    if (typeof target.focus === 'function' && documentObj.body.contains(target)) {
      return target;
    }

    const targetResolvers = {
      page: () => paginationContainer.querySelector(`[data-page="${target.value}"]`),
      'desk-note': () => {
        const selectorName = target.dataset.replace(/[A-Z]/g, (char) => `-${char.toLowerCase()}`);
        return filterNotesContainer.querySelector(`[data-${selectorName}="${target.value}"]`);
      }
    };

    return targetResolvers[target.type]?.() || null;
  }

  function restorePendingFocus() {
    const target = resolvePendingFocusTarget(pendingFocusTarget);
    pendingFocusTarget = null;
    if (target && typeof target.focus === 'function') {
      target.focus();
    }
  }

  function renderContent() {
    const filtered = filterAndSortArtifacts(allArtifacts, {
      currentFilter,
      currentSort,
      currentTags,
      currentTools
    });

    updateFilterResetVisibility();

    const totalItems = filtered.length;
    const totalPages = Math.max(1, Math.ceil(totalItems / ITEMS_PER_PAGE));
    currentPage = Math.max(1, Math.min(currentPage, totalPages));
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
    const endIndex = Math.min(startIndex + ITEMS_PER_PAGE, totalItems);
    const pageItems = filtered.slice(startIndex, endIndex);

    if (totalItems === 0) {
      grid.innerHTML = '';
      noResults.classList.remove('hidden');
      paginationContainer.innerHTML = '';
      overlay.updateExpandedCardState();
      restorePendingFocus();
      galleryStatus.textContent = 'No artifacts match the current search and filters.';
      return;
    }

    noResults.classList.add('hidden');
    grid.innerHTML = buildGridHtml(pageItems, overlay.getExpandedId());
    overlay.updateExpandedCardState();
    renderPagination(paginationContainer, currentPage, totalPages);
    restorePendingFocus();
    const artifactLabel = totalItems === 1 ? 'artifact' : 'artifacts';
    const pageLabel = totalPages === 1 ? 'single page' : `page ${currentPage} of ${totalPages}`;
    galleryStatus.textContent = `Showing ${totalItems} ${artifactLabel}; ${pageLabel}.`;
  }
}
