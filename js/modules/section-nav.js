/* Sticky section-progress nav: numbered nodes, a progress fill, and a scroll
 * spy. One scroll-progress number drives the active node, the label, and the
 * fill, so they always agree. Styled by the shared .section-nav rules. */

import { createFrameScheduler } from "./frame-scheduler.js";

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
 * Scroll offsets at which each section becomes the active one: when its top
 * reaches the scanline. Sections the page cannot scroll that far split the
 * last stretch of scrolling into equal shares, the final section included, so
 * it becomes active before the bottom and stays active down to it.
 * @param {number[]} tops - Section tops in document coordinates, in order.
 * @param {number} scanline - Distance of the scanline below the viewport top.
 * @param {number} end - Deepest scroll offset the page reaches.
 * @returns {number[]} Non-decreasing offsets, one per section.
 */
export function sectionAnchors(tops, scanline, end) {
  /** @type {number[]} */
  const anchors = [];
  for (const top of tops) {
    anchors.push(Math.max(anchors.at(-1) ?? 0, top - scanline));
  }
  const firstUnreachable = Math.max(1, anchors.findIndex((anchor) => anchor >= end));
  if (anchors.length > 1 && anchors[anchors.length - 1] >= end) {
    const from = Math.min(anchors[firstUnreachable - 1], end);
    const steps = anchors.length - firstUnreachable + 1;
    for (let index = firstUnreachable; index < anchors.length; index += 1) {
      anchors[index] = from + ((end - from) * (index - firstUnreachable + 1)) / steps;
    }
  }
  return anchors;
}

/**
 * Where a scroll offset sits between the section anchors, from 0 at the first
 * section to `anchors.length - 1` at the last. The whole part is the active
 * section and the fraction is how far the reader is towards the next one.
 * @param {number[]} anchors - Offsets from sectionAnchors.
 * @param {number} scrollY - Current scroll offset.
 * @returns {number}
 */
export function scrollProgress(anchors, scrollY) {
  for (let index = 1; index < anchors.length; index += 1) {
    if (scrollY < anchors[index]) {
      const start = anchors[index - 1];
      return index - 1 + Math.max(0, scrollY - start) / (anchors[index] - start);
    }
  }
  return Math.max(0, anchors.length - 1);
}

/**
 * Build one numbered node per section inside the nodes container and keep the
 * fill, node states, and label in sync with the reader's scroll position.
 * Anchor ids default to the kebab-case markup used by newer apps.
 *
 * Section positions are measured only when the layout changes (load, resize,
 * content growing or shrinking); a scroll frame just maps scrollY onto them,
 * so scrolling never forces a layout.
 *
 * @param {NavSection[]} [explicitSections] - Optional fixed list; when omitted,
 *   sections are discovered from elements carrying data-nav-label. Sections
 *   missing from the page get no node.
 * @param {{ nodesId?: string, fillId?: string, labelId?: string }} [anchors]
 * @returns {void}
 */
export function initSectionNav(explicitSections, anchors = {}) {
  const sections = (explicitSections ?? discoverSections()).filter((section) => document.getElementById(section.id));
  const { nodesId = "nav-nodes", fillId = "nav-fill", labelId = "nav-label" } = anchors;
  const nodesWrap = document.getElementById(nodesId);
  const fill = document.getElementById(fillId);
  const label = document.getElementById(labelId);
  if (sections.length === 0 || !nodesWrap || !fill || !label) {
    return;
  }
  const fillEl = fill;
  const labelEl = label;
  const targets = sections.map((section) => /** @type {HTMLElement} */ (document.getElementById(section.id)));

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

  /** @type {number[]} */
  let sectionOffsets = [];
  let drawnIndex = -1;
  let drawnScale = "";

  // Read every section's top once per layout.
  function measure() {
    const scrollY = window.scrollY || 0;
    const viewportHeight = window.innerHeight || 0;
    const tops = targets.map((target) => target.getBoundingClientRect().top + scrollY);
    const end = document.documentElement.scrollHeight - viewportHeight - 1;
    sectionOffsets = sectionAnchors(tops, viewportHeight * 0.35, end);
  }

  // The fill spans node center to node center, so a progress of k / (n - 1)
  // ends exactly on node k. Node classes and the label change only when the
  // active section does.
  function draw() {
    const progress = scrollProgress(sectionOffsets, window.scrollY || 0);
    const scale = `${sections.length > 1 ? progress / (sections.length - 1) : 0} 1`;
    if (scale !== drawnScale) {
      drawnScale = scale;
      fillEl.style.scale = scale;
    }
    const activeIndex = Math.floor(progress);
    if (activeIndex === drawnIndex) {
      return;
    }
    drawnIndex = activeIndex;
    nodeButtons.forEach((node, index) => {
      node.classList.toggle("done", index < activeIndex);
      node.classList.toggle("active", index === activeIndex);
    });
    labelEl.textContent = sections[activeIndex].label;
  }

  const scheduleDraw = createFrameScheduler(draw);
  const scheduleMeasure = createFrameScheduler(() => {
    measure();
    draw();
  });

  measure();
  draw();
  window.addEventListener("scroll", scheduleDraw, { passive: true });
  window.addEventListener("resize", scheduleMeasure, { passive: true });
  if (typeof ResizeObserver === "function") {
    new ResizeObserver(scheduleMeasure).observe(document.body);
  }
}
