import {
  filterAndSortArtifacts,
  hydrateArtifacts,
  sortValuesByDisplayOrder,
} from './catalog.js';
import { getGalleryConfig, getTagLabel, getToolLabel } from './config.js';
import {
  buildGalleryUrl,
  DEFAULT_GALLERY_STATE,
  readGalleryStateFromSearch
} from './gallery-url.js';
import { ICONS } from './icons.js';
import { setBackgroundContentInert } from './inert.js';
import { createMotionHelper } from './motion.js';
import { createBookScene } from './book-scene.js';
import {
  applyDynamicStyles,
  buildFilterNotes,
  buildGridHtml,
  renderPagination
} from './render.js';

const ITEMS_PER_PAGE = 4;
const SCROLL_TOP_THRESHOLD = 300;
const DETAIL_CLOSE_DELAY = 360;
const ACTIVATION_KEYS = new Set(['Enter', ' ']);

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
 * @typedef {Window & { ARTIFACTS_DATA?: ArtifactRecord[] }} GalleryWindow
 * @typedef {{
 *   dataset?: string,
 *   type: 'page' | 'desk-note' | 'mobile-filter',
 *   value: string
 * }} FocusTargetDescriptor
 * @typedef {HTMLElement | FocusTargetDescriptor | null} FocusTarget
 */

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
  return /** @type {HTMLElement} */ (element);
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
 * Return whether one element behaves like a text-entry control.
 * @param {Element | null} element - Element to inspect.
 * @returns {boolean} Whether the element accepts text entry.
 */
function isTextEntryElement(element) {
  const htmlElement = /** @type {HTMLElement | null} */ (element);
  return Boolean(element && (
    element.tagName === 'INPUT'
    || element.tagName === 'TEXTAREA'
    || htmlElement?.isContentEditable
  ));
}

/** Return whether a keyboard event should close the open detail overlay. */
function shouldCloseOverlayForEscape(event, overlay) {
  return event.key === 'Escape' && Boolean(overlay.getExpandedId());
}

/** Return whether a keyboard event should focus the gallery search input. */
function shouldFocusSearchShortcut(event, overlay, activeElement) {
  return (
    event.key === '/'
    && !overlay.getExpandedId()
    && !isTextEntryElement(activeElement)
  );
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
 * }} options - Injected document, runtime, and window dependencies.
 * @returns {void}
 */
export function initializeGalleryApp({ documentObj = document, runtime, windowObj = window }) {
  if (!runtime) {
    throw new Error('A runtime instance is required to initialize the gallery');
  }

  const appRuntime = runtime;
  const galleryWindow = /** @type {GalleryWindow} */ (windowObj);
  const grid = requireElement(documentObj, 'artifacts-grid');
  const searchInput = /** @type {HTMLInputElement} */ (requireElement(documentObj, 'search-input'));
  const searchClear = /** @type {HTMLButtonElement} */ (requireElement(documentObj, 'search-clear'));
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

  const backgroundElements = /** @type {HTMLElement[]} */ ([
    documentObj.querySelector('.header'),
    documentObj.querySelector('.container'),
    documentObj.querySelector('.footer'),
    scrollTopBtn
  ].filter(Boolean));

  const prefersReducedMotionQuery = windowObj.matchMedia('(prefers-reduced-motion: reduce)');
  const motion = createMotionHelper(prefersReducedMotionQuery, windowObj);
  const bookScene = createBookScene({ documentObj, windowObj, motion });
  const galleryConfig = getGalleryConfig(windowObj);
  const rawArtifacts = Array.isArray(galleryWindow.ARTIFACTS_DATA) ? galleryWindow.ARTIFACTS_DATA : [];
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

  /** @type {ReturnType<import('./detail-overlay.js').createDetailOverlay> | null} */
  let overlayInstance = null;
  /** @type {Promise<ReturnType<import('./detail-overlay.js').createDetailOverlay>> | null} */
  let overlayLoading = null;

  /** Lazily import and initialize the detail overlay, returning the cached instance. */
  function ensureOverlay() {
    if (overlayInstance) {
      return Promise.resolve(overlayInstance);
    }
    overlayLoading = overlayLoading || import('./detail-overlay.js')
      .then(({ createDetailOverlay }) => {
        overlayInstance = createDetailOverlay({
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
        return overlayInstance;
      })
      .catch((error) => {
        overlayLoading = null;
        throw error;
      });
    return overlayLoading;
  }

  let overlayActionToken = 0;

  /** Lazy proxy for the detail overlay; methods are safe to call before the module loads. */
  const overlay = {
    getExpandedId: () => overlayInstance?.getExpandedId() ?? null,
    getCardById: (id) => overlayInstance?.getCardById(id) ?? null,
    updateExpandedCardState: () => overlayInstance?.updateExpandedCardState(),
    trapFocus: (event) => overlayInstance?.trapFocus(event) ?? false,
    close: (opts) => {
      overlayActionToken += 1;
      return overlayInstance?.close(opts);
    },
    async open(id, triggerCard, items) {
      const token = ++overlayActionToken;
      try {
        const inst = await ensureOverlay();
        token === overlayActionToken && inst.open(id, triggerCard, items);
      } catch (error) {
        appRuntime.reportError(error, 'overlay open');
      }
    },
    async toggle(id, triggerCard, items) {
      const token = ++overlayActionToken;
      try {
        const inst = await ensureOverlay();
        token === overlayActionToken && inst.toggle(id, triggerCard, items);
      } catch (error) {
        appRuntime.reportError(error, 'overlay toggle');
      }
    }
  };

  grid.addEventListener('pointerenter', () => ensureOverlay(), { once: true });

  let currentPage = DEFAULT_GALLERY_STATE.page;
  let currentFilter = DEFAULT_GALLERY_STATE.q;
  let currentSort = DEFAULT_GALLERY_STATE.sort;
  /** @type {string[]} */
  let currentTools = [];
  /** @type {string[]} */
  let currentTags = [];
  let debounceTimer = null;
  let suppressPush = false;
  /** @type {FocusTarget} */
  let pendingFocusTarget = null;
  /** @type {Record<string, (value: string, surface?: string) => FocusTargetDescriptor | null>} */
  const filterNoteHandlers = {
    filterNote: (value, surface = 'desk') => {
      const resetFilter = resetFiltersByNote[value];
      if (!resetFilter) {
        return null;
      }

      resetFilter();
      return { type: surface === 'mobile' ? 'mobile-filter' : 'desk-note', dataset: 'filterNote', value };
    },
    filterTool: (value, surface = 'desk') => {
      currentTools = toggleSelection(currentTools, value);
      return { type: surface === 'mobile' ? 'mobile-filter' : 'desk-note', dataset: 'filterTool', value };
    },
    filterTag: (value, surface = 'desk') => {
      currentTags = toggleSelection(currentTags, value);
      return { type: surface === 'mobile' ? 'mobile-filter' : 'desk-note', dataset: 'filterTag', value };
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

  readStateFromURL();
  renderFilterNotes();

  const savedTheme = appRuntime.readStorage('theme', 'light') || 'light';
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

  searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = windowObj.setTimeout(() => {
      currentFilter = searchInput.value.toLowerCase();
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
    const target = /** @type {Element | null} */ (event.target);
    const tab = /** @type {HTMLElement | null} */ (
      target?.closest('.desk-note') || target?.closest('.mobile-filter-chip') || null
    );
    if (!tab) {
      return;
    }

    /** @type {Array<[string, string | undefined]>} */
    const filterDatasetEntries = [
      ['filterNote', tab.dataset.filterNote],
      ['filterTool', tab.dataset.filterTool],
      ['filterTag', tab.dataset.filterTag]
    ];
    const filterDatasetEntry = filterDatasetEntries.find(([, value]) => Boolean(value));
    if (!filterDatasetEntry) {
      return;
    }

    const [dataset, value] = filterDatasetEntry;
    if (!value) {
      return;
    }

    const focusTarget = filterNoteHandlers[dataset]?.(value, tab.dataset.filterSurface || 'desk');
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
    const target = /** @type {Element | null} */ (event.target);
    if (target?.closest('[data-close-detail]')) {
      overlay.close();
    }
  });

  grid.addEventListener('click', (event) => {
    const target = /** @type {Element | null} */ (event.target);
    const card = /** @type {HTMLElement | null} */ (target?.closest('.artifact-card') || null);
    if (!card) {
      return;
    }

    overlay.toggle(/** @type {string} */ (card.dataset.id), card, artifactById);
  });

  grid.addEventListener('keydown', (event) => {
    if (!ACTIVATION_KEYS.has(event.key)) {
      return;
    }

    const target = /** @type {Element | null} */ (event.target);
    const card = /** @type {HTMLElement | null} */ (target?.closest('.artifact-card') || null);
    if (!card) {
      return;
    }

    event.preventDefault();
    overlay.toggle(/** @type {string} */ (card.dataset.id), card, artifactById);
  });

  paginationContainer.addEventListener('click', async (event) => {
    const target = /** @type {Element | null} */ (event.target);
    const button = /** @type {HTMLButtonElement | null} */ (target?.closest('[data-page]') || null);
    if (!button || button.disabled) {
      return;
    }

    const page = Number.parseInt(button.dataset.page || '', 10);
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
        if (!shouldCloseOverlayForEscape(event, overlay)) {
          return;
        }

        event.preventDefault();
        overlay.close();
        return;

      case '/':
        if (!shouldFocusSearchShortcut(event, overlay, documentObj.activeElement)) {
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
      appRuntime.writeStorage('theme', theme);
    }

    const meta = documentObj.querySelector('meta[name="theme-color"]');
    if (meta) {
      const bgColor = windowObj.getComputedStyle(htmlElement).getPropertyValue('--color-bg-primary').trim();
      if (bgColor) {
        meta.setAttribute('content', bgColor);
      }
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
    applyDynamicStyles(filterNotesContainer);
    updateFilterNotesState();
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
    updateFilterNotesState();
  }

  function updateFilterNotesState() {
    const updateButtons = (selector, activeValues) => {
      filterNotesContainer.querySelectorAll(selector).forEach((element) => {
        const button = /** @type {HTMLElement} */ (element);
        const active = activeValues.includes(button.dataset.filterTool || button.dataset.filterTag || '');
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-pressed', String(active));
      });
    };

    updateButtons('[data-filter-tool]', currentTools);
    updateButtons('[data-filter-tag]', currentTags);

    /** @type {Array<[string, boolean]>} */
    const filterNoteStates = [
      ['[data-filter-note="all-tools"]', currentTools.length === 0],
      ['[data-filter-note="all-tags"]', currentTags.length === 0]
    ];

    filterNoteStates.forEach(([selector, active]) => {
      filterNotesContainer.querySelectorAll(selector).forEach((element) => {
        const button = /** @type {HTMLElement} */ (element);
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-pressed', String(active));
      });
    });

    const toolsSummary = filterNotesContainer.querySelector('[data-filter-summary="tools"]');
    if (toolsSummary) {
      toolsSummary.textContent = currentTools.length > 0 ? `${currentTools.length} active` : 'All tools';
    }

    const tagsSummary = filterNotesContainer.querySelector('[data-filter-summary="tags"]');
    if (tagsSummary) {
      tagsSummary.textContent = currentTags.length > 0 ? `${currentTags.length} active` : 'All tags';
    }
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

  /**
   * Apply gallery state changes, then optionally restore focus to a target.
   * @param {{ focusTarget?: FocusTarget }} [options={}] - Optional focus target.
   * @returns {void}
   */
  function applyStateChange({ focusTarget = null } = {}) {
    overlay.close({ restoreFocus: false, immediate: true });
    pendingFocusTarget = focusTarget;
    syncUIToState();
    pushState();
    renderContent();
  }

  function resetFilters() {
    currentFilter = '';
    currentTools = [];
    currentTags = [];
    currentPage = DEFAULT_GALLERY_STATE.page;
    searchInput.value = '';
    applyStateChange({ focusTarget: searchInput });
  }

  function resolvePendingFocusTarget(target) {
    if (!target) {
      return null;
    }

    const focusableTarget = /** @type {HTMLElement} */ (target);
    if (typeof focusableTarget.focus === 'function' && documentObj.body.contains(focusableTarget)) {
      return focusableTarget;
    }

    const descriptor = /** @type {FocusTargetDescriptor} */ (target);
    const targetResolvers = {
      page: () => /** @type {HTMLElement | null} */ (
        paginationContainer.querySelector(`[data-page="${CSS.escape(descriptor.value)}"]`)
      ),
      'desk-note': () => {
        const selectorName = (descriptor.dataset || '').replace(/[A-Z]/g, (char) => `-${char.toLowerCase()}`);
        return /** @type {HTMLElement | null} */ (
          filterNotesContainer.querySelector(`[data-${selectorName}="${CSS.escape(descriptor.value)}"]`)
        );
      },
      'mobile-filter': () => {
        const selectorName = (descriptor.dataset || '').replace(/[A-Z]/g, (char) => `-${char.toLowerCase()}`);
        return /** @type {HTMLElement | null} */ (
          filterNotesContainer.querySelector(`[data-filter-surface="mobile"][data-${selectorName}="${CSS.escape(descriptor.value)}"]`)
        );
      }
    };

    return targetResolvers[descriptor.type]?.() || null;
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
    applyDynamicStyles(grid);
    overlay.updateExpandedCardState();
    renderPagination(paginationContainer, currentPage, totalPages);
    restorePendingFocus();
    const artifactLabel = totalItems === 1 ? 'artifact' : 'artifacts';
    const pageLabel = totalPages === 1 ? 'single page' : `page ${currentPage} of ${totalPages}`;
    galleryStatus.textContent = `Showing ${totalItems} ${artifactLabel}; ${pageLabel}.`;
  }
}
