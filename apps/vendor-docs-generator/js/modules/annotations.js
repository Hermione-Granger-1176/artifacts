/**
 * Turns a document model's facts into the ground-truth sidecar.
 *
 * The sidecar is the label set for a rendered page. It is built from the same
 * values the page was printed from, so the two cannot disagree.
 *
 * Each field has two representations. `text` is what an OCR pass should read
 * off the page, character for character. `value` is what an extractor should
 * normalise to: an ISO date, a number, a plain string. Both are always present.
 *
 * Three rules hold for every document, and `annotations.test.js` enforces them:
 *
 * 1. Every key in `FIELD_KEYS` is present on every document. An absent fact is
 *    an explicit `null`, never a missing key and never an empty string.
 * 2. A field is non-null only when the page actually prints it.
 * 3. The money adds up: the line amounts sum to the subtotal, and subtotal plus
 *    tax plus shipping equals the grand total.
 *
 * @module annotations
 */

import { BOXES_APPLY_TO } from "./annotate-boxes.js";
import { DEGRADATION_APPLIES_TO } from "./degrade.js";
import {
  formatDate,
  formatMoney,
  formatRate,
  isoDate,
  printedTitle,
  printedVendorName,
  roundCents
} from "./format.js";

/**
 * @typedef {import("./document-model.js").DocumentModel} DocumentModel
 * @typedef {import("./document-model.js").DocumentFacts} DocumentFacts
 * @typedef {import("./annotate-boxes.js").BoxAnnotations} BoxAnnotations
 * @typedef {import("./degrade.js").DegradePlan} DegradePlan
 * @typedef {{ text: string, value: string | number } | null} AnnotatedField
 */

/**
 * Wire format version.
 *
 * Key names are frozen: a key never changes meaning. The version changes if a
 * key has to.
 */
export const SCHEMA_VERSION = "1.1";

/**
 * Every document-level key the sidecar emits, in output order.
 *
 * The list is the contract. The payload is built by walking it, so a document
 * type that does not set a key still emits it, as `null`.
 */
export const FIELD_KEYS = [
  "document_title",
  "document_number",
  "document_date",
  "due_date",
  "valid_until",
  "period_start",
  "period_end",
  "order_number",
  "order_date",
  "po_number",
  "reference",
  "against_invoice",
  "payment_method",
  "payment_terms",
  "adjustment_reason",
  "vehicle_number",
  "vendor_name",
  "vendor_address",
  "vendor_email",
  "vendor_phone",
  "vendor_tax_id",
  "vendor_company_reg",
  "buyer_name",
  "buyer_address",
  "buyer_contact",
  "buyer_phone",
  "subtotal",
  "tax_rate",
  "tax_amount",
  "shipping",
  "grand_total",
  "amount_paid",
  "balance_due",
  "total_quantity",
  "package_count"
];

/** Every per-line key, emitted for each entry of `line_items`. */
export const LINE_ITEM_KEYS = [
  "description",
  "sku",
  "product_code",
  "quantity",
  "unit",
  "unit_price",
  "amount",
  "tax_rate",
  "tax_amount",
  "line_total",
  "remarks"
];

/** Every per-row key, emitted for each entry of `transactions`. */
export const TRANSACTION_KEYS = [
  "date",
  "reference",
  "description",
  "charge",
  "payment",
  "balance"
];

const LOCALE = "en-US";
const CURRENCY = "USD";
const PAGE_SIZE = "A4";

/**
 * A plain string field.
 * @param {string | undefined | null} value - Printed string, if the page prints one.
 * @returns {AnnotatedField} Field pair, or null when nothing is printed.
 */
function textField(value) {
  if (value === undefined || value === null || value === "") {
    return null;
  }

  return { text: value, value };
}

/**
 * A string field whose printed form differs from its value, such as a title
 * the page sets in capitals.
 * @param {string} text - The characters on the page.
 * @param {string} value - The normalised value.
 * @returns {AnnotatedField} Field pair.
 */
function printedField(text, value) {
  return { text, value };
}

/**
 * Share the null handling and pair shape of numeric annotations.
 * @param {number | undefined | null} value - Number the page may print.
 * @param {(value: number) => string} format - Printed representation.
 * @param {(value: number) => number} [normalise] - Machine-readable representation.
 * @returns {AnnotatedField} Field pair, or null when nothing is printed.
 */
function numericField(value, format, normalise = (number) => number) {
  if (value === undefined || value === null) {
    return null;
  }

  return { text: format(value), value: normalise(value) };
}

/**
 * A money field: grouped and symbol-prefixed on the page, a plain number off it.
 * @param {number | undefined | null} amount - Amount in the document's currency.
 * @returns {AnnotatedField} Field pair, or null when nothing is printed.
 */
function moneyField(amount) {
  return numericField(amount, formatMoney, roundCents);
}

/**
 * A date field: the document's printed format alongside ISO 8601.
 * @param {Date | undefined | null} date - Date the page prints.
 * @returns {AnnotatedField} Field pair, or null when nothing is printed.
 */
function dateField(date) {
  if (!date) {
    return null;
  }

  return { text: formatDate(date), value: isoDate(date) };
}

/**
 * A percentage field: printed as a percentage, normalised as a fraction.
 * @param {number | undefined | null} rate - Rate as a fraction, for example 0.0825.
 * @returns {AnnotatedField} Field pair, or null when nothing is printed.
 */
function rateField(rate) {
  return numericField(rate, formatRate);
}

/**
 * A plain count field.
 * @param {number | undefined | null} count - Whole number the page prints.
 * @returns {AnnotatedField} Field pair, or null when nothing is printed.
 */
function countField(count) {
  return numericField(count, String);
}

/**
 * The buyer's address block.
 *
 * `text` keeps the line break the page prints. `value` is the single-line form
 * an extractor should produce.
 * @param {string[]} lines - Address lines.
 * @returns {AnnotatedField} Field pair, or null when there is no address.
 */
function addressField(lines) {
  if (!lines?.length) {
    return null;
  }

  return { text: lines.join("\n"), value: lines.join(", ") };
}

/**
 * Assemble the document-level field map.
 * @param {DocumentModel} model - Document to describe.
 * @returns {Record<string, AnnotatedField>} Every key in `FIELD_KEYS`.
 */
function documentFields(model) {
  const { facts, vendor } = model;
  const totals = facts.totals;

  // Both renderers print the letterhead on every page, so the five vendor facts
  // below are always set. Only the dense invoice prints the company registration.
  return {
    document_title: printedField(printedTitle(model.title), model.title),
    document_number: textField(facts.documentNumber),
    document_date: dateField(facts.documentDate),
    due_date: dateField(facts.dueDate),
    valid_until: dateField(facts.validUntil),
    period_start: dateField(facts.periodStart),
    period_end: dateField(facts.periodEnd),
    order_number: textField(facts.orderNumber),
    order_date: dateField(facts.orderDate),
    po_number: textField(facts.poNumber),
    reference: textField(facts.reference),
    against_invoice: textField(facts.againstInvoice),
    payment_method: textField(facts.paymentMethod),
    payment_terms: textField(facts.paymentTerms),
    adjustment_reason: textField(facts.reason),
    vehicle_number: textField(facts.vehicleNumber),
    vendor_name: printedField(printedVendorName(vendor), vendor.name),
    vendor_address: textField(vendor.addr),
    vendor_email: textField(vendor.email),
    vendor_phone: textField(vendor.phone),
    vendor_tax_id: textField(vendor.taxId),
    vendor_company_reg: textField(facts.vendorCompanyReg),
    buyer_name: textField(facts.buyer.name),
    buyer_address: addressField(facts.buyer.lines),
    buyer_contact: textField(facts.buyerContact),
    buyer_phone: textField(facts.buyerPhone),
    subtotal: moneyField(totals?.subtotal),
    tax_rate: rateField(totals?.taxRate),
    tax_amount: moneyField(totals?.tax),
    shipping: moneyField(facts.shipping),
    grand_total: moneyField(totals?.grand),
    amount_paid: moneyField(facts.amountPaid),
    balance_due: moneyField(facts.balanceDue),
    total_quantity: countField(facts.totalQuantity),
    package_count: countField(facts.packageCount)
  };
}

/**
 * Assemble the per-line annotations.
 *
 * Unpriced documents, such as a delivery challan, emit `null` for `unit_price`
 * and `amount`, because the page does not print them.
 * @param {DocumentFacts} facts - Facts recorded by the builder.
 * @returns {Record<string, AnnotatedField | number>[]} One entry per line item.
 */
function lineItems(facts) {
  const priced = facts.itemsPriced !== false;
  const taxRate = facts.totals?.taxRate;

  return (facts.items ?? []).map((item, index) => {
    const lineTax = facts.lineTaxes?.[index];

    return {
      index,
      description: textField(item.desc),
      sku: textField(facts.lineSkus?.[index]),
      product_code: textField(facts.lineProductCodes?.[index]),
      quantity: countField(item.qty),
      unit: textField(item.unit),
      unit_price: priced ? moneyField(item.price) : null,
      amount: priced ? moneyField(item.amount) : null,
      tax_rate: lineTax === undefined ? null : rateField(taxRate),
      tax_amount: moneyField(lineTax),
      line_total: lineTax === undefined ? null : moneyField(roundCents(item.amount + lineTax)),
      remarks: textField(facts.lineRemarks?.[index])
    };
  });
}

/**
 * Assemble the statement ledger annotations.
 *
 * Statement rows go in their own `transactions` array, with keys that differ
 * from `line_items`.
 * @param {DocumentFacts} facts - Facts recorded by the builder.
 * @returns {Record<string, AnnotatedField | number>[]} One entry per ledger row.
 */
function transactions(facts) {
  return (facts.transactions ?? []).map((entry, index) => ({
    index,
    date: dateField(entry.date),
    reference: textField(entry.reference),
    description: textField(entry.description),
    charge: moneyField(entry.charge),
    payment: moneyField(entry.payment),
    balance: moneyField(entry.balance)
  }));
}

/**
 * Build the ground-truth sidecar for one document.
 * @param {DocumentModel} model - Rendered document.
 * @param {BoxAnnotations | null} [boxes=null] - Region boxes, when they were collected.
 * @param {DegradePlan | null} [degradation=null] - Degradation the page was rendered under.
 * @returns {Record<string, any>} The sidecar, ready to serialise.
 */
export function buildAnnotations(model, boxes = null, degradation = null) {
  return {
    schema_version: SCHEMA_VERSION,
    generator: "vendor-docs-generator",
    seed: model.seed,
    vendor_id: model.vendor.id,
    doc_type: model.docVariantId,
    doc_type_label: model.title,
    style: model.style,
    locale: LOCALE,
    currency: CURRENCY,
    page_size: PAGE_SIZE,
    filename_base: model.filenameBase,
    fields: documentFields(model),
    line_items: lineItems(model.facts),
    transactions: transactions(model.facts),
    boxes,
    // Boxes are measured on the HTML page, so a text-layer PDF is not among the
    // renderings they describe.
    boxes_apply_to: boxes ? BOXES_APPLY_TO : null,
    // The transform is kept after the boxes are moved through it, so a consumer
    // can filter by geometry or map back to the clean render.
    degradation: degradation
      ? {
          preset: degradation.preset,
          seed: degradation.seed,
          settings: degradation.applied,
          transform: degradation.transform,
          applies_to: DEGRADATION_APPLIES_TO
        }
      : null
  };
}

/**
 * Serialise a sidecar as pretty-printed JSON.
 * @param {Record<string, any>} annotations - Payload from `buildAnnotations`.
 * @returns {string} Indented JSON text.
 */
export function annotationsToJson(annotations) {
  return `${JSON.stringify(annotations, null, 2)}\n`;
}

/**
 * Serialise a run of sidecars as JSON Lines.
 *
 * The batch writes this alongside the per-document files, so a dataset can be
 * read from one file.
 * @param {Record<string, any>[]} entries - Sidecars in generation order.
 * @returns {string} One compact JSON object per line.
 */
export function annotationsToJsonl(entries) {
  return entries.map((entry) => JSON.stringify(entry)).join("\n") + (entries.length ? "\n" : "");
}

/**
 * Describe a downloaded dataset in its own root file.
 *
 * The README records the settings a dataset was generated under, so the output
 * can be reproduced without the app.
 * @param {{
 *   boxes: boolean,
 *   count: number,
 *   degradation: string,
 *   format: string,
 *   generatedAt: string,
 *   pair: boolean,
 *   pdfMode: string,
 *   planned?: number,
 *   words: boolean
 * }} settings - What the run was asked for, and what it actually wrote.
 * @returns {string} Plain-text README.
 */
export function datasetReadme(settings) {
  const lines = [
    "Vendor document generator dataset",
    "=================================",
    "",
    `Generated: ${settings.generatedAt}`,
    // A stopped run still writes an archive. The count is the number of
    // documents inside it, not the number requested.
    `Documents: ${settings.count}${
      settings.planned && settings.planned !== settings.count
        ? ` (run stopped early; ${settings.planned} were planned)`
        : ""
    }`,
    `Format:    ${settings.format}`,
    `PDF mode:  ${settings.pdfMode}`,
    `Boxes:     ${settings.boxes ? (settings.words ? "region and word level" : "region level") : "off"}`,
    `Scan:      ${settings.degradation}${settings.pair ? ", paired with the clean original" : ""}`,
    `Schema:    ${SCHEMA_VERSION}`,
    "",
    "Layout",
    "------",
    "  <vendor>/<type>/<base>.pdf    rendered page, if PDF was requested",
    "  <vendor>/<type>/<base>.png    rendered page, if PNG was requested",
    "  <vendor>/<type>/<base>.jpg    rendered page, when the scan preset is lossy",
    "  <vendor>/<type>/<base>.clean.png   the undegraded original, in pair mode",
    "  <vendor>/<type>/<base>.json   ground truth for that page",
    "  manifest.jsonl                every sidecar again, one compact object per line",
    "",
    "Ground truth",
    "------------",
    "Every sidecar carries the same keys. A key whose value is null means the page",
    "does not print that field, which is different from the generator failing to",
    "record it: there is no third state, and no key is ever missing.",
    "",
    "Each field is an object with two representations:",
    "  text   exactly what is printed on the page, for scoring an OCR pass",
    "  value  the normalised form, for scoring an extractor",
    "         dates are ISO 8601, money is a number in the document's currency",
    "",
    "Arithmetic holds on every document: the line amounts sum to subtotal, and",
    "subtotal plus tax plus shipping equals grand_total.",
    "",
    "Boxes",
    "-----",
    "When present, boxes.regions holds one entry per labelled element, with the box",
    "as [x, y, width, height] in normalised page coordinates from 0 to 1. Multiply",
    "by your own image dimensions. A field printed in more than one place has more",
    "than one region.",
    "",
    "Boxes are measured on the rendered HTML page, so they line up with the PNG and",
    "with the rasterised PDF. They do NOT describe the text-layer PDF, which jsPDF",
    "lays out independently. boxes_apply_to records this on every payload.",
    "",
    "Scan degradation",
    "----------------",
    "degradation is null on a clean run. Otherwise it names the preset, the seed it",
    "was driven from, every resolved setting, and the projective transform applied,",
    "as a 3x3 matrix over the same normalised coordinates the boxes use.",
    "",
    "Skew, rotation, and keystone move the ink, so the boxes have ALREADY been run",
    "through that transform: they describe the degraded image, not the clean render.",
    "Each region also carries quad, the four corners in x0,y0,x1,y1,x2,y2,x3,y3 order,",
    "because a tilted value is not really an upright rectangle. box stays the",
    "axis-aligned bounding box of that quad, so a reader that only knows about box",
    "keeps working.",
    "",
    "The same seed, preset or settings, and reference date produce the same page.",
    "The reference date can be recovered from document_date and the seed-derived",
    "day offset. Clean and degraded runs with those inputs are directly comparable,",
    "which makes accuracy-against-scan-quality measurable.",
    "",
    "Provenance",
    "----------",
    "Every vendor, buyer, address, phone number, and tax identifier is invented.",
    "These are sample documents and are not valid invoices, receipts, or tax",
    "records. Sales tax is a flat illustrative rate, not a real jurisdiction's.",
    ""
  ];

  return lines.join("\n");
}
