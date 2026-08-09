/**
 * Renders a document model into a native jsPDF document with a real text
 * layer, so exported samples are searchable and selectable rather than a
 * picture of a page.
 *
 * It walks the exact same block list the on-screen paper renderer walks, so the
 * two agree on the content of a given seed. The layout is this module's own:
 * jsPDF positions in A4 points while the preview lays out in CSS pixels, so
 * nothing here can be derived from the DOM geometry. Anything drawn at a fixed
 * offset has to be measured against what sits next to it first, which is the
 * lesson of the letterhead and meta-gutter overprints this renderer shipped.
 *
 * @module pdf-render
 */

import { initialsOf } from "./format.js";

/**
 * @typedef {import("./document-model.js").DocumentModel} DocumentModel
 * @typedef {import("./document-model.js").DocumentBlock} DocumentBlock
 * @typedef {ArtifactsJsPdfConstructor} JsPdfConstructor
 * @typedef {ArtifactsJsPdfDocument} JsPdfDocument
 */

const MARGIN = 42;
const HEADER_BAR_HEIGHT = 6;
const BODY_START_Y = 150;
/** Distance from the bottom edge kept clear for the footer line. */
const FOOTER_INSET = 30;
/** Distance from the bottom edge past which a block moves to a new page. */
const CONTENT_INSET = 72;
const GREY = /** @type {[number, number, number]} */ ([120, 120, 120]);
const MUTED = /** @type {[number, number, number]} */ ([90, 90, 90]);
const INK = /** @type {[number, number, number]} */ ([35, 35, 35]);
const LINE = /** @type {[number, number, number]} */ ([215, 215, 215]);

/** Width of the label-and-value gutter on the right of a `parties` block. */
const META_GUTTER = 170;
/** Clear space kept between the letterhead and the document title. */
const HEADER_GAP = 14;
/** Smallest the document title may shrink to before the name wraps instead. */
const MIN_TITLE_SIZE = 13;
/** Side of the square monogram tile drawn for vendors whose logo uses one. */
const MONOGRAM_SIZE = 34;
/** Logo styles the preview renders as an initials tile. */
const MONOGRAM_STYLES = new Set(["block", "stamp"]);

/**
 * Map a CSS font stack onto one of the three fonts jsPDF ships by default.
 *
 * Each vendor carries a `font`, and the PDF renderer used to ignore it and set
 * Helvetica for everybody. That flattened six deliberately unrelated brands into
 * one letterhead in the export, which for a document-AI corpus throws away the
 * most valuable axis of variation there is. The core fonts are the only ones
 * available without embedding a binary, so serif and monospace stacks map onto
 * times and courier and everything else stays helvetica.
 * @param {string} stack - CSS font-family stack from the vendor record.
 * @returns {string} A jsPDF core font family name.
 */
export function pdfFontFor(stack) {
  const lowered = stack.toLowerCase();

  if (lowered.includes("mono") || lowered.includes("courier")) {
    return "courier";
  }

  if (
    (lowered.includes("serif") && !lowered.includes("sans-serif")) ||
    lowered.includes("georgia") ||
    lowered.includes("times")
  ) {
    return "times";
  }

  return "helvetica";
}

/**
 * Shrink a font size until the text fits the width available.
 * @param {JsPdfDocument} doc - Document used for measurement.
 * @param {string} text - Text to fit.
 * @param {string} family - Font family to measure in.
 * @param {string} weight - Font weight to measure in.
 * @param {number} startSize - Preferred size.
 * @param {number} available - Width the text has to fit inside.
 * @param {number} minSize - Smallest acceptable size.
 * @returns {number} The largest size at or below `startSize` that fits.
 */
function fitFontSize(doc, text, family, weight, startSize, available, minSize) {
  let size = startSize;

  doc.setFont(family, weight);

  while (size > minSize) {
    doc.setFontSize(size);

    if (doc.getTextWidth(text) <= available) {
      return size;
    }

    size -= 0.5;
  }

  return minSize;
}

/**
 * Convert a `#rrggbb` string into a jsPDF colour triple.
 * @param {string} hex - Hex colour, with or without the leading hash.
 * @returns {[number, number, number]} Red, green, and blue channels.
 */
export function hexToRgb(hex) {
  const value = hex.replace("#", "");
  return [
    Number.parseInt(value.slice(0, 2), 16),
    Number.parseInt(value.slice(2, 4), 16),
    Number.parseInt(value.slice(4, 6), 16)
  ];
}

/**
 * Small stateful cursor over one jsPDF document.
 *
 * jsPDF is entirely imperative and autotable reports where it stopped through
 * `lastAutoTable.finalY`; wrapping both in one object keeps the vertical
 * position in a single place instead of threading a `y` variable through every
 * block branch.
 */
class PdfCursor {
  /**
   * @param {JsPdfDocument} doc - Document being written.
   * @param {[number, number, number]} accent - Vendor accent colour.
   * @param {[number, number, number]} accentSoft - Vendor soft accent colour.
   * @param {string} family - jsPDF core font family for this vendor.
   */
  constructor(doc, accent, accentSoft, family) {
    this.doc = doc;
    this.accent = accent;
    this.accentSoft = accentSoft;
    this.family = family;
    this.width = doc.internal.pageSize.getWidth();
    const height = doc.internal.pageSize.getHeight();
    this.footerY = height - FOOTER_INSET;
    this.pageBottom = height - CONTENT_INSET;
    this.y = BODY_START_Y;
  }

  /**
   * Start a new page when the next block would not fit on this one.
   * @param {number} needed - Vertical space the next block wants.
   * @returns {void}
   */
  ensureSpace(needed) {
    if (this.y + needed > this.pageBottom) {
      this.doc.addPage();
      this.y = MARGIN + 20;
    }
  }

  /**
   * Run an autotable and advance the cursor to where it finished.
   * @param {ArtifactsAutoTableOptions} options - Autotable options.
   * @returns {void}
   */
  table(options) {
    this.doc.autoTable({ startY: this.y, margin: { left: MARGIN, right: MARGIN }, ...options });
    this.y = this.doc.lastAutoTable.finalY;
  }

  /**
   * Write wrapped body text and advance past it.
   * @param {string} text - Text to write.
   * @param {number} [size=8.5] - Font size.
   * @returns {void}
   */
  paragraph(text, size = 8.5) {
    this.doc.setFont(this.family, "normal");
    this.doc.setFontSize(size);
    this.doc.setTextColor(...GREY);

    for (const line of this.doc.splitTextToSize(text, this.width - 2 * MARGIN)) {
      this.y += size + 3.5;
      this.ensureSpace(0);
      this.doc.text(line, MARGIN, this.y);
    }
  }
}

/**
 * Draw the vendor letterhead and the document title.
 * @param {PdfCursor} cursor - Active cursor.
 * @param {DocumentModel} model - Document being rendered.
 * @returns {void}
 */
function drawHeader(cursor, model) {
  const { doc, width, accent, family } = cursor;
  const { vendor } = model;
  const ink = hexToRgb(vendor.ink);
  const title = model.title.toUpperCase();
  const hasMark = MONOGRAM_STYLES.has(vendor.logoStyle);
  const nameX = MARGIN + (hasMark ? MONOGRAM_SIZE + 12 : 0);

  doc.setFillColor(...accent);
  doc.rect(0, 0, width, HEADER_BAR_HEIGHT, "F");

  if (hasMark) {
    // The preview draws a monogram tile for these vendors and the PDF drew
    // nothing at all, which is part of why the exported page never looked like
    // the page on screen.
    doc.setFillColor(...accent);
    doc.rect(MARGIN, 30, MONOGRAM_SIZE, MONOGRAM_SIZE, "F");
    doc.setFont(family, "bold");
    doc.setFontSize(15);
    doc.setTextColor(255, 255, 255);
    doc.text(initialsOf(vendor.name), MARGIN + MONOGRAM_SIZE / 2, 30 + MONOGRAM_SIZE / 2 + 5, {
      align: "center"
    });
  }

  // Both halves of this row used to be drawn at a fixed size from opposite
  // margins with nothing measured between them, so "Ironwood Construction
  // Materials" and "DELIVERY CHALLAN" overprinted each other by 15pt on every
  // single seed. Measure the letterhead first, then give the title whatever is
  // left, shrinking it until it fits.
  doc.setFont(family, "bold");
  doc.setFontSize(17);
  const nameWidth = doc.getTextWidth(vendor.name);
  const titleRoom = width - MARGIN - nameX - nameWidth - HEADER_GAP;
  const titleSize = fitFontSize(
    doc,
    title,
    family,
    "bold",
    model.dense ? 18 : 26,
    titleRoom,
    MIN_TITLE_SIZE
  );

  doc.setFont(family, "bold");
  doc.setFontSize(17);
  doc.setTextColor(...ink);
  doc.text(vendor.name, nameX, 46);

  doc.setFont(family, "normal");
  doc.setFontSize(8.5);
  doc.setTextColor(...GREY);
  doc.text(vendor.tagline, MARGIN, 60 + (hasMark ? 14 : 0));
  doc.text(doc.splitTextToSize(vendor.addr, 260), MARGIN, 74 + (hasMark ? 14 : 0));
  doc.text(`${vendor.phone}  |  ${vendor.email}`, MARGIN, 96 + (hasMark ? 14 : 0));
  doc.text(vendor.taxId, MARGIN, 108 + (hasMark ? 14 : 0));

  doc.setFont(family, "bold");
  doc.setFontSize(titleSize);
  doc.setTextColor(...accent);
  doc.text(title, width - MARGIN, 50, { align: "right" });

  if (model.subtitle) {
    doc.setFont(family, "normal");
    doc.setFontSize(8);
    doc.setTextColor(...GREY);
    doc.text(model.subtitle, width - MARGIN, 62, { align: "right" });
  }
}

/**
 * Draw the sample-data footer on the current page.
 * @param {PdfCursor} cursor - Active cursor.
 * @param {DocumentModel} model - Document being rendered.
 * @returns {void}
 */
function drawFooter(cursor, model) {
  cursor.doc.setFont(cursor.family, "normal");
  cursor.doc.setFontSize(7.5);
  cursor.doc.setTextColor(165, 165, 165);

  // Wrapped, not centred blindly. Ironwood's name and tagline push this string
  // 6pt past the text column, and an unwrapped centred line bleeds into both
  // margins rather than breaking. The DOM renderer wraps it, which is why the
  // overflow only ever showed up in the PDF.
  const lines = cursor.doc.splitTextToSize(model.footer, cursor.width - 2 * MARGIN);

  lines.forEach((line, index) => {
    const offset = (lines.length - 1 - index) * 9;
    cursor.doc.text(line, cursor.width / 2, cursor.footerY - offset, { align: "center" });
  });
}

/**
 * Render the left party block and the right meta rows of a `parties` block.
 * @param {PdfCursor} cursor - Active cursor.
 * @param {import("./document-model.js").PartiesBlock} block - Block to draw.
 * @returns {void}
 */
function drawParties(cursor, block) {
  const { doc, width, family } = cursor;
  const top = cursor.y;

  doc.setFont(family, "normal");
  doc.setFontSize(8);
  doc.setTextColor(150, 150, 150);
  doc.text(block.label.toUpperCase(), MARGIN, top);

  let left = top + 13;
  doc.setFontSize(10);
  doc.setTextColor(...INK);

  block.lines.forEach((line, index) => {
    doc.setFont(family, index === 0 ? "bold" : "normal");

    for (const wrapped of doc.splitTextToSize(line, 240)) {
      doc.text(wrapped, MARGIN, left);
      left += 12;
    }
  });

  let right = top;
  doc.setFontSize(9);

  for (const [label, value] of block.meta) {
    const caption = `${label}:`;

    doc.setFont(family, "normal");
    doc.setTextColor(...GREY);
    doc.text(caption, width - MARGIN - META_GUTTER, right);

    // The value is right-aligned against the margin, so it grows leftward into
    // the label. The gutter was a fixed 170pt with nothing measured, which put
    // "Goods returned, damaged in transit" straight through "Reason:" on a
    // quarter of all credit notes. When the pair will not fit on one line, the
    // value drops to its own line instead of overprinting.
    const captionWidth = doc.getTextWidth(caption);
    doc.setFont(family, "bold");
    doc.setTextColor(...INK);

    if (doc.getTextWidth(value) <= META_GUTTER - captionWidth - 6) {
      doc.text(value, width - MARGIN, right, { align: "right" });
      right += 14;
      continue;
    }

    right += 11;

    for (const wrapped of doc.splitTextToSize(value, META_GUTTER)) {
      doc.text(wrapped, width - MARGIN, right, { align: "right" });
      right += 11;
    }

    right += 3;
  }

  cursor.y = Math.max(left, right) + 6;
}

/**
 * Render one block into the PDF.
 * @param {PdfCursor} cursor - Active cursor.
 * @param {DocumentBlock} block - Block to render.
 * @returns {void}
 */
function drawBlock(cursor, block) {
  const { doc, width, accent, accentSoft, family } = cursor;

  switch (block.kind) {
    case "stamp":
      doc.setFont(family, "bold");
      doc.setFontSize(14);
      doc.setTextColor(...accent);
      doc.text(block.text, width / 2, cursor.y + 6, { align: "center" });
      cursor.y += 26;
      return;

    case "parties":
      drawParties(cursor, block);
      return;

    case "keygrid": {
      const half = (width - 2 * MARGIN - 8) / 2;
      const startY = cursor.y;
      let lowest = cursor.y;

      block.columns.forEach((column, index) => {
        doc.autoTable({
          startY,
          margin: { left: MARGIN + index * (half + 8) },
          tableWidth: half,
          body: column.map(([label, value]) => [label, value]),
          styles: { fontSize: 7.5, cellPadding: 3, lineColor: LINE, lineWidth: 0.4 },
          columnStyles: {
            0: { fillColor: [244, 244, 244], fontStyle: "bold", cellWidth: half * 0.42 }
          }
        });
        lowest = Math.max(lowest, doc.lastAutoTable.finalY);
      });

      cursor.y = lowest + 8;
      return;
    }

    case "partypair":
      cursor.table({
        head: [[...block.headings]],
        body: [block.columns.map((lines) => lines.join("\n"))],
        headStyles: { fillColor: accent, textColor: 255, fontSize: 8.5 },
        bodyStyles: { fontSize: 8, cellPadding: 5 },
        styles: { font: family, lineColor: LINE, lineWidth: 0.4 }
      });
      cursor.y += 8;
      return;

    case "table": {
      /** @type {Record<number, NonNullable<ArtifactsAutoTableOptions["styles"]>>} */
      const columnStyles = {};

      block.columns.forEach((column, index) => {
        columnStyles[index] = column.width
          ? { halign: column.align, cellWidth: column.width }
          : { halign: column.align };
      });

      const body = block.footer ? [...block.rows, block.footer] : block.rows;
      const footerIndex = block.rows.length;

      cursor.ensureSpace(60);
      cursor.table({
        head: [block.columns.map((column) => column.label)],
        body,
        columnStyles,
        headStyles: {
          fillColor: accent,
          textColor: 255,
          fontSize: block.dense ? 7 : 8.5,
          fontStyle: "bold"
        },
        bodyStyles: { fontSize: block.dense ? 7 : 8.5, textColor: [40, 40, 40] },
        alternateRowStyles: { fillColor: [247, 247, 250] },
        styles: {
          font: family,
          cellPadding: block.dense ? 3 : 4,
          lineColor: LINE,
          lineWidth: 0.4
        },
        didParseCell: (data) => {
          if (block.footer && data.section === "body" && data.row.index === footerIndex) {
            data.cell.styles.fillColor = accentSoft;
            data.cell.styles.fontStyle = "bold";
          }
        }
      });
      return;
    }

    case "totals":
      cursor.ensureSpace(70);
      cursor.doc.autoTable({
        startY: cursor.y + 6,
        margin: { left: width - MARGIN - 230 },
        tableWidth: 230,
        body: block.rows.map(([label, value]) => [label, value]),
        styles: { fontSize: 9, cellPadding: 4, lineColor: LINE, lineWidth: 0.4 },
        columnStyles: { 0: { halign: "right", textColor: MUTED }, 1: { halign: "right" } },
        didParseCell: (data) => {
          if (data.row.index === block.emphasisIndex) {
            data.cell.styles.fillColor = accent;
            data.cell.styles.textColor = 255;
            data.cell.styles.fontStyle = "bold";
          }
        }
      });
      cursor.y = cursor.doc.lastAutoTable.finalY;
      return;

    case "words":
    case "note":
      cursor.paragraph(block.text);
      cursor.y += 6;
      return;

    case "callout":
      cursor.ensureSpace(40);
      cursor.table({
        startY: cursor.y + 8,
        body: [[block.text]],
        // `theme: "plain"` is load-bearing. Under the default striped theme,
        // `alternateRowStyles.fillColor` resolves to 245 on row index 0 and
        // outranks both `styles` and `bodyStyles`, so these single-row tables
        // painted flat grey no matter which of those the fill was declared in.
        // Measured, not assumed: didParseCell reports 245 for styles and for
        // bodyStyles, and the accent only for the plain and grid themes.
        theme: "plain",
        styles: { font: family, fontSize: 8.5, cellPadding: 8, lineColor: LINE, lineWidth: 0.4 },
        bodyStyles: { fillColor: accentSoft, textColor: INK }
      });
      return;

    case "chips":
      cursor.paragraph(
        block.items.map(([label, value]) => `${label}: ${value}`).join("     "),
        9
      );
      cursor.y += 6;
      return;

    case "banner":
      cursor.ensureSpace(40);
      cursor.doc.autoTable({
        startY: cursor.y + 8,
        margin: { left: width - MARGIN - 230 },
        tableWidth: 230,
        body: [[block.label, block.value]],
        // See the callout above: without the plain theme this prints white text
        // on rgb(245, 245, 245), which made the balance due, the one number a
        // statement of account exists to communicate, invisible in every PDF.
        theme: "plain",
        styles: { font: family, fontSize: 11, cellPadding: 7, fontStyle: "bold" },
        bodyStyles: { fillColor: accent, textColor: 255 },
        columnStyles: { 1: { halign: "right" } }
      });
      cursor.y = cursor.doc.lastAutoTable.finalY;
      return;

    case "signatures": {
      cursor.ensureSpace(60);
      cursor.y += 42;
      doc.setDrawColor(150, 150, 150);
      doc.setLineWidth(0.5);
      doc.setFont(family, "normal");
      doc.setFontSize(9);
      doc.setTextColor(...MUTED);

      block.labels.forEach((label, index) => {
        const left = index === 0 ? MARGIN : width - MARGIN - 170;
        doc.rect(left, cursor.y, 170, 0.5, "F");
        doc.text(label, left, cursor.y + 12);
      });

      cursor.y += 20;
      return;
    }

    default:
      cursor.y += 14;
      doc.setFont(family, "bold");
      doc.setFontSize(10);
      doc.setTextColor(...INK);
      doc.text(block.text, width - MARGIN, cursor.y, { align: "right" });
  }
}

/**
 * Render a document model into a fresh jsPDF document.
 * @param {DocumentModel} model - Document to render.
 * @param {JsPdfConstructor} JsPdf - jsPDF constructor from the vendored UMD build.
 * @returns {JsPdfDocument} The finished document, ready to save or serialise.
 */
export function renderPdf(model, JsPdf) {
  const doc = new JsPdf("p", "pt", "a4");
  const cursor = new PdfCursor(
    doc,
    hexToRgb(model.vendor.accent),
    hexToRgb(model.vendor.accentSoft),
    pdfFontFor(model.vendor.font)
  );

  drawHeader(cursor, model);

  for (const block of model.blocks) {
    drawBlock(cursor, block);
  }

  drawFooter(cursor, model);
  return doc;
}
