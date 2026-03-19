document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const grid = document.getElementById('artifacts-grid');
    const searchInput = document.getElementById('search-input');
    const searchClear = document.getElementById('search-clear');
    const sortButtons = document.querySelectorAll('.btn-sort');
    const themeToggle = document.getElementById('theme-toggle');
    const noResults = document.getElementById('no-results');
    const noResultsReset = document.getElementById('no-results-reset');
    const resultsCount = document.getElementById('results-count');
    const paginationContainer = document.getElementById('pagination');
    const resetFiltersBtn = document.getElementById('reset-filters');
    const activeFiltersBar = document.getElementById('active-filters');
    const scrollTopBtn = document.getElementById('scroll-top');
    const htmlElement = document.documentElement;

    // Filter Elements
    const toolFilters = document.getElementById('tool-filters');
    const tagFiltersContainer = document.getElementById('tag-filters');

    // Constants
    const ITEMS_PER_PAGE = 12;
    const THEME_COLORS = { dark: '#202020', light: '#f0f0f0' };
    const DEFAULTS = { page: 1, tool: 'all', tag: 'all', sort: 'newest', q: '' };
    const SCROLL_TOP_THRESHOLD = 300;

    // SVG icons
    const LAUNCH_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>';
    const CHEVRON_LEFT = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>';
    const CHEVRON_RIGHT = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>';
    const CHEVRON_FIRST = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="13 18 7 12 13 6"></polyline><line x1="17" y1="6" x2="17" y2="18"></line></svg>';
    const CHEVRON_LAST = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="11 18 17 12 11 6"></polyline><line x1="7" y1="6" x2="7" y2="18"></line></svg>';

    // State
    const allArtifacts = window.ARTIFACTS_DATA || [];
    let currentPage = 1;
    let currentFilter = '';
    let currentSort = 'newest';
    let currentTool = 'all';
    let currentTag = 'all';
    let expandedId = null;
    let debounceTimer = null;
    let suppressPush = false;

    // Build lookup map
    const artifactById = new Map(allArtifacts.map(item => [item.id, item]));

    // Collect all unique tags and tools from data
    const allTags = [...new Set(allArtifacts.flatMap(item => item.tags))].sort();
    const allTools = [...new Set(allArtifacts.flatMap(item => item.tools))].sort();

    // ─── URL State Management ───────────────────────────────────────────

    function readStateFromURL() {
        const params = new URLSearchParams(window.location.search);
        currentPage = Math.max(1, parseInt(params.get('page'), 10) || DEFAULTS.page);
        currentTool = params.get('tool') || DEFAULTS.tool;
        currentTag = params.get('tag') || DEFAULTS.tag;
        currentSort = params.get('sort') || DEFAULTS.sort;
        currentFilter = (params.get('q') || DEFAULTS.q).toLowerCase();
        searchInput.value = params.get('q') || '';
    }

    function buildQueryString() {
        const params = new URLSearchParams();
        if (currentPage > 1) params.set('page', currentPage);
        if (currentTool !== DEFAULTS.tool) params.set('tool', currentTool);
        if (currentTag !== DEFAULTS.tag) params.set('tag', currentTag);
        if (currentSort !== DEFAULTS.sort) params.set('sort', currentSort);
        if (currentFilter) params.set('q', currentFilter);
        const qs = params.toString();
        return qs ? `?${qs}` : window.location.pathname;
    }

    function pushState() {
        if (suppressPush) return;
        const url = buildQueryString();
        if (url !== window.location.search && url !== `${window.location.pathname}${window.location.search}`) {
            history.pushState(null, '', url);
        }
    }

    window.addEventListener('popstate', () => {
        suppressPush = true;
        readStateFromURL();
        syncUIToState();
        renderContent();
        suppressPush = false;
    });

    // ─── Theme Management ───────────────────────────────────────────────

    const savedTheme = localStorage.getItem('theme') || 'dark';
    applyTheme(savedTheme, false);

    themeToggle.addEventListener('click', () => {
        const current = htmlElement.getAttribute('data-theme');
        applyTheme(current === 'dark' ? 'light' : 'dark');
    });

    function applyTheme(theme, persist = true) {
        htmlElement.setAttribute('data-theme', theme);
        if (persist) localStorage.setItem('theme', theme);
        const meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.setAttribute('content', THEME_COLORS[theme] || THEME_COLORS.dark);
    }

    // ─── Dynamic Filter Buttons ─────────────────────────────────────────

    allTools.forEach(tool => {
        const btn = document.createElement('button');
        btn.className = 'btn-filter';
        btn.dataset.tool = tool;
        btn.innerHTML = `${escapeHtml(toolLabel(tool))}<span class="filter-count"></span>`;
        toolFilters.appendChild(btn);
    });

    allTags.forEach(tag => {
        const btn = document.createElement('button');
        btn.className = 'btn-filter';
        btn.dataset.tag = tag;
        btn.innerHTML = `${escapeHtml(tag)}<span class="filter-count"></span>`;
        tagFiltersContainer.appendChild(btn);
    });

    // ─── Initialize from URL ────────────────────────────────────────────

    readStateFromURL();
    syncUIToState();
    renderContent();
    document.body.classList.remove('js-loading');

    function syncUIToState() {
        if (searchInput.value.toLowerCase() !== currentFilter) {
            searchInput.value = currentFilter;
        }
        updateSearchClearVisibility();

        sortButtons.forEach(btn => {
            const isActive = btn.dataset.sort === currentSort;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-pressed', String(isActive));
        });

        toolFilters.querySelectorAll('.btn-filter').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tool === currentTool);
        });

        tagFiltersContainer.querySelectorAll('.btn-filter').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tag === currentTag);
        });

        updateResetButtonVisibility();
        renderActiveFilters();
    }

    // ─── Event Listeners ────────────────────────────────────────────────

    searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            currentFilter = e.target.value.toLowerCase();
            currentPage = 1;
            expandedId = null;
            updateSearchClearVisibility();
            pushState();
            renderContent();
        }, 150);
    });

    searchClear.addEventListener('click', () => {
        searchInput.value = '';
        currentFilter = '';
        currentPage = 1;
        expandedId = null;
        updateSearchClearVisibility();
        pushState();
        renderContent();
        searchInput.focus();
    });

    sortButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            sortButtons.forEach(b => { b.classList.remove('active'); b.setAttribute('aria-pressed', 'false'); });
            btn.classList.add('active');
            btn.setAttribute('aria-pressed', 'true');
            currentSort = btn.dataset.sort;
            currentPage = 1;
            expandedId = null;
            pushState();
            renderContent();
        });
    });

    toolFilters.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-filter');
        if (!btn) return;
        toolFilters.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentTool = btn.dataset.tool;
        currentPage = 1;
        expandedId = null;
        pushState();
        renderContent();
    });

    tagFiltersContainer.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-filter');
        if (!btn) return;
        tagFiltersContainer.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentTag = btn.dataset.tag;
        currentPage = 1;
        expandedId = null;
        pushState();
        renderContent();
    });

    resetFiltersBtn.addEventListener('click', resetAllFilters);
    noResultsReset.addEventListener('click', resetAllFilters);

    // Card clicks (event delegation)
    grid.addEventListener('click', (e) => {
        // Don't handle clicks on expand panel elements
        if (e.target.closest('.expand-panel')) return;
        const card = e.target.closest('.artifact-card');
        if (!card) return;
        toggleExpand(card.dataset.id);
    });

    grid.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        if (e.target.closest('.expand-panel')) return;
        const card = e.target.closest('.artifact-card');
        if (!card) return;
        e.preventDefault();
        toggleExpand(card.dataset.id);
    });

    // Pagination
    paginationContainer.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-page]');
        if (!btn || btn.disabled) return;
        const page = parseInt(btn.dataset.page, 10);
        if (page && page !== currentPage) {
            currentPage = page;
            expandedId = null;
            pushState();
            renderContent();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && expandedId) {
            expandedId = null;
            renderContent();
            return;
        }
        if (e.key === '/' && !expandedId) {
            const active = document.activeElement;
            const isInput = active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.isContentEditable);
            if (!isInput) {
                e.preventDefault();
                searchInput.focus();
            }
        }
    });

    // Scroll to top
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
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    // ─── Expand/Collapse ────────────────────────────────────────────────

    function toggleExpand(id) {
        if (expandedId === id) {
            expandedId = null;
        } else {
            expandedId = id;
        }
        renderContent();

        // Scroll the expanded panel into view
        if (expandedId) {
            requestAnimationFrame(() => {
                const panel = document.querySelector('.expand-panel.open');
                if (panel) {
                    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            });
        }
    }

    // ─── Reset ──────────────────────────────────────────────────────────

    function resetAllFilters() {
        currentFilter = '';
        currentTool = DEFAULTS.tool;
        currentTag = DEFAULTS.tag;
        currentSort = DEFAULTS.sort;
        currentPage = DEFAULTS.page;
        expandedId = null;
        searchInput.value = '';

        syncUIToState();
        pushState();
        renderContent();
        searchInput.focus();
    }

    function updateSearchClearVisibility() {
        searchClear.classList.toggle('hidden', searchInput.value.length === 0);
    }

    function updateResetButtonVisibility() {
        const hasActiveFilters =
            currentTool !== DEFAULTS.tool ||
            currentTag !== DEFAULTS.tag ||
            currentSort !== DEFAULTS.sort ||
            currentFilter !== DEFAULTS.q;
        resetFiltersBtn.classList.toggle('hidden', !hasActiveFilters);
    }

    // ─── Active Filters Bar ─────────────────────────────────────────────

    function renderActiveFilters() {
        const chips = [];
        if (currentTool !== DEFAULTS.tool) {
            chips.push({ label: `Tool: ${toolLabel(currentTool)}`, action: 'tool' });
        }
        if (currentTag !== DEFAULTS.tag) {
            chips.push({ label: `Tag: ${currentTag}`, action: 'tag' });
        }
        if (currentSort !== DEFAULTS.sort) {
            chips.push({ label: `Sort: ${currentSort === 'oldest' ? 'Oldest first' : 'Newest first'}`, action: 'sort' });
        }
        if (currentFilter) {
            chips.push({ label: `Search: "${currentFilter}"`, action: 'search' });
        }

        if (chips.length === 0) {
            activeFiltersBar.classList.add('hidden');
            activeFiltersBar.innerHTML = '';
            return;
        }

        activeFiltersBar.classList.remove('hidden');
        activeFiltersBar.innerHTML = chips.map(chip =>
            `<button class="active-filter-chip" data-dismiss="${escapeHtml(chip.action)}" aria-label="Remove filter: ${escapeHtml(chip.label)}">${escapeHtml(chip.label)} <span class="chip-dismiss">&times;</span></button>`
        ).join('');
    }

    activeFiltersBar.addEventListener('click', (e) => {
        const chip = e.target.closest('.active-filter-chip');
        if (!chip) return;
        const action = chip.dataset.dismiss;

        switch (action) {
            case 'tool':
                currentTool = DEFAULTS.tool;
                break;
            case 'tag':
                currentTag = DEFAULTS.tag;
                break;
            case 'sort':
                currentSort = DEFAULTS.sort;
                break;
            case 'search':
                currentFilter = '';
                searchInput.value = '';
                break;
            default:
                return;
        }

        currentPage = 1;
        expandedId = null;
        syncUIToState();
        pushState();
        renderContent();
    });

    // ─── Utility Functions ──────────────────────────────────────────────

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

    function toolClass(tool) {
        const known = ['claude', 'chatgpt', 'gemini'];
        return known.includes(tool) ? tool : 'default';
    }

    // ─── Filter Counts ──────────────────────────────────────────────────

    function updateFilterCounts() {
        const toolCounts = Object.fromEntries(allTools.map(t => [t, 0]));
        const tagCounts = Object.fromEntries(allTags.map(t => [t, 0]));

        allArtifacts.forEach(item => {
            const matchesTag = currentTag === 'all' || item.tags.includes(currentTag);
            const matchesSearch = !currentFilter || getSearchableText(item).includes(currentFilter);

            if (matchesTag && matchesSearch) {
                item.tools.forEach(t => {
                    if (toolCounts[t] !== undefined) toolCounts[t]++;
                });
            }

            const matchesTool = currentTool === 'all' || item.tools.includes(currentTool);
            if (matchesTool && matchesSearch) {
                item.tags.forEach(t => {
                    if (tagCounts[t] !== undefined) tagCounts[t]++;
                });
            }
        });

        toolFilters.querySelectorAll('.btn-filter').forEach(btn => {
            const countSpan = btn.querySelector('.filter-count');
            if (!countSpan) return;
            const tool = btn.dataset.tool;
            if (tool === 'all') return;
            countSpan.textContent = toolCounts[tool] || 0;
        });

        tagFiltersContainer.querySelectorAll('.btn-filter').forEach(btn => {
            const countSpan = btn.querySelector('.filter-count');
            if (!countSpan) return;
            const tag = btn.dataset.tag;
            if (tag === 'all') return;
            countSpan.textContent = tagCounts[tag] || 0;
        });
    }

    // ─── Render ─────────────────────────────────────────────────────────

    function renderContent() {
        let filtered = allArtifacts.filter(item => {
            if (currentTool !== 'all' && !item.tools.includes(currentTool)) return false;
            if (currentTag !== 'all' && !item.tags.includes(currentTag)) return false;
            if (currentFilter && !getSearchableText(item).includes(currentFilter)) return false;
            return true;
        });

        filtered.sort((a, b) => {
            return currentSort === 'newest'
                ? b.id.localeCompare(a.id)
                : a.id.localeCompare(b.id);
        });

        updateFilterCounts();
        updateResetButtonVisibility();
        renderActiveFilters();

        const totalItems = filtered.length;
        const totalPages = Math.max(1, Math.ceil(totalItems / ITEMS_PER_PAGE));
        currentPage = Math.max(1, Math.min(currentPage, totalPages));
        const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
        const endIndex = Math.min(startIndex + ITEMS_PER_PAGE, totalItems);
        const pageItems = filtered.slice(startIndex, endIndex);

        if (totalItems === 0) {
            resultsCount.textContent = 'No artifacts found';
        } else {
            resultsCount.textContent = `Showing ${startIndex + 1}\u2013${endIndex} of ${totalItems} artifacts`;
        }

        if (totalItems === 0) {
            grid.innerHTML = '';
            noResults.classList.remove('hidden');
            paginationContainer.innerHTML = '';
            return;
        }

        noResults.classList.add('hidden');
        grid.innerHTML = buildGridHtml(pageItems);
        renderPagination(totalPages);
    }

    function buildGridHtml(items) {
        return items.map(item => {
            const expandPanel = expandedId === item.id ? createExpandPanel(item) : '';
            return createCard(item) + expandPanel;
        }).join('');
    }

    function createCard(item) {
        const isExpanded = expandedId === item.id;
        const toolsHtml = item.tools.map(t =>
            `<span class="tool-badge ${escapeHtml(toolClass(t))}">${escapeHtml(toolLabel(t))}</span>`
        ).join('');

        const thumbnailHtml = item.thumbnail
            ? `<img class="card-thumbnail" src="${escapeHtml(item.thumbnail)}" alt="${escapeHtml(item.name)}" loading="lazy">`
            : `<div class="card-thumbnail-placeholder">&#9881;</div>`;

        return `
            <article class="artifact-card ${isExpanded ? 'expanded' : ''}" data-id="${escapeHtml(item.id)}" tabindex="0" role="button"
                aria-label="View details for ${escapeHtml(item.name)}" aria-expanded="${isExpanded}">
                ${thumbnailHtml}
                <div class="card-overlay">
                    <div class="card-tools">${toolsHtml}</div>
                    <div class="card-name">${escapeHtml(item.name)}</div>
                </div>
            </article>
        `;
    }

    function createExpandPanel(item) {
        const tagsHtml = item.tags.map(t =>
            `<span class="expand-tag-badge">${escapeHtml(t)}</span>`
        ).join('');

        const toolsHtml = item.tools.map(t =>
            `<span class="expand-tool-badge ${escapeHtml(toolClass(t))}">${escapeHtml(toolLabel(t))}</span>`
        ).join('');

        const bgHtml = item.thumbnail
            ? `<img class="expand-bg" src="${escapeHtml(item.thumbnail)}" alt="">`
            : '<div class="expand-bg-placeholder"></div>';

        return `
            <div class="expand-panel open">
                <div class="expand-inner">
                    ${bgHtml}
                    <div class="expand-gradient"></div>
                    <button class="expand-close" aria-label="Close details" onclick="event.stopPropagation(); document.querySelector('.artifact-card[data-id=&quot;${escapeHtml(item.id)}&quot;]').click();">&times;</button>
                    <div class="expand-content">
                        <h3 class="expand-name">${escapeHtml(item.name)}</h3>
                        <p class="expand-description">${escapeHtml(item.description)}</p>
                        <div class="expand-meta">
                            ${toolsHtml}
                            ${tagsHtml}
                        </div>
                        <a class="btn-launch" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">
                            ${LAUNCH_ICON}
                            Launch Artifact
                        </a>
                    </div>
                </div>
            </div>
        `;
    }

    // ─── Pagination ─────────────────────────────────────────────────────

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
        if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);

        const pages = [];
        const addPage = (p) => { if (!pages.includes(p)) pages.push(p); };

        addPage(1);
        addPage(2);
        for (let i = current - 1; i <= current + 1; i++) {
            if (i >= 1 && i <= total) addPage(i);
        }
        addPage(total - 1);
        addPage(total);

        pages.sort((a, b) => a - b);

        const result = [];
        for (let i = 0; i < pages.length; i++) {
            if (i > 0 && pages[i] - pages[i - 1] > 1) result.push('...');
            result.push(pages[i]);
        }
        return result;
    }
});
