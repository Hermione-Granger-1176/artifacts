/* Sticky section-progress nav, pipeline jump links, and the summary timeline. */

import { SECTIONS, SUMMARY_STEPS } from "./data.js";
import { byId, makeEl, clear } from "./dom.js";

function scrollToSection(id) {
  const target = byId(id);
  if (target) {
    target.scrollIntoView({ behavior: "smooth" });
  }
}

export function initNavigation() {
  const nodesWrap = byId("navNodes");
  const fill = byId("navFill");
  const label = byId("navLabel");
  if (!nodesWrap || !fill || !label) {
    return;
  }

  const nodeButtons = SECTIONS.map((section, i) => {
    const node = makeEl("button", "pc-nav-node");
    node.type = "button";
    node.setAttribute("aria-label", section.label);
    node.appendChild(makeEl("span", "", String(i + 1)));
    node.appendChild(makeEl("span", "pc-nav-tip", section.label));
    node.addEventListener("click", () => scrollToSection(section.id));
    nodesWrap.appendChild(node);
    return node;
  });

  function updateNav(idx) {
    nodeButtons.forEach((node, i) => {
      node.classList.toggle("done", i < idx);
      node.classList.toggle("active", i === idx);
    });
    const pct = SECTIONS.length > 1 ? (idx / (SECTIONS.length - 1)) * 100 : 0;
    fill.style.width = `${pct}%`;
    label.textContent = SECTIONS[idx].label;
  }

  updateNav(0);

  if (typeof IntersectionObserver === "function") {
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          const idx = SECTIONS.findIndex((section) => section.id === entry.target.id);
          if (idx >= 0) {
            updateNav(idx);
          }
        }
      }
    }, { threshold: 0.3 });

    for (const section of SECTIONS) {
      const target = byId(section.id);
      if (target) {
        observer.observe(target);
      }
    }
  }

  const pipeline = byId("pipelineDiagram");
  if (pipeline) {
    for (const node of pipeline.querySelectorAll("[data-target]")) {
      const el = /** @type {HTMLElement} */ (node);
      el.addEventListener("click", () => scrollToSection(el.dataset.target ?? ""));
    }
  }

  renderTimeline();
}

function renderTimeline() {
  const wrap = byId("summaryTimeline");
  if (!wrap) {
    return;
  }
  clear(wrap);

  SUMMARY_STEPS.forEach((step, i) => {
    const row = makeEl("div", `pc-timeline-row is-${step.tone}`);

    const rail = makeEl("div", "pc-timeline-rail");
    rail.appendChild(makeEl("div", "pc-timeline-dot", String(i + 1)));
    if (i < SUMMARY_STEPS.length - 1) {
      rail.appendChild(makeEl("div", "pc-timeline-line"));
    }

    const body = makeEl("div", "pc-timeline-body");
    body.appendChild(makeEl("div", "pc-timeline-title", step.title));
    body.appendChild(makeEl("div", "pc-timeline-desc", step.desc));

    row.append(rail, body);
    wrap.appendChild(row);
  });
}
