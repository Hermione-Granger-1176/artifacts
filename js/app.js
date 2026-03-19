document.addEventListener('DOMContentLoaded', () => {
    const grid = document.getElementById('artifacts-grid');
    const searchInput = document.getElementById('search-input');
    const searchClear = document.getElementById('search-clear');
    const sortToggle = document.getElementById('sort-toggle');
    const filterReset = document.getElementById('filter-reset');
    const themeToggle = document.getElementById('theme-toggle');
    const noResults = document.getElementById('no-results');
    const noResultsReset = document.getElementById('no-results-reset');
    const paginationContainer = document.getElementById('pagination');
    const scrollTopBtn = document.getElementById('scroll-top');
    const detailOverlay = document.getElementById('detail-overlay');
    const detailPanel = document.getElementById('detail-panel');
    const htmlElement = document.documentElement;

    const toolDropdown = document.getElementById('tool-dropdown');
    const toolFilterToggle = document.getElementById('tool-filter-toggle');
    const toolFilterLabel = document.getElementById('tool-filter-label');
    const toolFilterPanel = document.getElementById('tool-filter-panel');
    const tagDropdown = document.getElementById('tag-dropdown');
    const tagFilterToggle = document.getElementById('tag-filter-toggle');
    const tagFilterLabel = document.getElementById('tag-filter-label');
    const tagFilterPanel = document.getElementById('tag-filter-panel');

    const prefersReducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

    const ITEMS_PER_PAGE = 12;
    const THEME_COLORS = { dark: '#202020', light: '#f0f0f0' };
    const DEFAULTS = { page: 1, sort: 'newest', q: '' };
    const SCROLL_TOP_THRESHOLD = 300;
    const DETAIL_CLOSE_DELAY = 360;

    const OPEN_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>';
    const EXPAND_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"></path></svg>';
    const RESET_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 2v6h6"></path><path d="M21 12A9 9 0 0 0 6 5.3L3 8"></path><path d="M21 22v-6h-6"></path><path d="M3 12a9 9 0 0 0 15 6.7l3-2.7"></path></svg>';
    const CHEVRON_LEFT = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>';
    const CHEVRON_RIGHT = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>';
    const CHEVRON_FIRST = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="13 18 7 12 13 6"></polyline><line x1="17" y1="6" x2="17" y2="18"></line></svg>';
    const CHEVRON_LAST = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="11 18 17 12 11 6"></polyline><line x1="7" y1="6" x2="7" y2="18"></line></svg>';
    const CLOSE_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>';

    const allArtifacts = window.ARTIFACTS_DATA || [];
    const artifactById = new Map(allArtifacts.map((item) => [item.id, item]));
    const allTags = [...new Set(allArtifacts.flatMap((item) => item.tags))].sort();
    const allTools = [...new Set(allArtifacts.flatMap((item) => item.tools))].sort();

    const filterControls = {
        tool: {
            root: toolDropdown,
            toggle: toolFilterToggle,
            label: toolFilterLabel,
            panel: toolFilterPanel,
            values: allTools,
            emptyLabel: 'All tools',
            pluralLabel: 'tools',
            labelFormatter: toolLabel,
        },
        tag: {
            root: tagDropdown,
            toggle: tagFilterToggle,
            label: tagFilterLabel,
            panel: tagFilterPanel,
            values: allTags,
            emptyLabel: 'All tags',
            pluralLabel: 'tags',
            labelFormatter: (value) => value,
        },
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

    filterReset.innerHTML = RESET_ICON;

    buildFilterPanels();
    readStateFromURL();

    const savedTheme = localStorage.getItem('theme') || 'dark';
    applyTheme(savedTheme, false);

    syncUIToState();
    renderContent();
    document.body.classList.remove('js-loading');

    themeToggle.addEventListener('click', () => {
        const currentTheme = htmlElement.getAttribute('data-theme');
        applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
    });

    searchInput.addEventListener('input', (event) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            currentFilter = event.target.value.toLowerCase();
            currentPage = 1;
            closeFilterDropdown();
            closeExpandedOverlay({ restoreFocus: false, immediate: true });
            syncUIToState();
            pushState();
            renderContent();
        }, 150);
    });

    searchClear.addEventListener('click', () => {
        searchInput.value = '';
        currentFilter = '';
        currentPage = 1;
        closeFilterDropdown();
        closeExpandedOverlay({ restoreFocus: false, immediate: true });
        syncUIToState();
        pushState();
        renderContent();
        searchInput.focus();
    });

    Object.entries(filterControls).forEach(([key, control]) => {
        control.toggle.addEventListener('click', (event) => {
            event.stopPropagation();
            toggleFilterDropdown(key);
        });

        control.panel.addEventListener('change', (event) => {
            const checkbox = event.target.closest('.filter-dropdown-checkbox');
            if (!checkbox) return;

            const nextValues = getSelectedValues(key).slice();
            if (checkbox.checked) {
                nextValues.push(checkbox.value);
            } else {
                const index = nextValues.indexOf(checkbox.value);
                if (index >= 0) nextValues.splice(index, 1);
            }

            setSelectedValues(key, nextValues);
            currentPage = 1;
            closeExpandedOverlay({ restoreFocus: false, immediate: true });
            syncUIToState();
            pushState();
            renderContent();
        });
    });

    sortToggle.addEventListener('click', () => {
        currentSort = currentSort === 'newest' ? 'oldest' : 'newest';
        currentPage = 1;
        closeFilterDropdown();
        closeExpandedOverlay({ restoreFocus: false, immediate: true });
        syncUIToState();
        pushState();
        renderContent();
    });

    filterReset.addEventListener('click', () => {
        resetFilters();
    });

    noResultsReset.addEventListener('click', () => {
        resetFilters();
    });

    detailOverlay.addEventListener('click', (event) => {
        if (event.target.closest('[data-close-detail]')) {
            closeExpandedOverlay();
        }
    });

    grid.addEventListener('click', (event) => {
        const card = event.target.closest('.artifact-card');
        if (!card) return;
        toggleExpand(card.dataset.id, card);
    });

    grid.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        const card = event.target.closest('.artifact-card');
        if (!card) return;
        event.preventDefault();
        toggleExpand(card.dataset.id, card);
    });

    paginationContainer.addEventListener('click', (event) => {
        const button = event.target.closest('[data-page]');
        if (!button || button.disabled) return;
        const page = parseInt(button.dataset.page, 10);
        if (!page || page === currentPage) return;

        currentPage = page;
        closeExpandedOverlay({ restoreFocus: false, immediate: true });
        pushState();
        renderContent();
        scrollToTop();
    });

    document.addEventListener('click', (event) => {
        if (!openFilterKey) return;
        const activeControl = filterControls[openFilterKey];
        if (!activeControl.root.contains(event.target)) {
            closeFilterDropdown();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && openFilterKey) {
            event.preventDefault();
            closeFilterDropdown();
            return;
        }

        if (event.key === 'Escape' && expandedId) {
            event.preventDefault();
            closeExpandedOverlay();
            return;
        }

        if (event.key === '/') {
            const activeElement = document.activeElement;
            const isInput = activeElement && (
                activeElement.tagName === 'INPUT'
                || activeElement.tagName === 'TEXTAREA'
                || activeElement.isContentEditable
            );

            if (!isInput) {
                event.preventDefault();
                closeFilterDropdown();
                searchInput.focus();
            }
        }
    });

    window.addEventListener('popstate', () => {
        closeFilterDropdown();
        closeExpandedOverlay({ restoreFocus: false, immediate: true });
        suppressPush = true;
        readStateFromURL();
        syncUIToState();
        renderContent();
        suppressPush = false;
    });

    let scrollTicking = false;
    window.addEventListener('scroll', () => {
        if (!scrollTicking) {
            requestAnimationFrame(() => {
                scrollTopBtn.classList.toggle('visible', window.scrollY > SCROLL_TOP_THRESHOLD);
                scrollTicking = false;
            });
            scrollTicking = true;
        }
    }, { passive: true });

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
        window.scrollTo({ top: 0, behavior: getScrollBehavior() });
    }

    function applyTheme(theme, persist = true) {
        htmlElement.setAttribute('data-theme', theme);
        if (persist) localStorage.setItem('theme', theme);
        const meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.setAttribute('content', THEME_COLORS[theme] || THEME_COLORS.dark);
    }

    function buildFilterPanels() {
        Object.entries(filterControls).forEach(([key, control]) => {
            control.panel.innerHTML = control.values.map((value) => `
                <label class="filter-dropdown-item" role="option" aria-selected="false">
                    <input class="filter-dropdown-checkbox" type="checkbox" value="${escapeHtml(value)}" data-filter-group="${key}">
                    <span>${escapeHtml(control.labelFormatter(value))}</span>
                </label>
            `).join('');
        });
    }

    function readStateFromURL() {
        const params = new URLSearchParams(window.location.search);
        currentPage = Math.max(1, parseInt(params.get('page'), 10) || DEFAULTS.page);
        currentFilter = (params.get('q') || DEFAULTS.q).toLowerCase();
        currentSort = params.get('sort') === 'oldest' ? 'oldest' : DEFAULTS.sort;
        currentTools = normalizeSelection(splitListParam(params.get('tool')), allTools);
        currentTags = normalizeSelection(splitListParam(params.get('tag')), allTags);
        searchInput.value = params.get('q') || '';
    }

    function splitListParam(rawValue) {
        if (!rawValue) return [];
        return rawValue.split(',').map((value) => value.trim()).filter(Boolean);
    }

    function normalizeSelection(values, allowedValues) {
        const allowedSet = new Set(allowedValues);
        const unique = [];

        values.forEach((value) => {
            if (allowedSet.has(value) && !unique.includes(value)) {
                unique.push(value);
            }
        });

        return allowedValues.filter((value) => unique.includes(value));
    }

    function buildQueryString() {
        const params = new URLSearchParams();
        if (currentPage > 1) params.set('page', currentPage);
        if (currentTools.length > 0) params.set('tool', currentTools.join(','));
        if (currentTags.length > 0) params.set('tag', currentTags.join(','));
        if (currentSort !== DEFAULTS.sort) params.set('sort', currentSort);
        if (currentFilter) params.set('q', currentFilter);
        const queryString = params.toString();
        return queryString ? `${window.location.pathname}?${queryString}` : window.location.pathname;
    }

    function pushState() {
        if (suppressPush) return;
        const nextUrl = buildQueryString();
        const currentUrl = `${window.location.pathname}${window.location.search}`;
        if (nextUrl !== currentUrl) {
            history.pushState(null, '', nextUrl);
        }
    }

    function syncUIToState() {
        if (searchInput.value.toLowerCase() !== currentFilter) {
            searchInput.value = currentFilter;
        }

        updateSearchClearVisibility();
        updateFilterDropdownUI('tool');
        updateFilterDropdownUI('tag');
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

    function getSelectedValues(key) {
        return key === 'tool' ? currentTools : currentTags;
    }

    function setSelectedValues(key, values) {
        if (key === 'tool') {
            currentTools = normalizeSelection(values, allTools);
            return;
        }
        currentTags = normalizeSelection(values, allTags);
    }

    function getFilterSummary(selectedValues, control) {
        if (selectedValues.length === 0) return control.emptyLabel;
        if (selectedValues.length === 1) return control.labelFormatter(selectedValues[0]);
        return `${selectedValues.length} ${control.pluralLabel}`;
    }

    function updateFilterDropdownUI(key) {
        const control = filterControls[key];
        const selectedValues = getSelectedValues(key);
        control.label.textContent = getFilterSummary(selectedValues, control);

        control.panel.querySelectorAll('.filter-dropdown-checkbox').forEach((checkbox) => {
            const isChecked = selectedValues.includes(checkbox.value);
            checkbox.checked = isChecked;
            const option = checkbox.closest('.filter-dropdown-item');
            option.setAttribute('aria-selected', String(isChecked));
            option.classList.toggle('is-selected', isChecked);
        });
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
    }

    function closeFilterDropdown() {
        if (!openFilterKey) return;
        const control = filterControls[openFilterKey];
        control.root.classList.remove('open');
        control.toggle.setAttribute('aria-expanded', 'false');
        openFilterKey = null;
    }

    function resetFilters() {
        currentFilter = '';
        currentTools = [];
        currentTags = [];
        currentPage = DEFAULTS.page;
        searchInput.value = '';

        closeFilterDropdown();
        closeExpandedOverlay({ restoreFocus: false, immediate: true });
        syncUIToState();
        pushState();
        renderContent();
        searchInput.focus();
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
        if (!item) return;

        clearTimeout(overlayResetTimer);
        expandedId = id;
        lastExpandedTrigger = triggerCard || getCardById(id);
        detailPanel.innerHTML = createDetailContent(item);
        detailOverlay.classList.add('visible');
        detailOverlay.setAttribute('aria-hidden', 'false');
        document.body.classList.add('detail-open');
        updateExpandedCardState();

        const panelRect = detailPanel.getBoundingClientRect();
        const originRect = lastExpandedTrigger ? lastExpandedTrigger.getBoundingClientRect() : null;
        applyDetailMotion(originRect, panelRect);

        requestAnimationFrame(() => {
            detailOverlay.classList.add('open');
            const closeButton = detailPanel.querySelector('.detail-close');
            if (closeButton) {
                closeButton.focus({ preventScroll: true });
            }
        });
    }

    function closeExpandedOverlay({ restoreFocus = true, immediate = false } = {}) {
        if (!expandedId && !detailOverlay.classList.contains('visible')) return;

        const closingId = expandedId;
        const fallbackCard = lastExpandedTrigger && document.body.contains(lastExpandedTrigger)
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
        document.body.classList.remove('detail-open');

        const finishClose = () => {
            detailOverlay.classList.remove('visible');
            detailPanel.innerHTML = '';
            clearDetailMotion();
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

        overlayResetTimer = window.setTimeout(finishClose, DETAIL_CLOSE_DELAY);
    }

    function applyDetailMotion(originRect, panelRect) {
        clearDetailMotion();
        if (prefersReducedMotion() || !originRect || !panelRect.width || !panelRect.height) {
            return;
        }

        const panelCenterX = panelRect.left + (panelRect.width / 2);
        const panelCenterY = panelRect.top + (panelRect.height / 2);
        const originCenterX = originRect.left + (originRect.width / 2);
        const originCenterY = originRect.top + (originRect.height / 2);
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

    function getSearchableText(item) {
        return `${item.name} ${item.description} ${item.tags.join(' ')} ${item.tools.join(' ')} ${item.id}`.toLowerCase();
    }

    function escapeHtml(unsafe) {
        if (!unsafe) return '';
        return unsafe.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    function toolLabel(tool) {
        const labels = { claude: 'Claude', chatgpt: 'ChatGPT', gemini: 'Gemini' };
        return labels[tool] || tool.charAt(0).toUpperCase() + tool.slice(1);
    }

    function updateExpandedCardState() {
        grid.querySelectorAll('.artifact-card').forEach((card) => {
            const isExpanded = card.dataset.id === expandedId;
            card.classList.toggle('expanded', isExpanded);
            card.setAttribute('aria-expanded', String(isExpanded));
        });
    }

    function createDetailContent(item) {
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
                    ${CLOSE_ICON}
                </button>
                <div class="detail-content">
                    <h2 id="detail-title" class="detail-title">${escapeHtml(item.name)}</h2>
                    <p class="detail-description">${escapeHtml(description)}</p>
                </div>
                <a class="detail-open-icon" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" aria-label="Open artifact in a new tab">
                    ${OPEN_ICON}
                </a>
            </div>
        `;
    }

    function renderContent() {
        const filtered = allArtifacts.filter((item) => {
            if (currentTools.length > 0 && !item.tools.some((tool) => currentTools.includes(tool))) return false;
            if (currentTags.length > 0 && !item.tags.some((tag) => currentTags.includes(tag))) return false;
            if (currentFilter && !getSearchableText(item).includes(currentFilter)) return false;
            return true;
        }).sort((left, right) => {
            return currentSort === 'newest'
                ? right.id.localeCompare(left.id)
                : left.id.localeCompare(right.id);
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
        grid.innerHTML = buildGridHtml(pageItems);
        updateExpandedCardState();
        renderPagination(totalPages);
    }

    function buildGridHtml(items) {
        return items.map(createCard).join('');
    }

    function createCard(item) {
        const isExpanded = expandedId === item.id;
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
                        <span class="card-open-indicator" aria-hidden="true">${EXPAND_ICON}</span>
                    </div>
                </div>
            </article>
        `;
    }

    function renderPagination(totalPages) {
        if (totalPages <= 1) {
            paginationContainer.innerHTML = '';
            return;
        }

        const pages = getPageNumbers(currentPage, totalPages);
        let html = '';

        const onFirst = currentPage === 1;
        const onLast = currentPage === totalPages;

        html += `<button class="page-btn" data-page="1" ${onFirst ? 'disabled' : ''} aria-label="First page">${CHEVRON_FIRST}</button>`;
        html += `<button class="page-btn" data-page="${currentPage - 1}" ${onFirst ? 'disabled' : ''} aria-label="Previous page">${CHEVRON_LEFT}</button>`;

        for (const page of pages) {
            if (page === '...') {
                html += '<span class="page-ellipsis">&hellip;</span>';
            } else {
                const isActive = page === currentPage;
                html += `<button class="page-btn ${isActive ? 'active' : ''}" data-page="${page}" ${isActive ? 'aria-current="page"' : ''} aria-label="Page ${page}">${page}</button>`;
            }
        }

        html += `<button class="page-btn" data-page="${currentPage + 1}" ${onLast ? 'disabled' : ''} aria-label="Next page">${CHEVRON_RIGHT}</button>`;
        html += `<button class="page-btn" data-page="${totalPages}" ${onLast ? 'disabled' : ''} aria-label="Last page">${CHEVRON_LAST}</button>`;

        paginationContainer.innerHTML = html;
    }

    function getPageNumbers(current, total) {
        if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1);

        const pages = [];
        const addPage = (page) => {
            if (!pages.includes(page)) pages.push(page);
        };

        addPage(1);
        addPage(2);
        for (let page = current - 1; page <= current + 1; page += 1) {
            if (page >= 1 && page <= total) addPage(page);
        }
        addPage(total - 1);
        addPage(total);

        pages.sort((left, right) => left - right);

        const result = [];
        for (let index = 0; index < pages.length; index += 1) {
            if (index > 0 && pages[index] - pages[index - 1] > 1) result.push('...');
            result.push(pages[index]);
        }
        return result;
    }
});
