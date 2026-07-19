/* Sticky section-progress nav: numbered nodes, a progress fill, and a scroll
 * spy. An IntersectionObserver tracks which sections are on screen and the
 * active one is chosen by position, so short headings and tall cards coexist.
 * Styled by the shared .section-nav rules. */

/**
 * @typedef {{ id: string, label: string }} NavSection
 */

// Static skeleton with the kebab-case ids that initSectionNav defaults to.
// The label starts empty because initSectionNav writes the active section's
// label as soon as it runs.
const SECTION_NAV_MARKUP = `
  <nav class="section-nav" aria-label="Section progress">
    <div class="section-nav-inner">
      <div class="section-nav-track">
        <div class="section-nav-line"></div>
        <div class="section-nav-fill" id="nav-fill"></div>
        <div class="section-nav-nodes" id="nav-nodes"></div>
      </div>
      <div class="section-nav-label" id="nav-label"></div>
    </div>
  </nav>
`;

/**
 * Inject the shared section-nav skeleton into a mount slot, mirroring how
 * app-shell fills its placeholder slots: fill the slot's innerHTML only when it
 * has no element children yet, so a repeat call is a no-op. The injected ids
 * (nav-fill, nav-nodes, nav-label) match initSectionNav's defaults.
 *
 * @param {Element | null} mount - Slot element to fill.
 * @returns {void}
 */
export function renderSectionNav(mount) {
  if (!mount || mount.childElementCount > 0) {
    return;
  }
  mount.innerHTML = SECTION_NAV_MARKUP.trim();
}

/**
 * Scroll a section into view, honoring the user's reduced-motion preference.
 * Shared so apps route their own jump links (pipeline nodes, buttons) through
 * the same reduced-motion-aware scroll as the nav nodes.
 * @param {string} id - Target element id.
 * @returns {void}
 */
export function scrollToSection(id) {
  const target = document.getElementById(id);
  if (target) {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
  }
}

/**
 * Collect nav sections from the document: every element carrying both an id
 * and a data-nav-label attribute becomes one section, in document order, so
 * apps declare their nav in markup instead of a parallel JS list.
 * @returns {NavSection[]}
 */
function discoverSections() {
  /** @type {NavSection[]} */
  const found = [];
  for (const target of document.querySelectorAll("[data-nav-label]")) {
    const label = (target.getAttribute("data-nav-label") || "").trim();
    if (target.id && label) {
      found.push({ id: target.id, label });
    }
  }
  return found;
}

/**
 * Build one numbered node per section inside the nodes container and keep the
 * fill width, node states, and label in sync with the section in view.
 * Anchor ids default to the kebab-case markup used by newer apps.
 *
 * @param {NavSection[]} [explicitSections] - Optional fixed list; when omitted,
 *   sections are discovered from elements carrying data-nav-label.
 * @param {{ nodesId?: string, fillId?: string, labelId?: string }} [anchors]
 * @returns {void}
 */
export function initSectionNav(explicitSections, anchors = {}) {
  const sections = explicitSections ?? discoverSections();
  const { nodesId = "nav-nodes", fillId = "nav-fill", labelId = "nav-label" } = anchors;
  const nodesWrap = document.getElementById(nodesId);
  const fill = document.getElementById(fillId);
  const label = document.getElementById(labelId);
  if (sections.length === 0 || !nodesWrap || !fill || !label) {
    return;
  }
  const fillEl = fill;
  const labelEl = label;

  const nodeButtons = sections.map((section, index) => {
    const node = document.createElement("button");
    node.type = "button";
    node.className = "section-nav-node";
    node.setAttribute("aria-label", section.label);

    const number = document.createElement("span");
    number.textContent = String(index + 1);
    const tip = document.createElement("span");
    tip.className = "section-nav-tip";
    tip.textContent = section.label;
    node.append(number, tip);

    node.addEventListener("click", () => scrollToSection(section.id));
    nodesWrap.appendChild(node);
    return node;
  });

  function updateNav(activeIndex) {
    nodeButtons.forEach((node, index) => {
      node.classList.toggle("done", index < activeIndex);
      node.classList.toggle("active", index === activeIndex);
    });
    const percent = sections.length > 1 ? (activeIndex / (sections.length - 1)) * 100 : 0;
    fillEl.style.width = `${percent}%`;
    labelEl.textContent = sections[activeIndex].label;
  }

  updateNav(0);

  if (typeof IntersectionObserver !== "function") {
    return;
  }

  /** @type {{ index: number, target: Element }[]} */
  const observed = [];
  sections.forEach((section, index) => {
    const target = document.getElementById(section.id);
    if (target) {
      observed.push({ index, target });
    }
  });

  /** @type {Set<number>} */
  const visible = new Set();

  // Activate the last on-screen section whose top has passed a scanline near
  // the top of the viewport, falling back to the first on-screen section. A
  // single "last section to cross a visibility threshold wins" rule misses
  // click-jumps to sections that are already partially visible (no threshold
  // fires, so the nav never advances) and lets a short heading beat the tall
  // card the reader is actually looking at. At the bottom of the page the
  // scanline can no longer reach the final section's top, so the deepest
  // on-screen section wins there instead.
  function selectActive() {
    if (visible.size === 0) {
      return;
    }
    const viewportHeight = window.innerHeight || 0;
    const scanline = viewportHeight * 0.35;
    let candidate = -1;
    let firstVisible = -1;
    let lastVisible = -1;
    for (const { index, target } of observed) {
      if (!visible.has(index)) {
        continue;
      }
      if (firstVisible === -1) {
        firstVisible = index;
      }
      lastVisible = index;
      if (target.getBoundingClientRect().top <= scanline) {
        candidate = index;
      }
    }
    const doc = document.documentElement;
    const scrollable = doc ? doc.scrollHeight > viewportHeight + 2 : false;
    const atBottom = doc && (window.scrollY || 0) + viewportHeight >= doc.scrollHeight - 2;
    if (scrollable && atBottom) {
      updateNav(lastVisible);
      return;
    }
    updateNav(candidate === -1 ? firstVisible : candidate);
  }

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        const item = observed.find(({ target }) => target === entry.target);
        if (!item) {
          continue;
        }
        if (entry.isIntersecting) {
          visible.add(item.index);
        } else {
          visible.delete(item.index);
        }
      }
      selectActive();
    },
    { threshold: 0 }
  );

  for (const { target } of observed) {
    observer.observe(target);
  }

  // Scroll and resize re-run the position check because the observer only
  // fires on enter/leave; the scanline can cross section tops between those
  // events, and layout changes move them without any scrolling.
  window.addEventListener("scroll", selectActive, { passive: true });
  window.addEventListener("resize", selectActive, { passive: true });
}
