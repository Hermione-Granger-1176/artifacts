/**
 * Builds the seed-driven data model behind every generated document.
 *
 * The model is deliberately renderer-agnostic: `buildDocument` returns a header
 * plus an ordered list of typed blocks, and both the on-screen paper renderer
 * and the jsPDF renderer walk that same list. One model means the two renderers
 * cannot disagree about the *facts* of a document.
 *
 * They can still disagree about its *appearance*, and for a long time they did:
 * the PDF ignored the vendor font, alignment and logo entirely. Sharing a model
 * is not the same as sharing a layout engine, and the docs used to claim it
 * was.
 *
 * @module document-model
 */

import {
  addDays,
  amountInWords,
  formatDate,
  formatMoney,
  formatRate,
  padNumber,
  roundCents
} from "./format.js";
import { createSeededRandom, pickCount, pickFrom, shuffleIndices } from "./random.js";
import { TAX_RATE, catalogFor, findDocumentType, findVendor } from "./vendors.js";

/**
 * @typedef {import("./vendors.js").Vendor} Vendor
 * @typedef {{ amount: number, desc: string, price: number, qty: number, unit: string }} LineItem
 * @typedef {{ contact: string, lines: string[], name: string, phone: string }} Buyer
 * @typedef {"left" | "center" | "right"} Align
 * @typedef {{ align: Align, label: string, width?: number }} Column
 *
 * A printed label, the value beside it, and optionally the ground-truth field
 * that value belongs to. The third slot is what lets the paper renderer stamp
 * `data-field` onto the node without knowing anything about the schema, and
 * what keeps the box annotations and the JSON sidecar naming one thing once.
 * @typedef {[label: string, value: string, field?: string]} LabelledValue
 *
 * @typedef {{ kind: "stamp", text: string }} StampBlock
 * @typedef {{ kind: "parties", label: string, lineFields?: (string | null)[], lines: string[], meta: LabelledValue[] }} PartiesBlock
 * @typedef {{ kind: "keygrid", columns: LabelledValue[][] }} KeyGridBlock
 * @typedef {{ kind: "partypair", columnFields?: (string | null)[][], columns: [string[], string[]], headings: [string, string] }} PartyPairBlock
 * @typedef {{ kind: "table", columns: Column[], dense?: boolean, fields?: (string | null)[], footer?: string[], rowScope?: string, rows: string[][] }} TableBlock
 * @typedef {{ kind: "totals", emphasisIndex: number, rows: LabelledValue[] }} TotalsBlock
 * @typedef {{ kind: "words", text: string }} WordsBlock
 * @typedef {{ kind: "note", text: string, tone: "plain" | "accent" }} NoteBlock
 * @typedef {{ kind: "callout", text: string }} CalloutBlock
 * @typedef {{ kind: "chips", items: LabelledValue[] }} ChipsBlock
 * @typedef {{ kind: "banner", field?: string, label: string, value: string }} BannerBlock
 * @typedef {{ kind: "signatures", labels: [string, string] }} SignaturesBlock
 * @typedef {{ kind: "signoff", text: string }} SignoffBlock
 *
 * @typedef {StampBlock | PartiesBlock | KeyGridBlock | PartyPairBlock | TableBlock
 *   | TotalsBlock | WordsBlock | NoteBlock | CalloutBlock | ChipsBlock | BannerBlock
 *   | SignaturesBlock | SignoffBlock} DocumentBlock
 *
 * @typedef {{ balance: number, charge: number | null, date: Date, description: string, payment: number | null, reference: string }} LedgerEntry
 * @typedef {{ grand: number, subtotal: number, tax: number, taxRate: number }} Totals
 *
 * The structured truth a builder had in hand before it stringified anything.
 *
 * Every property beyond `buyer`, `documentDate` and `documentNumber` is
 * optional because document types genuinely differ: a delivery challan has no
 * totals and a statement has no line items. `annotations.js` turns an absent
 * property into an explicit `null` in the sidecar, so a consumer can always
 * tell "this document has no due date" from "the generator forgot to record
 * one".
 * A property is set only when the document actually prints the thing. That is
 * the whole contract: `buyer_phone` is null on a clean invoice because a clean
 * invoice does not show one, and an extractor scored against this file is
 * therefore never penalised for failing to read something that is not there.
 * @typedef {{
 *   againstInvoice?: string,
 *   amountPaid?: number,
 *   balanceDue?: number,
 *   buyer: Buyer,
 *   buyerContact?: string,
 *   buyerPhone?: string,
 *   documentDate: Date,
 *   documentNumber: string,
 *   dueDate?: Date,
 *   items?: LineItem[],
 *   itemsPriced?: boolean,
 *   lineProductCodes?: string[],
 *   lineRemarks?: string[],
 *   lineSkus?: string[],
 *   lineTaxes?: number[],
 *   orderDate?: Date,
 *   orderNumber?: string,
 *   packageCount?: number,
 *   paymentMethod?: string,
 *   paymentTerms?: string,
 *   periodEnd?: Date,
 *   periodStart?: Date,
 *   poNumber?: string,
 *   reason?: string,
 *   reference?: string,
 *   shipping?: number,
 *   totalQuantity?: number,
 *   totals?: Totals,
 *   transactions?: LedgerEntry[],
 *   validUntil?: Date,
 *   vehicleNumber?: string,
 *   vendorCompanyReg?: string
 * }} DocumentFacts
 *
 * @typedef {{ blocks: DocumentBlock[], facts: DocumentFacts, title?: string, variantId?: string }} BuiltDocument
 *
 * @typedef {{
 *   blocks: DocumentBlock[],
 *   dense: boolean,
 *   docTypeId: string,
 *   docTypeLabel: string,
 *   docVariantId: string,
 *   facts: DocumentFacts,
 *   filenameBase: string,
 *   footer: string,
 *   seed: number,
 *   style: string,
 *   subtitle: string,
 *   title: string,
 *   vendor: Vendor
 * }} DocumentModel
 */

const BUYER_NAMES = [
  "Northpoint Retail Group",
  "Cedar and Co. Holdings",
  "BlueRiver Manufacturing",
  "Summit Hospitality LLC",
  "Greystone Property Mgmt",
  "Tideline Distributors",
  "Maplewood Trading Co.",
  "Ironvale Logistics",
  "Brightline Hospitality",
  "Crestar Wholesale",
  "Pinnacle Foodservice",
  "Westgate Supply Chain",
  "Halcyon Retail Partners",
  "Stonebridge Holdings",
  "Vertex Procurement Inc.",
  "Lakeshore Distribution"
];

const BUYER_CITIES = /** @type {[string, string, string][]} */ ([
  ["Denver", "CO", "802"],
  ["Austin", "TX", "787"],
  ["Seattle", "WA", "981"],
  ["Atlanta", "GA", "303"],
  ["Chicago", "IL", "606"],
  ["Phoenix", "AZ", "850"],
  ["Boston", "MA", "021"],
  ["Tampa", "FL", "336"]
]);

const BUYER_STREETS = [
  "Commerce Ave",
  "Market St",
  "Industry Blvd",
  "Harbor Way",
  "Park Row"
];

const BUYER_CONTACTS = [
  "Accounts Payable",
  "Finance Dept",
  "Procurement",
  "AP Team",
  "Purchasing Office"
];

const PAYMENT_METHODS = [
  "Visa ****4021",
  "ACH Transfer",
  "Wire Transfer",
  "Check #2287",
  "Mastercard ****8830"
];

const CREDIT_REASONS = [
  "Goods returned, damaged in transit",
  "Price adjustment per agreement",
  "Short-shipped items credited",
  "Overcharge on original invoice"
];

const DEBIT_REASONS = [
  "Additional freight charges",
  "Price revision, undercharged",
  "Extra units supplied",
  "Correction to invoice total"
];

const SAMPLE_FOOTNOTE = "Sample document generated for testing. Not a valid tax record.";

/** Days of account activity a statement of account covers. */
const PERIOD_DAYS = 91;

/**
 * Rolling hash over a string, seeded and bounded by its caller.
 * @param {string} text - Text to hash.
 * @param {number} initial - Starting value.
 * @param {number} multiplier - Per-character multiplier.
 * @param {number} modulo - Upper bound on the result.
 * @returns {number} Deterministic hash below `modulo`.
 */
function hashText(text, initial, multiplier, modulo) {
  let hash = initial;

  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * multiplier + text.charCodeAt(index)) % modulo;
  }

  return hash;
}

/**
 * A small stable number derived from a vendor id.
 *
 * The seed owns the commercial event: which buyer, which dates. The vendor owns
 * its own paperwork: its document number series, its ledger, how many of its own
 * catalogue items it puts on a page. Those used to be seed-only, so one seed
 * produced the same invoice number, the same quantity vector, and a
 * byte-identical statement across all six vendors. Folding this salt into the
 * vendor-owned derivations separates them while leaving the buyer and the dates
 * shared, which is what keeps the side-by-side comparison in the About section
 * honest.
 * @param {string} vendorId - Vendor identifier.
 * @returns {number} Deterministic salt for that vendor.
 */
export function vendorSalt(vendorId) {
  return hashText(vendorId, 11, 37, 99_991);
}

/**
 * Plausible quantity range per unit of measure.
 *
 * Drawing 2 to 40 of everything produced nonsense on the service and freight
 * catalogues: fourteen forty-foot shipping containers and eight "shipments" of
 * a document handling fee on one page. Anything not listed keeps the wide
 * default, so a new catalogue entry with a familiar unit is covered without
 * touching this table.
 * @type {Record<string, [number, number]>}
 */
const QTY_RANGE_BY_UNIT = {
  ctr: [1, 4],
  day: [1, 10],
  mo: [1, 3],
  shp: [1, 4],
  yr: [1, 3]
};

/** Quantity range for units with no entry in `QTY_RANGE_BY_UNIT`. */
const DEFAULT_QTY_RANGE = /** @type {[number, number]} */ ([2, 40]);

/**
 * Build the line items for one document.
 * @param {string} vendorId - Vendor whose catalogue to draw from.
 * @param {number} seed - Seed driving order, price jitter, and quantities.
 * @param {number} count - Maximum number of items to include.
 * @returns {LineItem[]} Line items with per-row amounts already rounded.
 */
export function buildItems(vendorId, seed, count) {
  const catalog = catalogFor(vendorId);
  const random = createSeededRandom(seed);
  const order = shuffleIndices(catalog.length, random);
  const items = [];

  for (let index = 0; index < count && index < order.length; index += 1) {
    const entry = catalog[order[index]];
    // Around +/-4% of list price, then rounded the way a real price list would
    // be: to the dollar above $100, to the nearest nickel below it.
    const jitter = 1 + (random() * 0.08 - 0.04);
    const jittered = entry.basePrice * jitter;
    const price =
      entry.basePrice >= 100
        ? Math.round(jittered)
        : roundCents(Math.round(jittered * 20) / 20);
    const [minQty, maxQty] = QTY_RANGE_BY_UNIT[entry.unit] ?? DEFAULT_QTY_RANGE;
    const qty = minQty + Math.floor(random() * (maxQty - minQty + 1));

    items.push({
      desc: entry.desc,
      unit: entry.unit,
      price,
      qty,
      amount: roundCents(qty * price)
    });
  }

  return items;
}

/**
 * Stable per-item product code.
 *
 * The dense invoice used to print an HSN column, which is an Indian GST
 * classification sitting next to a US sales-tax scheme and an EIN, and its
 * values were the row index plus a constant rather than a classification of
 * anything. A neutral internal product code carries the same "extra identifier
 * column" signal for extraction work without claiming a jurisdiction, and
 * hashing the description means one catalogue item keeps one code everywhere.
 * @param {string} description - Catalogue description.
 * @returns {string} Six-digit product code.
 */
export function productCode(description) {
  return padNumber(hashText(description, 7, 31, 1_000_000), 6);
}

/**
 * Derive the buying party for a seed.
 * @param {number} seed - Seed driving the buyer identity.
 * @returns {Buyer} Buyer name, address lines, contact, and phone.
 */
export function buildBuyer(seed) {
  const city = BUYER_CITIES[Math.floor(seed / 7) % BUYER_CITIES.length];
  const street = pickFrom(BUYER_STREETS, seed);
  const houseNumber = 100 + ((seed * 7) % 900);
  const suite = 20 + (seed % 80);

  return {
    name: pickFrom(BUYER_NAMES, seed),
    lines: [
      `${houseNumber} ${street}, Suite ${suite}`,
      `${city[0]}, ${city[1]} ${city[2]}${padNumber(seed % 99, 2)}`
    ],
    contact: pickFrom(BUYER_CONTACTS, seed),
    phone: `(720) 555-0${100 + (seed % 800)}`
  };
}

/**
 * Round each line's share of the tax.
 * @param {LineItem[]} items - Priced line items.
 * @param {number} [taxRate=TAX_RATE] - Sales-tax rate as a fraction.
 * @returns {number[]} Tax for each line, in line order.
 */
export function computeLineTaxes(items, taxRate = TAX_RATE) {
  return items.map((item) => roundCents(item.amount * taxRate));
}

/**
 * Sum line items and apply the flat sales-tax rate.
 *
 * The tax is the sum of the per-line rounded tax, not the rate applied once to
 * the subtotal. Those two disagree by a cent whenever the per-line rounding
 * happens to push the same way: the clean and dense layouts of one seed used to
 * print $53,484.92 and $53,484.93 for the same five lines, because each did it
 * the other way. Summing the lines is the definition every layout can honour,
 * including the dense one that has to print a tax column that adds up.
 * @param {LineItem[]} items - Priced line items.
 * @param {number} [taxRate=TAX_RATE] - Sales-tax rate as a fraction.
 * @returns {{ grand: number, subtotal: number, tax: number, taxRate: number }} Totals.
 */
export function computeTotals(items, taxRate = TAX_RATE) {
  const subtotal = roundCents(items.reduce((sum, item) => sum + item.amount, 0));
  const tax = roundCents(
    computeLineTaxes(items, taxRate).reduce((sum, lineTax) => sum + lineTax, 0)
  );
  return { subtotal, tax, grand: roundCents(subtotal + tax), taxRate };
}

const DISPATCH_NOTES = [
  "",
  "",
  "",
  ", handle with care",
  ", partial dispatch",
  ", inspected",
  ", stacked on pallet"
];

/**
 * Lot number and optional handling note stamped against one challan row.
 * @param {number} seed - Document seed.
 * @param {number} index - Row index.
 * @returns {string} Distinct dispatch remark.
 */
function dispatchRemark(seed, index) {
  const lot = `${padNumber(((seed * 13 + index * 29) % 8_999) + 1_000, 4)}-${padNumber(index + 1, 2)}`;
  return `Lot ${lot}${DISPATCH_NOTES[(seed * 7 + index * 5) % DISPATCH_NOTES.length]}`;
}

/**
 * How many packages the dispatched goods are crated into.
 * @param {LineItem[]} items - Dispatched line items.
 * @param {number} seed - Document seed.
 * @returns {number} Package count, always at least one per line item.
 */
function packageCount(items, seed) {
  const random = createSeededRandom(seed + 613);
  return items.reduce((sum) => sum + 1 + Math.floor(random() * 3), 0);
}

/** Units that describe a service rather than something that ships in a crate. */
const SERVICE_UNITS = new Set(["day", "mo", "shp", "yr"]);

/**
 * Freight and handling charged on top of the line items.
 *
 * This used to be a hardcoded `$0.00` on every dense invoice, which is a dead
 * field: an extractor can learn it without reading the page. A page of services
 * still ships nothing, so those stay at zero and the corpus keeps genuine zeros
 * alongside genuine values.
 * @param {LineItem[]} items - Priced line items.
 * @param {number} seed - Seed driving the charge.
 * @returns {number} Shipping and handling in currency units.
 */
export function shippingCharge(items, seed) {
  if (items.every((item) => SERVICE_UNITS.has(item.unit))) {
    return 0;
  }

  const random = createSeededRandom(seed + 907);

  // Roughly a fifth of goods shipments go out carriage paid.
  return random() < 0.2 ? 0 : roundCents(Math.round(random() * 340 + 35) + 0.5);
}

/** @returns {Column[]} Standard priced item table columns. */
function pricedColumns() {
  return [
    { label: "#", align: "center", width: 24 },
    { label: "Description", align: "left" },
    { label: "Qty", align: "center" },
    { label: "Unit", align: "center" },
    { label: "Unit price", align: "right" },
    { label: "Amount", align: "right" }
  ];
}

/**
 * Ground-truth field for each column of the standard priced table.
 *
 * `null` marks a column that carries no extractable fact: the row number is an
 * artefact of the layout, not something a parser should be scored on.
 * @type {(string | null)[]}
 */
const PRICED_FIELDS = [null, "description", "quantity", "unit", "unit_price", "amount"];

/**
 * The buying party's address block, paired with the field each line belongs to.
 *
 * The renderer stamps these onto the individual line elements, so a two-line
 * address produces two `buyer_address` regions rather than one box stretched
 * over the gap between them.
 * @param {string} label - Heading above the buyer.
 * @param {Buyer} buyer - Buyer to render.
 * @param {LabelledValue[]} meta - Document metadata beside the buyer.
 * @param {string} [trailing] - Optional last line, such as a contact or phone.
 * @param {string} [trailingField] - Ground-truth field for that last line.
 * @returns {PartiesBlock} Buyer and document metadata block.
 */
function partiesBlock(label, buyer, meta, trailing, trailingField) {
  const lines = [buyer.name, ...buyer.lines];
  /** @type {(string | null)[]} */
  const lineFields = ["buyer_name", ...buyer.lines.map(() => "buyer_address")];

  if (trailing !== undefined) {
    lines.push(trailing);
    lineFields.push(trailingField ?? null);
  }

  return { kind: "parties", label, lines, lineFields, meta };
}

/**
 * @param {LineItem[]} items - Line items to render.
 * @returns {string[][]} Row cells as display strings.
 */
function pricedRows(items) {
  return items.map((item, index) => [
    String(index + 1),
    item.desc,
    String(item.qty),
    item.unit,
    formatMoney(item.price),
    formatMoney(item.amount)
  ]);
}

/**
 * @param {LineItem[]} items - Line items to render.
 * @returns {TableBlock} Standard priced line-item table.
 */
function pricedTable(items) {
  return {
    kind: "table",
    columns: pricedColumns(),
    fields: PRICED_FIELDS,
    rowScope: "line_items",
    rows: pricedRows(items)
  };
}

/**
 * Build the standard subtotal / tax / total block.
 * @param {ReturnType<typeof computeTotals>} totals - Computed totals.
 * @param {number | null} [shipping] - Optional shipping charge.
 * @returns {TotalsBlock} Totals block with the grand total emphasised.
 */
function totalsBlock(totals, shipping = null) {
  const rows = /** @type {LabelledValue[]} */ ([
    ["Subtotal", formatMoney(totals.subtotal), "subtotal"],
    [`Sales tax (${formatRate(totals.taxRate)})`, formatMoney(totals.tax), "tax_amount"]
  ]);

  if (shipping !== null) {
    rows.push(["Shipping and handling", formatMoney(shipping), "shipping"]);
  }

  rows.push(["TOTAL", formatMoney(totals.grand), "grand_total"]);

  return {
    kind: "totals",
    rows,
    emphasisIndex: rows.length - 1
  };
}

/**
 * Shared context every per-type builder receives.
 * @typedef {{
 *   baseDate: Date,
 *   buyer: Buyer,
 *   daysAgo: number,
 *   number: string,
 *   random: () => number,
 *   seed: number,
 *   vendor: Vendor
 * }} BuildContext
 */

/**
 * @param {BuildContext} context - Shared document context.
 * @returns {LineItem[]} Lines shared by an invoice, its receipt, and its adjustment notes.
 */
function invoiceItems(context) {
  return buildItems(
    context.vendor.id,
    context.seed * 3 + vendorSalt(context.vendor.id),
    pickCount(context.seed, 3, 5)
  );
}

/**
 * @param {BuildContext} context - Shared document context.
 * @returns {BuiltDocument} Clean commercial invoice.
 */
function buildInvoice(context) {
  const items = invoiceItems(context);
  const totals = computeTotals(items);
  const shipping = shippingCharge(items, context.seed);
  const billedTotals = { ...totals, grand: roundCents(totals.grand + shipping) };
  const due = addDays(context.baseDate, 30);
  const documentNumber = `INV-${context.number}`;

  return {
    facts: {
      buyer: context.buyer,
      buyerContact: context.buyer.contact,
      documentDate: context.baseDate,
      documentNumber,
      dueDate: due,
      items,
      paymentTerms: "Net 30",
      shipping,
      totals: billedTotals
    },
    blocks: [
      partiesBlock(
        "Bill to",
        context.buyer,
        [
          ["Invoice #", documentNumber, "document_number"],
          ["Date", formatDate(context.baseDate), "document_date"],
          ["Due date", formatDate(due), "due_date"],
          ["Terms", "Net 30", "payment_terms"]
        ],
        context.buyer.contact,
        "buyer_contact"
      ),
      pricedTable(items),
      totalsBlock(billedTotals, shipping),
      {
        kind: "note",
        tone: "accent",
        text: `Please remit payment by the due date. Make checks payable to ${context.vendor.name}. Late payments are subject to 1.5% monthly interest.`
      }
    ]
  };
}

/**
 * @param {BuildContext} context - Shared document context.
 * @returns {BuiltDocument} Dense line-level tax invoice.
 */
function buildDenseInvoice(context) {
  const { vendor, buyer, seed, baseDate, number, random } = context;
  // Deliberately the same draw as `buildInvoice`. The two layouts are two
  // treatments of one invoice, which is what the layout toggle promises, and it
  // is the only way the grand totals can be expected to agree.
  const items = invoiceItems(context);
  const orderNumber = `ORD-${padNumber(Math.floor(random() * 8_999_999_999) + 1_000_000_000, 10)}`;
  const reference = `${vendor.id}-${padNumber(Math.floor(random() * 899_999_999_999) + 100_000_000_000, 12)}-1`;

  // The same helpers the clean invoice uses, so one seed cannot print two
  // different grand totals depending on which layout is showing.
  const totals = computeTotals(items);
  const lineTaxes = computeLineTaxes(items);
  const shipping = shippingCharge(items, seed);
  const grand = roundCents(totals.grand + shipping);
  const documentNumber = `INV-${number}`;
  const dueDate = addDays(baseDate, 30);
  const orderDate = addDays(baseDate, -6);
  const skus = items.map(
    (_item, index) => `${vendor.id.slice(0, 3).toUpperCase()}${padNumber(seed * 7 + index * 13, 6)}`
  );
  const productCodes = items.map((item) => productCode(item.desc));

  const rows = items.map((item, index) => [
    String(index + 1),
    item.desc,
    skus[index],
    productCodes[index],
    String(item.qty),
    item.unit,
    formatMoney(item.price),
    formatMoney(item.amount),
    formatRate(TAX_RATE),
    formatMoney(lineTaxes[index]),
    formatMoney(roundCents(item.amount + lineTaxes[index]))
  ]);

  const blocks = /** @type {DocumentBlock[]} */ ([
    {
      kind: "keygrid",
      columns: [
        [
          // Every buyer in the corpus is a business with an accounts-payable
          // contact, and the seller carries a tax id. That is B2B.
          ["Supply type", "B2B"],
          ["Document type code", "Invoice"],
          ["Seller legal name", `${vendor.name} Inc.`],
          ["Seller address", vendor.addr, "vendor_address"],
          ["Seller tax ID", vendor.taxId, "vendor_tax_id"],
          ["Tax scheme", "US sales tax"],
          ["Currency", "USD"],
          ["Invoice type", "Regular"],
          ["Payment terms", "Net 30", "payment_terms"]
        ],
        [
          // A company registration belongs to the seller, not to the seed. It
          // used to be derived from the seed alone, so all six vendors shared
          // one registration number.
          ["Company reg", vendor.companyReg, "vendor_company_reg"],
          ["Order number", orderNumber, "order_number"],
          ["Order date", formatDate(orderDate), "order_date"],
          ["Support email", vendor.email, "vendor_email"],
          ["Support phone", vendor.phone, "vendor_phone"],
          ["Invoice number", documentNumber, "document_number"],
          ["Invoice date", formatDate(baseDate), "document_date"],
          ["Due date", formatDate(dueDate), "due_date"],
          ["Reference", reference, "reference"]
        ]
      ]
    },
    {
      kind: "partypair",
      headings: ["Details of receiver (billed to)", "Details of consignee (shipped to)"],
      columns: [
        [buyer.name, ...buyer.lines, `Contact: ${buyer.contact}`],
        [buyer.name, ...buyer.lines, `Tel: ${buyer.phone}`]
      ],
      // Only the receiver column is tagged. The consignee repeats the same
      // party, and tagging both would put two regions with the same field on
      // opposite sides of the page for one printed fact.
      columnFields: [
        ["buyer_name", ...buyer.lines.map(() => "buyer_address"), null],
        [null, ...buyer.lines.map(() => null), null]
      ]
    },
    {
      kind: "table",
      dense: true,
      columns: [
        { label: "Sl", align: "center" },
        { label: "Item description", align: "left" },
        { label: "SKU", align: "center" },
        { label: "Product code", align: "center" },
        { label: "Qty", align: "center" },
        { label: "UOM", align: "center" },
        { label: "Rate", align: "right" },
        { label: "Assessable", align: "right" },
        { label: "Tax rate", align: "center" },
        { label: "Tax amt", align: "right" },
        { label: "Item total", align: "right" }
      ],
      fields: [
        null,
        "description",
        "sku",
        "product_code",
        "quantity",
        "unit",
        "unit_price",
        "amount",
        "tax_rate",
        "tax_amount",
        "line_total"
      ],
      rowScope: "line_items",
      rows,
      // The table footer totals the line items. Shipping is not a line item, so
      // it joins below and only the totals block carries the grand total.
      footer: [
        "Total",
        "",
        "",
        "",
        "",
        "",
        "",
        formatMoney(totals.subtotal),
        "",
        formatMoney(totals.tax),
        formatMoney(totals.grand)
      ]
    },
    {
      kind: "totals",
      rows: [
        ["Total assessable value", formatMoney(totals.subtotal), "subtotal"],
        ["Total sales tax", formatMoney(totals.tax), "tax_amount"],
        ["Shipping and handling", formatMoney(shipping), "shipping"],
        ["Grand total", formatMoney(grand), "grand_total"]
      ],
      emphasisIndex: 3
    },
    { kind: "words", text: `Grand total (in words): ${amountInWords(grand)}` },
    {
      kind: "note",
      tone: "plain",
      text: "Notes: 1. Sales tax is collected per applicable state regulations. 2. Reverse charge is not applicable to this supply. 3. For prepaid orders the amount is already received."
    },
    { kind: "signoff", text: `For ${vendor.name} Inc.` },
    { kind: "signatures", labels: ["Authorised signatory", "Date"] }
  ]);

  return {
    blocks,
    facts: {
      buyer,
      buyerContact: buyer.contact,
      buyerPhone: buyer.phone,
      documentDate: baseDate,
      documentNumber,
      dueDate,
      items,
      lineProductCodes: productCodes,
      lineSkus: skus,
      lineTaxes,
      orderDate,
      orderNumber,
      paymentTerms: "Net 30",
      reference,
      shipping,
      // The printed grand total includes shipping, which is not a line item, so
      // the sidecar's `grand_total` has to include it too or the JSON and the
      // page disagree about the one number a payer cares about.
      totals: { ...totals, grand },
      vendorCompanyReg: vendor.companyReg
    }
  };
}

/**
 * @param {BuildContext} context - Shared document context.
 * @returns {BuiltDocument} Payment receipt with a zero balance.
 */
function buildReceipt(context) {
  // A receipt settles the invoice produced by the same seed, so it must repeat
  // that invoice's lines and amount rather than merely borrowing its number.
  const items = invoiceItems(context);
  const totals = computeTotals(items);
  const shipping = shippingCharge(items, context.seed);
  const paidTotals = { ...totals, grand: roundCents(totals.grand + shipping) };
  const documentNumber = `RCP-${context.number}`;
  const againstInvoice = `INV-${context.number}`;
  const paymentMethod = pickFrom(PAYMENT_METHODS, context.seed);
  const receiptDate = addDays(
    context.baseDate,
    pickCount(context.seed * 11, 0, Math.min(30, context.daysAgo))
  );

  return {
    facts: {
      againstInvoice,
      amountPaid: paidTotals.grand,
      balanceDue: 0,
      buyer: context.buyer,
      buyerContact: context.buyer.contact,
      documentDate: receiptDate,
      documentNumber,
      items,
      paymentMethod,
      shipping,
      totals: paidTotals
    },
    blocks: [
      { kind: "stamp", text: "PAID" },
      partiesBlock(
        "Received from",
        context.buyer,
        [
          ["Receipt #", documentNumber, "document_number"],
          ["Date", formatDate(receiptDate), "document_date"],
          // One seed is one commercial event, so the receipt settles the invoice
          // that same seed produces. It used to derive its own unrelated number,
          // which meant no receipt in the corpus could ever be matched to an
          // invoice in the corpus.
          ["Against invoice", againstInvoice, "against_invoice"],
          ["Method", paymentMethod, "payment_method"]
        ],
        context.buyer.contact,
        "buyer_contact"
      ),
      pricedTable(items),
      {
        // The subtotal and tax rows are not decoration. Without them the receipt
        // jumped from a line-item table straight to an amount due that silently
        // included 8.25%, so the printed lines never summed to the printed total.
        kind: "totals",
        rows: [
          ["Subtotal", formatMoney(totals.subtotal), "subtotal"],
          [`Sales tax (${formatRate(totals.taxRate)})`, formatMoney(totals.tax), "tax_amount"],
          ["Shipping and handling", formatMoney(shipping), "shipping"],
          ["Amount due", formatMoney(paidTotals.grand), "grand_total"],
          ["AMOUNT PAID", formatMoney(paidTotals.grand), "amount_paid"],
          ["Balance due", formatMoney(0), "balance_due"]
        ],
        emphasisIndex: 4
      },
      {
        kind: "note",
        tone: "plain",
        text: "Thank you for your payment. This receipt confirms funds received in full."
      }
    ]
  };
}

/**
 * @param {BuildContext} context - Shared document context.
 * @returns {BuiltDocument} Quotation, explicitly marked as not a tax invoice.
 */
function buildQuotation(context) {
  const items = buildItems(context.vendor.id, context.seed * 7 + vendorSalt(context.vendor.id), pickCount(context.seed, 3, 6));
  const totals = computeTotals(items);
  const documentNumber = `QTE-${context.number}`;
  const validUntil = addDays(context.baseDate, 14);

  return {
    facts: {
      buyer: context.buyer,
      documentDate: context.baseDate,
      documentNumber,
      items,
      totals,
      validUntil
    },
    blocks: [
      partiesBlock("Prepared for", context.buyer, [
        ["Quote #", documentNumber, "document_number"],
        ["Date", formatDate(context.baseDate), "document_date"],
        ["Valid until", formatDate(validUntil), "valid_until"],
        ["Prepared by", "Sales team"]
      ]),
      pricedTable(items),
      totalsBlock(totals),
      {
        kind: "note",
        tone: "accent",
        text: "Prices are estimates valid for 14 days and subject to change. This quotation is not a tax invoice or a demand for payment. To proceed, issue a purchase order referencing the quote number above."
      }
    ]
  };
}

/**
 * @param {BuildContext} context - Shared document context.
 * @returns {BuiltDocument} Delivery challan with no prices.
 */
function buildChallan(context) {
  const items = buildItems(context.vendor.id, context.seed * 11 + vendorSalt(context.vendor.id), pickCount(context.seed, 3, 6));
  const totalQty = items.reduce((sum, item) => sum + item.qty, 0);
  const poNumber = `PO-${padNumber(Math.floor(createSeededRandom(context.seed + 41)() * 8_999_999) + 1_000_000, 7)}`;
  const documentNumber = `DC-${context.number}`;
  const vehicleNumber = `TX-${4100 + (context.seed % 900)}`;
  const packages = packageCount(items, context.seed);
  const remarks = items.map((_item, index) => dispatchRemark(context.seed, index));

  return {
    facts: {
      buyer: context.buyer,
      documentDate: context.baseDate,
      documentNumber,
      items,
      itemsPriced: false,
      lineRemarks: remarks,
      packageCount: packages,
      poNumber,
      totalQuantity: totalQty,
      vehicleNumber
    },
    blocks: [
      partiesBlock("Deliver to", context.buyer, [
        ["Challan #", documentNumber, "document_number"],
        ["Date", formatDate(context.baseDate), "document_date"],
        ["PO ref", poNumber, "po_number"],
        ["Vehicle no", vehicleNumber, "vehicle_number"]
      ]),
      {
        kind: "table",
        columns: [
          { label: "#", align: "center", width: 24 },
          { label: "Description", align: "left" },
          { label: "Qty", align: "center" },
          { label: "Unit", align: "center" },
          { label: "Remarks", align: "left" }
        ],
        fields: [null, "description", "quantity", "unit", "remarks"],
        rowScope: "line_items",
        // The remarks column used to read "Goods only" on every row, which is a
        // column of one repeated constant. A lot number plus the occasional
        // handling note gives it something an extraction pipeline can actually be
        // asked to read.
        rows: items.map((item, index) => [
          String(index + 1),
          item.desc,
          String(item.qty),
          item.unit,
          remarks[index]
        ])
      },
      {
        kind: "chips",
        items: [
          // Packages are how the goods are crated, not how many rows the table
          // has. Those were the same number on every challan ever generated.
          ["Total packages", String(packages), "package_count"],
          ["Total qty", String(totalQty), "total_quantity"]
        ]
      },
      {
        kind: "note",
        tone: "accent",
        text: "The goods described above are dispatched for delivery. This document is not a sale invoice and no payment is due against it. Any value shown is for transport and insurance purposes only."
      },
      { kind: "signatures", labels: ["Dispatched by", "Received by (sign and date)"] }
    ]
  };
}

/**
 * Credit or debit note, chosen by seed parity.
 *
 * The selectable type is "Credit or debit note", so a page that says DEBIT NOTE
 * is correct. What was wrong is that the filename and the ZIP folder still said
 * `creditnote`, which means the label contradicted the image for half the
 * corpus. The resolved variant is returned so the filename can say which one it
 * actually is.
 * @param {BuildContext} context - Shared document context.
 * @returns {BuiltDocument} Body blocks, facts, title, and the resolved variant.
 */
function buildAdjustmentNote(context) {
  const isCredit = context.seed % 2 === 0;
  const title = isCredit ? "Credit note" : "Debit note";
  const variantId = isCredit ? "creditnote" : "debitnote";
  const salt = vendorSalt(context.vendor.id);
  const sourceItems = invoiceItems(context);
  const itemOrder = shuffleIndices(
    sourceItems.length,
    createSeededRandom(context.seed * 13 + salt)
  );
  const items = itemOrder
    .slice(0, pickCount(context.seed, 1, Math.min(3, sourceItems.length)))
    .map((index) => sourceItems[index]);
  const totals = computeTotals(items);
  const reasons = isCredit ? CREDIT_REASONS : DEBIT_REASONS;
  const documentNumber = `${isCredit ? "CN" : "DN"}-${context.number}`;
  const againstInvoice = `INV-${context.number}`;
  const reason = pickFrom(reasons, context.seed);

  return {
    title,
    variantId,
    facts: {
      againstInvoice,
      buyer: context.buyer,
      documentDate: context.baseDate,
      documentNumber,
      items,
      reason,
      totals
    },
    blocks: [
      partiesBlock("Issued to", context.buyer, [
        [`${title} #`, documentNumber, "document_number"],
        ["Date", formatDate(context.baseDate), "document_date"],
        ["Against invoice", againstInvoice, "against_invoice"],
        ["Reason", reason, "adjustment_reason"]
      ]),
      pricedTable(items),
      totalsBlock(totals),
      {
        kind: "callout",
        text: isCredit
          ? `This credit note reduces the amount you owe by ${formatMoney(totals.grand)}. It has been applied against the referenced invoice.`
          : `This debit note adds ${formatMoney(totals.grand)} to the amount payable against the referenced invoice.`
      }
    ]
  };
}

/**
 * @param {BuildContext} context - Shared document context.
 * @returns {BuiltDocument} Statement of account with a running ledger.
 */
function buildStatement(context) {
  const salt = vendorSalt(context.vendor.id);
  const random = createSeededRandom(context.seed * 17 + salt);

  // The ledger has to end on or before the day the statement was generated. It
  // used to start at `new Date(year, seed % 6, 3)`, which had no relationship to
  // the generated date at all: a statement generated in March would list
  // transactions running through June, summarising activity that had not
  // happened yet, and no statement could ever fall in the second half of a year.
  const periodStart = addDays(context.baseDate, -PERIOD_DAYS);

  // Six movement dates drawn anywhere in the period and then sorted, rather than
  // accumulated from random gaps. Accumulating cannot fill the period without
  // sometimes running past its end, and clamping the overshoot piles rows onto
  // the last day. Drawing then sorting is monotonic and in-bounds by
  // construction, so the ledger always spans the period the heading claims.
  const offsets = Array.from({ length: 6 }, () => 1 + Math.floor(random() * PERIOD_DAYS)).sort(
    (left, right) => left - right
  );

  // The period opens with the balance carried in from the previous one, so the
  // first payment has something to settle. Without it a ledger that happens to
  // draw a payment first would go negative, which a statement of account never
  // does: you cannot pay down a debt you do not have.
  let balance = roundCents(180 + random() * 1400);
  /** @type {LedgerEntry[]} */
  const transactions = [
    {
      balance,
      charge: null,
      date: periodStart,
      description: "Balance brought forward",
      payment: null,
      reference: ""
    }
  ];

  for (let index = 0; index < 6; index += 1) {
    const cursor = addDays(periodStart, offsets[index]);
    const amount = roundCents(60 + random() * 1800);

    // A payment is only drawn when there is something outstanding, and it is
    // capped at the outstanding amount.
    const isCharge = random() > 0.45 || balance <= 0;
    const charge = isCharge ? amount : null;
    const paid = Math.min(amount, balance);
    const payment = isCharge ? null : paid;
    balance = roundCents(isCharge ? balance + amount : balance - paid);
    transactions.push({
      balance,
      charge,
      date: cursor,
      description: isCharge ? "Invoice" : "Payment received",
      payment,
      reference: `${isCharge ? "INV" : "PMT"}-${padNumber(
        (isCharge ? 1000 + index * 11 : 500 + index * 7) + context.seed + salt
      )}`
    });
  }

  const lastMovement = addDays(periodStart, offsets[offsets.length - 1]);
  const documentNumber = `STM-${context.number}`;

  return {
    facts: {
      balanceDue: balance,
      buyer: context.buyer,
      documentDate: context.baseDate,
      documentNumber,
      periodEnd: lastMovement,
      periodStart,
      transactions
    },
    blocks: [
      partiesBlock("Account", context.buyer, [
        ["Statement #", documentNumber, "document_number"],
        // The printed period describes the rows underneath it. The old label was
        // `Q${1 + seed % 4}`, a quarter drawn from the seed and unrelated to
        // both the transactions and the generated date, so a Q4 heading routinely
        // sat on a ledger of Q2 rows.
        ["Period", `${formatDate(periodStart)} - ${formatDate(lastMovement)}`],
        ["Generated", formatDate(context.baseDate), "document_date"]
      ]),
      {
        kind: "table",
        columns: [
          { label: "Date", align: "left" },
          { label: "Ref", align: "left" },
          { label: "Description", align: "left" },
          { label: "Charges", align: "right" },
          { label: "Payments", align: "right" },
          { label: "Balance", align: "right" }
        ],
        fields: ["date", "reference", "description", "charge", "payment", "balance"],
        rowScope: "transactions",
        rows: transactions.map((entry) => [
          formatDate(entry.date),
          entry.reference,
          entry.description,
          entry.charge === null ? "" : formatMoney(entry.charge),
          entry.payment === null ? "" : formatMoney(entry.payment),
          formatMoney(entry.balance)
        ])
      },
      { kind: "banner", label: "Balance due", value: formatMoney(balance), field: "balance_due" },
      {
        kind: "note",
        tone: "plain",
        text: `Summary of account activity for the period shown. Please remit any outstanding balance. Contact ${context.vendor.email} with questions.`
      }
    ]
  };
}

const SUBTITLES = /** @type {Record<string, string>} */ ({
  quotation: "THIS IS NOT A TAX INVOICE",
  receipt: "PAYMENT CONFIRMED",
  challan: "GOODS DISPATCH NOTE",
  creditnote: "ADJUSTMENT DOCUMENT",
  statement: "STATEMENT OF ACCOUNT"
});

/** @type {Record<string, (context: BuildContext) => BuiltDocument>} */
const DOCUMENT_BUILDERS = {
  invoice: buildInvoice,
  receipt: buildReceipt,
  quotation: buildQuotation,
  challan: buildChallan,
  creditnote: buildAdjustmentNote,
  statement: buildStatement
};

/**
 * Build the complete model for one document.
 * @param {{
 *   docTypeId: string,
 *   seed: number,
 *   style?: string,
 *   today?: Date,
 *   vendorId: string
 * }} options - Selection driving the document.
 * @returns {DocumentModel} Renderer-agnostic document model.
 */
export function buildDocument({ docTypeId, seed, style = "clean", today = new Date(), vendorId }) {
  const vendor = findVendor(vendorId);
  const docType = findDocumentType(docTypeId);
  const dense = docType.id === "invoice" && style === "dense";
  const random = createSeededRandom(seed + 13);
  // Draw order matters: days-ago first, then the document number, so a seed
  // keeps producing the same dates and numbers as it always has.
  const daysAgo = Math.floor(random() * 180);
  const baseDate = addDays(today, -daysAgo);
  // A document number comes out of the issuing vendor's own series, so the
  // vendor salt goes in here. The buyer and the base date above stay purely
  // seed-derived, which is what lets the same seed be compared across vendors.
  const number = padNumber(
    100_000 + ((Math.floor(random() * 899_999) + vendorSalt(vendor.id)) % 899_999),
    6
  );

  /** @type {BuildContext} */
  const context = { baseDate, buyer: buildBuyer(seed), daysAgo, number, random, seed, vendor };

  const title = dense ? "Tax invoice" : docType.id === "statement" ? "Statement" : docType.label;
  const built = dense ? buildDenseInvoice(context) : DOCUMENT_BUILDERS[docType.id](context);

  const variantId = built.variantId ?? docType.id;

  return {
    blocks: built.blocks,
    dense,
    docTypeId: docType.id,
    docTypeLabel: docType.label,
    docVariantId: variantId,
    facts: built.facts,
    filenameBase: `${vendor.id}_${variantId}${dense ? "_dense" : ""}_${seed}`,
    footer: `${vendor.name} - ${vendor.email} - ${vendor.tagline}. ${SAMPLE_FOOTNOTE}`,
    seed,
    style: dense ? "dense" : "clean",
    subtitle: SUBTITLES[docType.id] ?? "",
    title: built.title ?? title,
    vendor
  };
}
