/* Sticky section-progress nav: numbered nodes, a progress fill, and an
 * IntersectionObserver scroll spy. Styled by the shared .section-nav rules. */

/**
 * @typedef {{ id: string, label: string }} NavSection
 */

function scrollToSection(id) {
  const target = document.getElementById(id);
  if (target) {
    target.scrollIntoView({ behavior: "smooth" });
  }
}

/**
 * Build one numbered node per section inside the nodes container and keep the
 * fill width, node states, and label in sync with the section in view.
 * Anchor ids default to the kebab-case markup used by newer apps.
 *
 * @param {NavSection[]} sections
 * @param {{ nodesId?: string, fillId?: string, labelId?: string }} [anchors]
 * @returns {void}
 */
export function initSectionNav(sections, anchors = {}) {
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

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) {
          continue;
        }
        const index = sections.findIndex((section) => section.id === entry.target.id);
        if (index >= 0) {
          updateNav(index);
        }
      }
    },
    { threshold: 0.3 }
  );

  for (const section of sections) {
    const target = document.getElementById(section.id);
    if (target) {
      observer.observe(target);
    }
  }
}
