import {
  filterAndSortArtifacts,
  hydrateArtifacts,
  normalizeSelection,
  sortValuesByDisplayOrder,
  splitListParam
} from './catalog.js';
import { getGalleryConfig, getTagLabel, getToolLabel } from './config.js';
import { ICONS } from './icons.js';
import {
  buildFilterPanelHtml,
  buildGridHtml,
  createDetailContent,
  renderPagination,
  updateFilterDropdownUI
} from './render.js';

const ITEMS_PER_PAGE = 12;
const THEME_COLORS = { dark: '#202020', light: '#f0f0f0' };
const DEFAULTS = { page: 1, sort: 'newest', q: '' };
const SCROLL_TOP_THRESHOLD = 300;
const DETAIL_CLOSE_DELAY = 360;

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

function requireElement(documentObj, id) {
  const element = documentObj.getElementById(id);
  if (!element) {
    throw new Error(`Missing required element: #${id}`);
  }
  return element;
}

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
  const detailOverlay = requireElement(documentObj, 'detail-overlay');
  const detailPanel = requireElement(documentObj, 'detail-panel');
  const htmlElement = documentObj.documentElement;

  const backgroundElements = [
    documentObj.querySelector('.header'),
    documentObj.querySelector('.container'),
    documentObj.querySelector('.footer'),
    scrollTopBtn
  ].filter(Boolean);

  const toolDropdown = requireElement(documentObj, 'tool-dropdown');
  const toolFilterToggle = requireElement(documentObj, 'tool-filter-toggle');
  const toolFilterLabel = requireElement(documentObj, 'tool-filter-label');
  const toolFilterPanel = requireElement(documentObj, 'tool-filter-panel');
  const tagDropdown = requireElement(documentObj, 'tag-dropdown');
  const tagFilterToggle = requireElement(documentObj, 'tag-filter-toggle');
  const tagFilterLabel = requireElement(documentObj, 'tag-filter-label');
  const tagFilterPanel = requireElement(documentObj, 'tag-filter-panel');

  const prefersReducedMotionQuery = windowObj.matchMedia('(prefers-reduced-motion: reduce)');
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

  const filterControls = {
    tool: {
      root: toolDropdown,
      toggle: toolFilterToggle,
      label: toolFilterLabel,
      panel: toolFilterPanel,
      values: allTools,
      emptyLabel: 'All tools',
      pluralLabel: 'tools',
      labelFormatter: (value) => getToolLabel(galleryConfig, value)
    },
    tag: {
      root: tagDropdown,
      toggle: tagFilterToggle,
      label: tagFilterLabel,
      panel: tagFilterPanel,
      values: allTags,
      emptyLabel: 'All tags',
      pluralLabel: 'tags',
      labelFormatter: (value) => getTagLabel(galleryConfig, value)
    }
  };

  let currentPage = DEFAULTS.page;
  let currentFilter = DEFAULTS.q;
  let currentSort = DEFAULTS.sort;
  let currentTools = [];
  let currentTags = [];
  let expandedId = null;
  let debounceTimer = null;
  let suppressPush = false;
  let lastExpandedTrigger = null;
  let overlayResetTimer = null;
  let openFilterKey = null;

  filterReset.innerHTML = ICONS.reset;

  buildFilterPanels();
  readStateFromURL();

  const savedTheme = runtime.readStorage('theme', 'dark') || 'dark';
  applyTheme(savedTheme, false);

  syncUIToState();
  renderContent();
  documentObj.body.classList.remove('js-loading');

  themeToggle.addEventListener('click', () => {
    const currentTheme = htmlElement.getAttribute('data-theme');
    applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
  });

  searchInput.addEventListener('input', (event) => {
    clearTimeout(debounceTimer);
    debounceTimer = windowObj.setTimeout(() => {
      currentFilter = event.target.value.toLowerCase();
      currentPage = 1;
      applyStateChange({ closeFilter: true });
    }, 150);
  });

  searchClear.addEventListener('click', () => {
    searchInput.value = '';
    currentFilter = '';
    currentPage = 1;
    applyStateChange({ closeFilter: true, focusTarget: searchInput });
  });

  Object.entries(filterControls).forEach(([key, control]) => {
    control.toggle.addEventListener('click', (event) => {
      event.stopPropagation();
      toggleFilterDropdown(key);
    });

    control.panel.addEventListener('change', (event) => {
      const checkbox = event.target.closest('.filter-dropdown-checkbox');
      if (!checkbox) {
        return;
      }

      const nextValues = new Set(getSelectedValues(key));
      if (checkbox.checked) {
        nextValues.add(checkbox.value);
      } else {
        nextValues.delete(checkbox.value);
      }

      setSelectedValues(key, [...nextValues]);
      currentPage = 1;
      applyStateChange();
    });
  });

  sortToggle.addEventListener('click', () => {
    currentSort = currentSort === 'newest' ? 'oldest' : 'newest';
    currentPage = 1;
    applyStateChange({ closeFilter: true });
  });

  filterReset.addEventListener('click', resetFilters);
  noResultsReset.addEventListener('click', resetFilters);

  detailOverlay.addEventListener('click', (event) => {
    if (event.target.closest('[data-close-detail]')) {
      closeExpandedOverlay();
    }
  });

  grid.addEventListener('click', (event) => {
    const card = event.target.closest('.artifact-card');
    if (!card) {
      return;
    }

    toggleExpand(card.dataset.id, card);
  });

  grid.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return;
    }

    const card = event.target.closest('.artifact-card');
    if (!card) {
      return;
    }

    event.preventDefault();
    toggleExpand(card.dataset.id, card);
  });

  paginationContainer.addEventListener('click', (event) => {
    const button = event.target.closest('[data-page]');
    if (!button || button.disabled) {
      return;
    }

    const page = Number.parseInt(button.dataset.page, 10);
    if (!page || page === currentPage) {
      return;
    }

    currentPage = page;
    closeExpandedOverlay({ restoreFocus: false, immediate: true });
    pushState();
    renderContent();
    scrollToTop();
  });

  documentObj.addEventListener('click', (event) => {
    if (!openFilterKey) {
      return;
    }

    const activeControl = filterControls[openFilterKey];
    if (!activeControl.root.contains(event.target)) {
      closeFilterDropdown();
    }
  });

  documentObj.addEventListener('keydown', (event) => {
    switch (event.key) {
      case 'Tab':
        trapDetailOverlayFocus(event);
        return;

      case 'Escape':
        if (openFilterKey) {
          event.preventDefault();
          closeFilterDropdown();
          return;
        }

        if (!expandedId) {
          return;
        }

        event.preventDefault();
        closeExpandedOverlay();
        return;

      case '/': {
        if (expandedId) {
          return;
        }

        const activeElement = documentObj.activeElement;
        const isInput = activeElement && (
          activeElement.tagName === 'INPUT'
          || activeElement.tagName === 'TEXTAREA'
          || activeElement.isContentEditable
        );

        if (isInput) {
          return;
        }

        event.preventDefault();
        closeFilterDropdown();
        searchInput.focus();
        return;
      }

      default:
        return;
    }
  });

  windowObj.addEventListener('popstate', () => {
    closeFilterDropdown();
    closeExpandedOverlay({ restoreFocus: false, immediate: true });
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
        scrollTopBtn.classList.toggle('visible', windowObj.scrollY > SCROLL_TOP_THRESHOLD);
        scrollTicking = false;
      });
      scrollTicking = true;
    },
    { passive: true }
  );

  scrollTopBtn.addEventListener('click', () => {
    scrollToTop();
  });

  function prefersReducedMotion() {
    return prefersReducedMotionQuery.matches;
  }

  function getScrollBehavior() {
    return prefersReducedMotion() ? 'auto' : 'smooth';
  }

  function scrollToTop() {
    windowObj.scrollTo({ top: 0, behavior: getScrollBehavior() });
  }

  function applyTheme(theme, persist = true) {
    htmlElement.setAttribute('data-theme', theme);
    if (persist) {
      runtime.writeStorage('theme', theme);
    }

    const meta = documentObj.querySelector('meta[name="theme-color"]');
    if (meta) {
      meta.setAttribute('content', THEME_COLORS[theme] || THEME_COLORS.dark);
    }
  }

  function buildFilterPanels() {
    Object.entries(filterControls).forEach(([key, control]) => {
      control.panel.innerHTML = buildFilterPanelHtml({
        key,
        values: control.values,
        labelFormatter: control.labelFormatter
      });
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

  function buildQueryString() {
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

    const nextUrl = buildQueryString();
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
    updateFilterDropdownUI(filterControls.tool, currentTools);
    updateFilterDropdownUI(filterControls.tag, currentTags);
    updateSortToggle();
    updateFilterResetVisibility();
  }

  function updateSearchClearVisibility() {
    searchClear.classList.toggle('hidden', searchInput.value.length === 0);
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

  function setBackgroundContentInert(isInert) {
    const updateInteractivity = isInert ? makeElementInert : restoreElementInteractivity;
    backgroundElements.forEach(updateInteractivity);
  }

  function makeElementInert(element) {
    if (element.inert) {
      return;
    }

    element.dataset.prevAriaHidden = element.getAttribute('aria-hidden') ?? '';
    element.setAttribute('aria-hidden', 'true');
    element.inert = true;
  }

  function restoreElementInteractivity(element) {
    if (!element.inert) {
      return;
    }

    if (element.dataset.prevAriaHidden === '') {
      element.removeAttribute('aria-hidden');
    } else {
      element.setAttribute('aria-hidden', element.dataset.prevAriaHidden);
    }

    delete element.dataset.prevAriaHidden;
    element.inert = false;
  }

  function applyStateChange({ closeFilter = false, focusTarget = null } = {}) {
    if (closeFilter) {
      closeFilterDropdown();
    }

    closeExpandedOverlay({ restoreFocus: false, immediate: true });
    syncUIToState();
    pushState();
    renderContent();

    if (focusTarget) {
      focusTarget.focus();
    }
  }

  function trapDetailOverlayFocus(event) {
    if (!expandedId) {
      return false;
    }

    const focusableSelectors = [
      'a[href]',
      'button:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      '[tabindex]:not([tabindex="-1"])'
    ].join(',');

    const focusableElements = [...detailPanel.querySelectorAll(focusableSelectors)].filter(
      (element) => !element.hasAttribute('hidden') && element.getAttribute('aria-hidden') !== 'true'
    );

    if (focusableElements.length === 0) {
      event.preventDefault();
      detailPanel.focus({ preventScroll: true });
      return true;
    }

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];
    const activeElement = documentObj.activeElement;

    if (event.shiftKey) {
      if (activeElement === firstElement || !detailPanel.contains(activeElement)) {
        event.preventDefault();
        lastElement.focus({ preventScroll: true });
        return true;
      }

      return false;
    }

    if (activeElement === lastElement || !detailPanel.contains(activeElement)) {
      event.preventDefault();
      firstElement.focus({ preventScroll: true });
      return true;
    }

    return false;
  }

  function getSelectedValues(key) {
    switch (key) {
      case 'tool':
        return currentTools;
      case 'tag':
        return currentTags;
      default:
        throw new Error(`Unknown filter key: ${key}`);
    }
  }

  function setSelectedValues(key, values) {
    switch (key) {
      case 'tool':
        currentTools = normalizeSelection(values, allTools);
        return;
      case 'tag':
        currentTags = normalizeSelection(values, allTags);
        return;
      default:
        throw new Error(`Unknown filter key: ${key}`);
    }
  }

  function toggleFilterDropdown(key) {
    if (openFilterKey === key) {
      closeFilterDropdown();
      return;
    }

    openFilterDropdown(key);
  }

  function openFilterDropdown(key) {
    closeFilterDropdown();
    openFilterKey = key;
    const control = filterControls[key];
    control.root.classList.add('open');
    control.toggle.setAttribute('aria-expanded', 'true');
    control.panel.setAttribute('aria-hidden', 'false');
  }

  function closeFilterDropdown() {
    if (!openFilterKey) {
      return;
    }

    const control = filterControls[openFilterKey];
    control.root.classList.remove('open');
    control.toggle.setAttribute('aria-expanded', 'false');
    control.panel.setAttribute('aria-hidden', 'true');
    openFilterKey = null;
  }

  function resetFilters() {
    currentFilter = '';
    currentTools = [];
    currentTags = [];
    currentPage = DEFAULTS.page;
    searchInput.value = '';
    applyStateChange({ closeFilter: true, focusTarget: searchInput });
  }

  function getCardById(id) {
    return id ? grid.querySelector(`.artifact-card[data-id="${id}"]`) : null;
  }

  function toggleExpand(id, triggerCard) {
    if (expandedId === id) {
      closeExpandedOverlay();
      return;
    }

    openExpandedOverlay(id, triggerCard);
  }

  function openExpandedOverlay(id, triggerCard) {
    const item = artifactById.get(id);
    if (!item) {
      return;
    }

    clearTimeout(overlayResetTimer);
    expandedId = id;
    lastExpandedTrigger = triggerCard || getCardById(id);
    detailPanel.innerHTML = createDetailContent(item);
    detailOverlay.classList.add('visible');
    detailOverlay.setAttribute('aria-hidden', 'false');
    documentObj.body.classList.add('detail-open');
    setBackgroundContentInert(true);
    updateExpandedCardState();

    const panelRect = detailPanel.getBoundingClientRect();
    const originRect = lastExpandedTrigger ? lastExpandedTrigger.getBoundingClientRect() : null;
    applyDetailMotion(originRect, panelRect);

    windowObj.requestAnimationFrame(() => {
      detailOverlay.classList.add('open');
      const closeButton = detailPanel.querySelector('.detail-close');
      if (closeButton) {
        closeButton.focus({ preventScroll: true });
      }
    });
  }

  function closeExpandedOverlay({ restoreFocus = true, immediate = false } = {}) {
    if (!expandedId && !detailOverlay.classList.contains('visible')) {
      return;
    }

    const closingId = expandedId;
    const fallbackCard = lastExpandedTrigger && documentObj.body.contains(lastExpandedTrigger)
      ? lastExpandedTrigger
      : getCardById(closingId);

    if (!immediate) {
      const panelRect = detailPanel.getBoundingClientRect();
      const originRect = fallbackCard ? fallbackCard.getBoundingClientRect() : null;
      applyDetailMotion(originRect, panelRect);
    } else {
      clearDetailMotion();
    }

    expandedId = null;
    updateExpandedCardState();
    detailOverlay.classList.remove('open');
    detailOverlay.setAttribute('aria-hidden', 'true');
    documentObj.body.classList.remove('detail-open');

    const finishClose = () => {
      detailOverlay.classList.remove('visible');
      detailPanel.innerHTML = '';
      clearDetailMotion();
      setBackgroundContentInert(false);
      if (restoreFocus && fallbackCard) {
        fallbackCard.focus({ preventScroll: true });
      }
      lastExpandedTrigger = null;
    };

    clearTimeout(overlayResetTimer);
    if (immediate || prefersReducedMotion()) {
      finishClose();
      return;
    }

    overlayResetTimer = windowObj.setTimeout(finishClose, DETAIL_CLOSE_DELAY);
  }

  function applyDetailMotion(originRect, panelRect) {
    clearDetailMotion();
    if (prefersReducedMotion() || !originRect || !panelRect.width || !panelRect.height) {
      return;
    }

    const panelCenterX = panelRect.left + panelRect.width / 2;
    const panelCenterY = panelRect.top + panelRect.height / 2;
    const originCenterX = originRect.left + originRect.width / 2;
    const originCenterY = originRect.top + originRect.height / 2;
    const scaleX = Math.max(0.36, Math.min(1, originRect.width / panelRect.width));
    const scaleY = Math.max(0.24, Math.min(1, originRect.height / panelRect.height));

    detailPanel.style.setProperty('--detail-from-x', `${originCenterX - panelCenterX}px`);
    detailPanel.style.setProperty('--detail-from-y', `${originCenterY - panelCenterY}px`);
    detailPanel.style.setProperty('--detail-from-scale-x', `${scaleX}`);
    detailPanel.style.setProperty('--detail-from-scale-y', `${scaleY}`);
  }

  function clearDetailMotion() {
    detailPanel.style.removeProperty('--detail-from-x');
    detailPanel.style.removeProperty('--detail-from-y');
    detailPanel.style.removeProperty('--detail-from-scale-x');
    detailPanel.style.removeProperty('--detail-from-scale-y');
  }

  function updateExpandedCardState() {
    grid.querySelectorAll('.artifact-card').forEach((card) => {
      const isExpanded = card.dataset.id === expandedId;
      card.classList.toggle('expanded', isExpanded);
      card.setAttribute('aria-expanded', String(isExpanded));
    });
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
      updateExpandedCardState();
      return;
    }

    noResults.classList.add('hidden');
    grid.innerHTML = buildGridHtml(pageItems, expandedId);
    updateExpandedCardState();
    renderPagination(paginationContainer, currentPage, totalPages);
  }
}
