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
 * Mark an element as carrying a ground-truth value.
 *
 * This is the entire coupling between the renderer and the annotation layer:
 * `annotate-boxes.js` reads `[data-field]` back off the page and never needs to
 * know what a totals block or a keygrid is. Empty values are skipped so a blank
 * cell in a ledger does not produce a box for a field the sidecar reports as
 * null.
 * @param {HTMLElement} element - Element holding the value.
 * @param {string | null | undefined} field - Ground-truth field key.
 * @param {string} [value] - The printed value, used to skip blanks.
 * @returns {HTMLElement} The same element, for chaining.
 */
function tag(element, field, value) {
  if (field && value !== "") {
    element.setAttribute("data-field", field);
  }

  return element;
}

/**
 * Append one element per line of text.
 * @param {Document} doc - Owning document.
 * @param {HTMLElement} parent - Element to append into.
 * @param {string[]} lines - Lines to render.
 * @param {string} className - Class for each line element.
 * @param {(string | null)[]} fields - Ground-truth field per line, including the name.
 * @returns {void}
 */
function appendLines(doc, parent, lines, className, fields) {
  lines.forEach((line, index) => {
    parent.appendChild(tag(make(doc, "div", className, line), fields[index + 1], line));
  });
}

/**
 * Build a two-column key/value table.
 * @param {Document} doc - Owning document.
 * @param {import("./document-model.js").LabelledValue[]} pairs - Label/value/field triples.
 * @param {string} className - Class for the table element.
 * @returns {HTMLElement} The table.
 */
function keyValueTable(doc, pairs, className) {
  const table = make(doc, "table", className);
  const body = make(doc, "tbody");

  for (const [label, value, field] of pairs) {
    const row = make(doc, "tr");
    row.appendChild(make(doc, "th", "vd-kv-key", label));
    row.appendChild(tag(make(doc, "td", "vd-kv-value", value), field, value));
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

  /**
   * @param {string} className - Class for the span.
   * @param {string} text - Text to show.
   * @returns {HTMLElement} A span tagged as part of the vendor name.
   */
  const namePart = (className, text) => tag(make(doc, "span", className, text), "vendor_name", text);

  if (vendor.logoStyle === "block" || vendor.logoStyle === "stamp") {
    logo.appendChild(make(doc, "span", "vd-logo-mark", initialsOf(vendor.name)));
    logo.appendChild(namePart("vd-logo-name", vendor.name));
    return logo;
  }

  if (vendor.logoStyle === "leaf" || vendor.logoStyle === "mono") {
    const glyph = vendor.logoStyle === "leaf" ? "☘" : "☁";
    logo.appendChild(make(doc, "span", "vd-logo-glyph", glyph));
    logo.appendChild(namePart("vd-logo-name", vendor.name));
    return logo;
  }

  if (vendor.logoStyle === "thin") {
    // The thin lockup splits the name across two spans, so it produces two
    // `vendor_name` regions rather than one. That is the truth of the layout:
    // there is no single box on the page holding the whole name.
    logo.appendChild(namePart("vd-logo-name", firstWord));
    logo.appendChild(namePart("vd-logo-sub", restWords.join(" ")));
    return logo;
  }

  logo.appendChild(namePart("vd-logo-name", vendor.name));
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
      const fields = block.lineFields ?? [];
      party.appendChild(tag(make(doc, "div", "vd-party-name", name), fields[0], name));
      appendLines(doc, party, rest, "vd-party-line", fields);
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

      block.columns.forEach((lines, columnIndex) => {
        const cell = make(doc, "td", "vd-partypair-cell");
        const fields = block.columnFields?.[columnIndex] ?? [];
        const [name, ...rest] = lines;
        cell.appendChild(tag(make(doc, "div", "vd-party-name", name), fields[0], name));
        appendLines(doc, cell, rest, "vd-party-line", fields);
        bodyRow.appendChild(cell);
      });

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

      block.rows.forEach((row, rowIndex) => {
        const tableRow = make(doc, "tr");
        row.forEach((cell, index) => {
          const align = block.columns[index]?.align ?? "left";
          const column = block.fields?.[index];
          // Row-scoped fields are addressed the way a consumer indexes them:
          // `line_items.2.amount` points at exactly one cell on exactly one page.
          const field = block.rowScope && column ? `${block.rowScope}.${rowIndex}.${column}` : null;
          tableRow.appendChild(tag(make(doc, "td", `is-${align}`, cell), field, cell));
        });
        body.appendChild(tableRow);
      });

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

      block.rows.forEach(([label, value, field], index) => {
        const row = make(doc, "tr", index === block.emphasisIndex ? "is-emphasis" : undefined);
        row.appendChild(make(doc, "th", "vd-totals-label", label));
        row.appendChild(tag(make(doc, "td", "vd-totals-value", value), field, value));
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

      for (const [label, value, field] of block.items) {
        const chip = make(doc, "span", "vd-doc-chip");
        chip.appendChild(make(doc, "span", "vd-doc-chip-label", label));
        chip.appendChild(tag(make(doc, "span", "vd-doc-chip-value", value), field, value));
        wrapper.appendChild(chip);
      }

      return wrapper;
    }

    case "banner": {
      const wrapper = make(doc, "div", "vd-banner-row");
      const banner = make(doc, "div", "vd-banner");
      banner.appendChild(make(doc, "span", "vd-banner-label", block.label));
      banner.appendChild(
        tag(make(doc, "span", "vd-banner-value", block.value), block.field, block.value)
      );
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
  vendorLines.appendChild(
    tag(make(doc, "div", "vd-vendor-line", vendor.addr), "vendor_address", vendor.addr)
  );

  // The phone and the email share one printed line but are two separate facts,
  // so each gets its own span and its own box rather than one region holding
  // both values and the separator between them.
  const contactLine = make(doc, "div", "vd-vendor-line");
  contactLine.appendChild(tag(make(doc, "span", "", vendor.phone), "vendor_phone", vendor.phone));
  contactLine.appendChild(make(doc, "span", "", " · "));
  contactLine.appendChild(tag(make(doc, "span", "", vendor.email), "vendor_email", vendor.email));
  vendorLines.appendChild(contactLine);

  vendorLines.appendChild(
    tag(make(doc, "div", "vd-vendor-line", vendor.taxId), "vendor_tax_id", vendor.taxId)
  );
  brand.appendChild(vendorLines);
  header.appendChild(brand);

  const titleWrap = make(doc, "div", "vd-doc-title-wrap");
  titleWrap.appendChild(
    tag(make(doc, "div", "vd-doc-title", model.title), "document_title", model.title)
  );

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
