/* Section-progress nav wiring, pipeline jump links, and the summary timeline. */

import { initSectionNav, renderSectionNav, scrollToSection } from "../../../../js/modules/section-nav.js";
import { SECTIONS, SUMMARY_STEPS } from "./data.js";
import { byId, makeEl, clear } from "./dom.js";

export function initNavigation() {
  renderSectionNav(document.querySelector("[data-section-nav]"));
  initSectionNav(SECTIONS);

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
