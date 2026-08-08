/**
 * Renders a document model onto the on-screen A4 paper.
 *
 * Two constraints shape this module. The app ships under a self-only
 * Content-Security-Policy with no `unsafe-inline`, so inline `style`
 * attributes never apply: per-vendor colour and type come in as CSS custom
 * properties set through CSSOM, which CSP does not police. And the repo bans
 * assigning template literals to `innerHTML`, so everything below is built
 * with `createElement` and `textContent`, which also makes the generated
 * content injection-proof by construction.
 *
 * @module paper-render
 */

/**
 * @typedef {import("./document-model.js").DocumentModel} DocumentModel
 * @typedef {import("./document-model.js").DocumentBlock} DocumentBlock
 * @typedef {import("./vendors.js").Vendor} Vendor
 */

import { initialsOf } from "./format.js";

/**
 * Create an element with an optional class list and text.
 * @param {Document} doc - Owning document.
 * @param {string} tag - Tag name.
 * @param {string} [className] - Space-separated class names.
 * @param {string} [text] - Text content.
 * @returns {HTMLElement} The new element.
 */
function make(doc, tag, className, text) {
  const element = doc.createElement(tag);

  if (className) {
    element.className = className;
  }

  if (text !== undefined) {
    element.textContent = text;
  }

  return element;
}

/**
 * Append one element per line of text.
 * @param {Document} doc - Owning document.
 * @param {HTMLElement} parent - Element to append into.
 * @param {string[]} lines - Lines to render.
 * @param {string} className - Class for each line element.
 * @returns {void}
 */
function appendLines(doc, parent, lines, className) {
  for (const line of lines) {
    parent.appendChild(make(doc, "div", className, line));
  }
}

/**
 * Build a two-column key/value table.
 * @param {Document} doc - Owning document.
 * @param {[string, string][]} pairs - Label/value pairs.
 * @param {string} className - Class for the table element.
 * @returns {HTMLElement} The table.
 */
function keyValueTable(doc, pairs, className) {
  const table = make(doc, "table", className);
  const body = make(doc, "tbody");

  for (const [label, value] of pairs) {
    const row = make(doc, "tr");
    row.appendChild(make(doc, "th", "vd-kv-key", label));
    row.appendChild(make(doc, "td", "vd-kv-value", value));
    body.appendChild(row);
  }

  table.appendChild(body);
  return table;
}

/**
 * Build the vendor logo lockup for a vendor's chosen treatment.
 * @param {Document} doc - Owning document.
 * @param {Vendor} vendor - Vendor whose logo to draw.
 * @returns {HTMLElement} Logo element.
 */
export function buildLogo(doc, vendor) {
  const logo = make(doc, "div", `vd-logo is-${vendor.logoStyle}`);
  const [firstWord, ...restWords] = vendor.name.split(" ");

  if (vendor.logoStyle === "block" || vendor.logoStyle === "stamp") {
    logo.appendChild(make(doc, "span", "vd-logo-mark", initialsOf(vendor.name)));
    logo.appendChild(make(doc, "span", "vd-logo-name", vendor.name));
    return logo;
  }

  if (vendor.logoStyle === "leaf" || vendor.logoStyle === "mono") {
    const glyph = vendor.logoStyle === "leaf" ? "☘" : "☁";
    logo.appendChild(make(doc, "span", "vd-logo-glyph", glyph));
    logo.appendChild(make(doc, "span", "vd-logo-name", vendor.name));
    return logo;
  }

  if (vendor.logoStyle === "thin") {
    logo.appendChild(make(doc, "span", "vd-logo-name", firstWord));
    logo.appendChild(make(doc, "span", "vd-logo-sub", restWords.join(" ")));
    return logo;
  }

  logo.appendChild(make(doc, "span", "vd-logo-name", vendor.name));
  return logo;
}

/**
 * Render one model block.
 * @param {Document} doc - Owning document.
 * @param {DocumentBlock} block - Block to render.
 * @returns {HTMLElement} Element for the block.
 */
function renderBlock(doc, block) {
  switch (block.kind) {
    case "stamp": {
      const row = make(doc, "div", "vd-stamp-row");
      row.appendChild(make(doc, "span", "vd-stamp", block.text));
      return row;
    }

    case "parties": {
      const wrapper = make(doc, "div", "vd-parties");
      const party = make(doc, "div", "vd-party");
      party.appendChild(make(doc, "div", "vd-party-label", block.label));
      const [name, ...rest] = block.lines;
      party.appendChild(make(doc, "div", "vd-party-name", name));
      appendLines(doc, party, rest, "vd-party-line");
      wrapper.appendChild(party);
      wrapper.appendChild(keyValueTable(doc, block.meta, "vd-meta"));
      return wrapper;
    }

    case "keygrid": {
      const grid = make(doc, "div", "vd-keygrid");

      for (const column of block.columns) {
        grid.appendChild(keyValueTable(doc, column, "vd-kv"));
      }

      return grid;
    }

    case "partypair": {
      const table = make(doc, "table", "vd-partypair");
      const head = make(doc, "thead");
      const headRow = make(doc, "tr");

      for (const heading of block.headings) {
        headRow.appendChild(make(doc, "th", "vd-partypair-head", heading));
      }

      head.appendChild(headRow);
      table.appendChild(head);

      const body = make(doc, "tbody");
      const bodyRow = make(doc, "tr");

      for (const lines of block.columns) {
        const cell = make(doc, "td", "vd-partypair-cell");
        const [name, ...rest] = lines;
        cell.appendChild(make(doc, "div", "vd-party-name", name));
        appendLines(doc, cell, rest, "vd-party-line");
        bodyRow.appendChild(cell);
      }

      body.appendChild(bodyRow);
      table.appendChild(body);
      return table;
    }

    case "table": {
      const table = make(doc, "table", block.dense ? "vd-items is-dense" : "vd-items");
      const head = make(doc, "thead");
      const headRow = make(doc, "tr");

      for (const column of block.columns) {
        headRow.appendChild(make(doc, "th", `is-${column.align}`, column.label));
      }

      head.appendChild(headRow);
      table.appendChild(head);

      const body = make(doc, "tbody");

      for (const row of block.rows) {
        const tableRow = make(doc, "tr");
        row.forEach((cell, index) => {
          const align = block.columns[index]?.align ?? "left";
          tableRow.appendChild(make(doc, "td", `is-${align}`, cell));
        });
        body.appendChild(tableRow);
      }

      table.appendChild(body);

      if (block.footer) {
        const foot = make(doc, "tfoot");
        const footRow = make(doc, "tr");
        block.footer.forEach((cell, index) => {
          const align = block.columns[index]?.align ?? "left";
          footRow.appendChild(make(doc, "td", `is-${align}`, cell));
        });
        foot.appendChild(footRow);
        table.appendChild(foot);
      }

      return table;
    }

    case "totals": {
      const wrapper = make(doc, "div", "vd-totals-row");
      const table = make(doc, "table", "vd-totals");
      const body = make(doc, "tbody");

      block.rows.forEach(([label, value], index) => {
        const row = make(doc, "tr", index === block.emphasisIndex ? "is-emphasis" : undefined);
        row.appendChild(make(doc, "th", "vd-totals-label", label));
        row.appendChild(make(doc, "td", "vd-totals-value", value));
        body.appendChild(row);
      });

      table.appendChild(body);
      wrapper.appendChild(table);
      return wrapper;
    }

    case "words":
      return make(doc, "div", "vd-words", block.text);

    case "note":
      return make(doc, "p", `vd-note is-${block.tone}`, block.text);

    case "callout":
      return make(doc, "div", "vd-doc-callout", block.text);

    case "chips": {
      const wrapper = make(doc, "div", "vd-doc-chips");

      for (const [label, value] of block.items) {
        const chip = make(doc, "span", "vd-doc-chip");
        chip.appendChild(make(doc, "span", "vd-doc-chip-label", label));
        chip.appendChild(make(doc, "span", "vd-doc-chip-value", value));
        wrapper.appendChild(chip);
      }

      return wrapper;
    }

    case "banner": {
      const wrapper = make(doc, "div", "vd-banner-row");
      const banner = make(doc, "div", "vd-banner");
      banner.appendChild(make(doc, "span", "vd-banner-label", block.label));
      banner.appendChild(make(doc, "span", "vd-banner-value", block.value));
      wrapper.appendChild(banner);
      return wrapper;
    }

    case "signatures": {
      const wrapper = make(doc, "div", "vd-signatures");

      for (const label of block.labels) {
        wrapper.appendChild(make(doc, "div", "vd-signature", label));
      }

      return wrapper;
    }

    default:
      return make(doc, "div", "vd-signoff", block.text);
  }
}

/**
 * Push a vendor's brand values onto an element as custom properties.
 *
 * This is the CSP-safe half of the theming: the stylesheet only ever reads
 * `var(--vd-*)`, and the concrete values arrive here through CSSOM.
 * @param {HTMLElement} element - Element to theme.
 * @param {Vendor} vendor - Vendor supplying the values.
 * @returns {void}
 */
export function applyVendorTheme(element, vendor) {
  element.style.setProperty("--vd-accent", vendor.accent);
  element.style.setProperty("--vd-accent-soft", vendor.accentSoft);
  element.style.setProperty("--vd-ink", vendor.ink);
  element.style.setProperty("--vd-font", vendor.font);
}

/**
 * Replace the paper's contents with a rendered document.
 * @param {HTMLElement} paper - The `.vd-paper` element.
 * @param {DocumentModel} model - Document to render.
 * @param {Document} [doc=document] - Owning document, injectable for tests.
 * @returns {HTMLElement} The paper element, for chaining.
 */
export function renderPaper(paper, model, doc = document) {
  const { vendor } = model;
  applyVendorTheme(paper, vendor);
  paper.replaceChildren();

  const page = make(doc, "div", `vd-page is-${vendor.layout}${model.dense ? " is-dense" : ""}`);
  page.appendChild(make(doc, "div", "vd-accent-bar"));

  const header = make(doc, "header", "vd-doc-head");
  const brand = make(doc, "div", "vd-brand");
  brand.appendChild(buildLogo(doc, vendor));
  const vendorLines = make(doc, "div", "vd-vendor-lines");
  appendLines(
    doc,
    vendorLines,
    [vendor.addr, `${vendor.phone} · ${vendor.email}`, vendor.taxId],
    "vd-vendor-line"
  );
  brand.appendChild(vendorLines);
  header.appendChild(brand);

  const titleWrap = make(doc, "div", "vd-doc-title-wrap");
  titleWrap.appendChild(make(doc, "div", "vd-doc-title", model.title));

  if (model.subtitle) {
    titleWrap.appendChild(make(doc, "div", "vd-doc-subtitle", model.subtitle));
  }

  header.appendChild(titleWrap);
  page.appendChild(header);

  const body = make(doc, "div", "vd-doc-body");

  for (const block of model.blocks) {
    body.appendChild(renderBlock(doc, block));
  }

  page.appendChild(body);
  page.appendChild(make(doc, "footer", "vd-doc-foot", model.footer));
  paper.appendChild(page);

  return paper;
}
