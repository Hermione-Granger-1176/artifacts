/* Sticky section-progress nav: numbered nodes, a progress fill, and a scroll
 * spy. One scroll-progress number drives the active node, the label, and the
 * fill, so they always agree. Styled by the shared .section-nav rules. */

import { createFrameScheduler } from "./frame-scheduler.js";
import { scrollBehavior } from "./motion.js";

/**
 * @typedef {{ id: string, label: string, target: HTMLElement }} NavSection
 */

// Skeleton with the ids that initSectionNav reads (nav-nodes, nav-fill,
// nav-label). The label starts empty. initSectionNav writes the active
// section's label when it runs.
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
 * Inject the shared section-nav skeleton into the page's empty
 * `[data-section-nav]` slot. The injected ids (nav-fill, nav-nodes, nav-label)
 * are the ones initSectionNav reads.
 *
 * @param {Element | null} mount - The slot, as `document.querySelector` returns it. Every page that calls this ships one.
 * @returns {void}
 */
export function renderSectionNav(mount) {
  /** @type {Element} */ (mount).innerHTML = SECTION_NAV_MARKUP.trim();
}

/**
 * Scroll the element with the given id into view. The scroll behavior is "auto"
 * when the user prefers reduced motion and "smooth" otherwise. Apps call this for
 * their own jump links, and the scroll matches the nav nodes. Does nothing when no
 * element has the id.
 * @param {string} id - Target element id.
 * @returns {void}
 */
export function scrollToSection(id) {
  const target = document.getElementById(id);
  if (target) {
    target.scrollIntoView({ behavior: scrollBehavior() });
  }
}

/**
 * Collect nav sections from the document. Each element with an id and a
 * non-empty data-nav-label becomes one section, in document order. Apps declare
 * the nav in markup.
 * @returns {NavSection[]}
 */
function discoverSections() {
  /** @type {NavSection[]} */
  const found = [];
  for (const target of document.querySelectorAll("[data-nav-label]")) {
    const label = (target.getAttribute("data-nav-label") || "").trim();
    if (target.id && label) {
      found.push({ id: target.id, label, target: /** @type {HTMLElement} */ (target) });
    }
  }
  return found;
}

/**
 * Scroll offsets at which each section becomes the active one: when its top
 * reaches the scanline. Sections the page cannot scroll that far split the
 * last stretch of scrolling into equal shares, the final section included, so
 * it becomes active before the bottom and stays active down to it. A page with
 * no scroll range keeps the natural anchors, so its first section stays active.
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
  if (end > 0 && anchors.length > 1 && anchors[anchors.length - 1] >= end) {
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
      // Two sections can share an offset, for example a hidden one that
      // reports 0. Dividing by that zero span would return NaN.
      const span = anchors[index] - start;
      return index - 1 + (span > 0 ? Math.max(0, scrollY - start) / span : 0);
    }
  }
  return Math.max(0, anchors.length - 1);
}

/**
 * Build one numbered node per section inside the nodes container and keep the
 * fill, node states, and label in sync with the reader's scroll position.
 * Sections are the elements with an id and a data-nav-label, in document
 * order. Call it after renderSectionNav, on a page with at least one section.
 *
 * Section positions are measured at init, on window resize, and when
 * `document.body` resizes. A scroll frame only maps `scrollY` onto the measured
 * offsets and does not measure.
 *
 * @returns {void}
 */
export function initSectionNav() {
  const sections = discoverSections();
  const nodesWrap = /** @type {HTMLElement} */ (document.getElementById("nav-nodes"));
  const fillEl = /** @type {HTMLElement} */ (document.getElementById("nav-fill"));
  const labelEl = /** @type {HTMLElement} */ (document.getElementById("nav-label"));
  const targets = sections.map((section) => section.target);

  const nodeButtons = sections.map((section, index) => {
    const node = document.createElement("button");
    node.type = "button";
    // Each node starts in its top-of-page state, with the first one active.
    node.className = index === 0 ? "section-nav-node active" : "section-nav-node";
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

  labelEl.textContent = sections[0].label;

  /** @type {number[]} */
  let sectionOffsets = [];
  let drawnIndex = 0;
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
  new ResizeObserver(scheduleMeasure).observe(document.body);
}
