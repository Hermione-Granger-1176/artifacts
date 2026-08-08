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
 * @typedef {{ kind: "stamp", text: string }} StampBlock
 * @typedef {{ kind: "parties", label: string, lines: string[], meta: [string, string][] }} PartiesBlock
 * @typedef {{ kind: "keygrid", columns: [string, string][][] }} KeyGridBlock
 * @typedef {{ kind: "partypair", headings: [string, string], columns: [string[], string[]] }} PartyPairBlock
 * @typedef {{ kind: "table", columns: Column[], rows: string[][], footer?: string[], dense?: boolean }} TableBlock
 * @typedef {{ kind: "totals", rows: [string, string][], emphasisIndex: number }} TotalsBlock
 * @typedef {{ kind: "words", text: string }} WordsBlock
 * @typedef {{ kind: "note", text: string, tone: "plain" | "accent" }} NoteBlock
 * @typedef {{ kind: "callout", text: string }} CalloutBlock
 * @typedef {{ kind: "chips", items: [string, string][] }} ChipsBlock
 * @typedef {{ kind: "banner", label: string, value: string }} BannerBlock
 * @typedef {{ kind: "signatures", labels: [string, string] }} SignaturesBlock
 * @typedef {{ kind: "signoff", text: string }} SignoffBlock
 *
 * @typedef {StampBlock | PartiesBlock | KeyGridBlock | PartyPairBlock | TableBlock
 *   | TotalsBlock | WordsBlock | NoteBlock | CalloutBlock | ChipsBlock | BannerBlock
 *   | SignaturesBlock | SignoffBlock} DocumentBlock
 *
 * @typedef {{
 *   blocks: DocumentBlock[],
 *   dense: boolean,
 *   docTypeId: string,
 *   docTypeLabel: string,
 *   docVariantId: string,
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
  let hash = 11;

  for (let index = 0; index < vendorId.length; index += 1) {
    hash = (hash * 37 + vendorId.charCodeAt(index)) % 99_991;
  }

  return hash;
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
  let hash = 7;

  for (let index = 0; index < description.length; index += 1) {
    hash = (hash * 31 + description.charCodeAt(index)) % 1_000_000;
  }

  return padNumber(hash, 6);
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
 * Lot number stamped against one challan row.
 * @param {number} seed - Document seed.
 * @param {number} index - Row index.
 * @returns {string} Lot code.
 */
function lotCode(seed, index) {
  return `${padNumber(((seed * 13 + index * 29) % 8_999) + 1_000, 4)}-${padNumber(index + 1, 2)}`;
}

/**
 * Optional handling note appended to a challan row.
 * @param {number} seed - Document seed.
 * @param {number} index - Row index.
 * @returns {string} Note text, empty for most rows.
 */
function dispatchNote(seed, index) {
  return DISPATCH_NOTES[(seed * 7 + index * 5) % DISPATCH_NOTES.length];
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

/**
 * Standard priced item table columns.
 * @returns {Column[]} Column definitions.
 */
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
 * Turn line items into priced table rows.
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
 * Build the standard subtotal / tax / total block.
 * @param {ReturnType<typeof computeTotals>} totals - Computed totals.
 * @returns {TotalsBlock} Totals block with the grand total emphasised.
 */
function totalsBlock(totals) {
  return {
    kind: "totals",
    rows: [
      ["Subtotal", formatMoney(totals.subtotal)],
      [`Sales tax (${formatRate(totals.taxRate)})`, formatMoney(totals.tax)],
      ["TOTAL", formatMoney(totals.grand)]
    ],
    emphasisIndex: 2
  };
}

/**
 * Shared context every per-type builder receives.
 * @typedef {{
 *   baseDate: Date,
 *   buyer: Buyer,
 *   number: string,
 *   random: () => number,
 *   seed: number,
 *   vendor: Vendor
 * }} BuildContext
 */

/**
 * Clean commercial invoice.
 * @param {BuildContext} context - Shared document context.
 * @returns {DocumentBlock[]} Blocks for the document body.
 */
function buildInvoice(context) {
  const items = buildItems(context.vendor.id, context.seed * 3 + vendorSalt(context.vendor.id), pickCount(context.seed, 3, 5));
  const totals = computeTotals(items);
  const due = addDays(context.baseDate, 30);

  return [
    {
      kind: "parties",
      label: "Bill to",
      lines: [context.buyer.name, ...context.buyer.lines, context.buyer.contact],
      meta: [
        ["Invoice #", `INV-${context.number}`],
        ["Date", formatDate(context.baseDate)],
        ["Due date", formatDate(due)],
        ["Terms", "Net 30"]
      ]
    },
    { kind: "table", columns: pricedColumns(), rows: pricedRows(items) },
    totalsBlock(totals),
    {
      kind: "note",
      tone: "accent",
      text: `Please remit payment by the due date. Make checks payable to ${context.vendor.name}. Late payments are subject to 1.5% monthly interest.`
    }
  ];
}

/**
 * Dense line-level tax invoice, the layout heavy extraction pipelines choke on.
 * @param {BuildContext} context - Shared document context.
 * @returns {DocumentBlock[]} Blocks for the document body.
 */
function buildDenseInvoice(context) {
  const { vendor, buyer, seed, baseDate, number, random } = context;
  const salt = vendorSalt(vendor.id);
  // Deliberately the same draw as `buildInvoice`. The two layouts are two
  // treatments of one invoice, which is what the layout toggle promises, and it
  // is the only way the grand totals can be expected to agree.
  const items = buildItems(vendor.id, seed * 3 + salt, pickCount(seed, 3, 5));
  const orderNumber = `ORD-${padNumber(Math.floor(random() * 8_999_999_999) + 1_000_000_000, 10)}`;
  const reference = `${vendor.id}-${padNumber(Math.floor(random() * 899_999_999_999) + 100_000_000_000, 12)}-1`;

  // The same helpers the clean invoice uses, so one seed cannot print two
  // different grand totals depending on which layout is showing.
  const totals = computeTotals(items);
  const lineTaxes = computeLineTaxes(items);
  const shipping = shippingCharge(items, seed);
  const grand = roundCents(totals.grand + shipping);

  const rows = items.map((item, index) => [
    String(index + 1),
    item.desc,
    `${vendor.id.slice(0, 3).toUpperCase()}${padNumber(seed * 7 + index * 13, 6)}`,
    productCode(item.desc),
    String(item.qty),
    item.unit,
    formatMoney(item.price),
    formatMoney(item.amount),
    formatRate(TAX_RATE),
    formatMoney(lineTaxes[index]),
    formatMoney(roundCents(item.amount + lineTaxes[index]))
  ]);

  return [
    {
      kind: "keygrid",
      columns: [
        [
          // Every buyer in the corpus is a business with an accounts-payable
          // contact, and the seller carries a tax id. That is B2B.
          ["Supply type", "B2B"],
          ["Document type code", "Invoice"],
          ["Seller legal name", `${vendor.name} Inc.`],
          ["Seller address", vendor.addr],
          ["Seller tax ID", vendor.taxId],
          ["Tax scheme", "US sales tax"],
          ["Currency", "USD"],
          ["Invoice type", "Regular"],
          ["Payment terms", "Net 30"]
        ],
        [
          // A company registration belongs to the seller, not to the seed. It
          // used to be derived from the seed alone, so all six vendors shared
          // one registration number.
          ["Company reg", vendor.companyReg],
          ["Order number", orderNumber],
          ["Order date", formatDate(addDays(baseDate, -6))],
          ["Support email", vendor.email],
          ["Support phone", vendor.phone],
          ["Invoice number", `INV-${number}`],
          ["Invoice date", formatDate(baseDate)],
          ["Due date", formatDate(addDays(baseDate, 30))],
          ["Reference", reference]
        ]
      ]
    },
    {
      kind: "partypair",
      headings: ["Details of receiver (billed to)", "Details of consignee (shipped to)"],
      columns: [
        [buyer.name, ...buyer.lines, `Contact: ${buyer.contact}`],
        [buyer.name, ...buyer.lines, `Tel: ${buyer.phone}`]
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
        ["Total assessable value", formatMoney(totals.subtotal)],
        ["Total sales tax", formatMoney(totals.tax)],
        ["Shipping and handling", formatMoney(shipping)],
        ["Grand total", formatMoney(grand)]
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
  ];
}

/**
 * Payment receipt with a PAID stamp and a zero balance.
 * @param {BuildContext} context - Shared document context.
 * @returns {DocumentBlock[]} Blocks for the document body.
 */
function buildReceipt(context) {
  const items = buildItems(context.vendor.id, context.seed * 5 + vendorSalt(context.vendor.id), pickCount(context.seed, 2, 4));
  const totals = computeTotals(items);

  return [
    { kind: "stamp", text: "PAID" },
    {
      kind: "parties",
      label: "Received from",
      lines: [context.buyer.name, ...context.buyer.lines, context.buyer.contact],
      meta: [
        ["Receipt #", `RCP-${context.number}`],
        ["Date", formatDate(context.baseDate)],
        // One seed is one commercial event, so the receipt settles the invoice
        // that same seed produces. It used to derive its own unrelated number,
        // which meant no receipt in the corpus could ever be matched to an
        // invoice in the corpus.
        ["Against invoice", `INV-${context.number}`],
        ["Method", pickFrom(PAYMENT_METHODS, context.seed)]
      ]
    },
    { kind: "table", columns: pricedColumns(), rows: pricedRows(items) },
    {
      // The subtotal and tax rows are not decoration. Without them the receipt
      // jumped from a line-item table straight to an amount due that silently
      // included 8.25%, so the printed lines never summed to the printed total.
      kind: "totals",
      rows: [
        ["Subtotal", formatMoney(totals.subtotal)],
        [`Sales tax (${formatRate(totals.taxRate)})`, formatMoney(totals.tax)],
        ["Amount due", formatMoney(totals.grand)],
        ["AMOUNT PAID", formatMoney(totals.grand)],
        ["Balance due", formatMoney(0)]
      ],
      emphasisIndex: 3
    },
    {
      kind: "note",
      tone: "plain",
      text: "Thank you for your payment. This receipt confirms funds received in full."
    }
  ];
}

/**
 * Quotation, explicitly marked as not a tax invoice.
 * @param {BuildContext} context - Shared document context.
 * @returns {DocumentBlock[]} Blocks for the document body.
 */
function buildQuotation(context) {
  const items = buildItems(context.vendor.id, context.seed * 7 + vendorSalt(context.vendor.id), pickCount(context.seed, 3, 6));
  const totals = computeTotals(items);

  return [
    {
      kind: "parties",
      label: "Prepared for",
      lines: [context.buyer.name, ...context.buyer.lines],
      meta: [
        ["Quote #", `QTE-${context.number}`],
        ["Date", formatDate(context.baseDate)],
        ["Valid until", formatDate(addDays(context.baseDate, 14))],
        ["Prepared by", "Sales team"]
      ]
    },
    { kind: "table", columns: pricedColumns(), rows: pricedRows(items) },
    totalsBlock(totals),
    {
      kind: "note",
      tone: "accent",
      text: "Prices are estimates valid for 14 days and subject to change. This quotation is not a tax invoice or a demand for payment. To proceed, issue a purchase order referencing the quote number above."
    }
  ];
}

/**
 * Delivery challan: goods dispatched, no prices, signature lines.
 * @param {BuildContext} context - Shared document context.
 * @returns {DocumentBlock[]} Blocks for the document body.
 */
function buildChallan(context) {
  const items = buildItems(context.vendor.id, context.seed * 11 + vendorSalt(context.vendor.id), pickCount(context.seed, 3, 6));
  const totalQty = items.reduce((sum, item) => sum + item.qty, 0);
  const poNumber = padNumber(Math.floor(createSeededRandom(context.seed + 41)() * 8_999_999) + 1_000_000, 7);

  return [
    {
      kind: "parties",
      label: "Deliver to",
      lines: [context.buyer.name, ...context.buyer.lines],
      meta: [
        ["Challan #", `DC-${context.number}`],
        ["Date", formatDate(context.baseDate)],
        ["PO ref", `PO-${poNumber}`],
        ["Vehicle no", `TX-${4100 + (context.seed % 900)}`]
      ]
    },
    {
      kind: "table",
      columns: [
        { label: "#", align: "center", width: 24 },
        { label: "Description", align: "left" },
        { label: "Qty", align: "center" },
        { label: "Unit", align: "center" },
        { label: "Remarks", align: "left" }
      ],
      // The remarks column used to read "Goods only" on every row, which is a
      // column of one repeated constant. A lot number plus the occasional
      // handling note gives it something an extraction pipeline can actually be
      // asked to read.
      rows: items.map((item, index) => [
        String(index + 1),
        item.desc,
        String(item.qty),
        item.unit,
        `Lot ${lotCode(context.seed, index)}${dispatchNote(context.seed, index)}`
      ])
    },
    {
      kind: "chips",
      items: [
        // Packages are how the goods are crated, not how many rows the table
        // has. Those were the same number on every challan ever generated.
        ["Total packages", String(packageCount(items, context.seed))],
        ["Total qty", String(totalQty)]
      ]
    },
    {
      kind: "note",
      tone: "accent",
      text: "The goods described above are dispatched for delivery. This document is not a sale invoice and no payment is due against it. Any value shown is for transport and insurance purposes only."
    },
    { kind: "signatures", labels: ["Dispatched by", "Received by (sign and date)"] }
  ];
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
 * @returns {{ blocks: DocumentBlock[], title: string, variantId: string }} Body blocks, title, variant.
 */
function buildAdjustmentNote(context) {
  const isCredit = context.seed % 2 === 0;
  const title = isCredit ? "Credit note" : "Debit note";
  const variantId = isCredit ? "creditnote" : "debitnote";
  const items = buildItems(context.vendor.id, context.seed * 13 + vendorSalt(context.vendor.id), pickCount(context.seed, 1, 3));
  const totals = computeTotals(items);
  const reasons = isCredit ? CREDIT_REASONS : DEBIT_REASONS;

  return {
    title,
    variantId,
    blocks: [
      {
        kind: "parties",
        label: "Issued to",
        lines: [context.buyer.name, ...context.buyer.lines],
        meta: [
          [`${title} #`, `${isCredit ? "CN" : "DN"}-${context.number}`],
          ["Date", formatDate(context.baseDate)],
          ["Against invoice", `INV-${context.number}`],
          ["Reason", pickFrom(reasons, context.seed)]
        ]
      },
      { kind: "table", columns: pricedColumns(), rows: pricedRows(items) },
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
 * Statement of account: a running ledger of invoices and payments.
 * @param {BuildContext} context - Shared document context.
 * @returns {DocumentBlock[]} Blocks for the document body.
 */
function buildStatement(context) {
  const random = createSeededRandom(context.seed * 17 + vendorSalt(context.vendor.id));

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
  const rows = [
    [formatDate(periodStart), "", "Balance brought forward", "", "", formatMoney(balance)]
  ];

  for (let index = 0; index < 6; index += 1) {
    const cursor = addDays(periodStart, offsets[index]);
    const amount = roundCents(60 + random() * 1800);

    // A payment is only drawn when there is something outstanding, and it is
    // capped at the outstanding amount.
    if (random() > 0.45 || balance <= 0) {
      balance = roundCents(balance + amount);
      rows.push([
        formatDate(cursor),
        `INV-${padNumber(1000 + index * 11 + context.seed + vendorSalt(context.vendor.id))}`,
        "Invoice",
        formatMoney(amount),
        "",
        formatMoney(balance)
      ]);
    } else {
      const paid = Math.min(amount, balance);
      balance = roundCents(balance - paid);
      rows.push([
        formatDate(cursor),
        `PMT-${padNumber(500 + index * 7 + context.seed + vendorSalt(context.vendor.id))}`,
        "Payment received",
        "",
        formatMoney(paid),
        formatMoney(balance)
      ]);
    }
  }

  const lastMovement = addDays(periodStart, offsets[offsets.length - 1]);

  return [
    {
      kind: "parties",
      label: "Account",
      lines: [context.buyer.name, ...context.buyer.lines],
      meta: [
        ["Statement #", `STM-${context.number}`],
        // The printed period describes the rows underneath it. The old label was
        // `Q${1 + seed % 4}`, a quarter drawn from the seed and unrelated to
        // both the transactions and the generated date, so a Q4 heading routinely
        // sat on a ledger of Q2 rows.
        ["Period", `${formatDate(periodStart)} - ${formatDate(lastMovement)}`],
        ["Generated", formatDate(context.baseDate)]
      ]
    },
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
      rows
    },
    { kind: "banner", label: "Balance due", value: formatMoney(balance) },
    {
      kind: "note",
      tone: "plain",
      text: `Summary of account activity for the period shown. Please remit any outstanding balance. Contact ${context.vendor.email} with questions.`
    }
  ];
}

const SUBTITLES = /** @type {Record<string, string>} */ ({
  quotation: "THIS IS NOT A TAX INVOICE",
  receipt: "PAYMENT CONFIRMED",
  challan: "GOODS DISPATCH NOTE",
  creditnote: "ADJUSTMENT DOCUMENT",
  statement: "STATEMENT OF ACCOUNT"
});

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
  const baseDate = addDays(today, -Math.floor(random() * 180));
  // A document number comes out of the issuing vendor's own series, so the
  // vendor salt goes in here. The buyer and the base date above stay purely
  // seed-derived, which is what lets the same seed be compared across vendors.
  const number = padNumber(
    100_000 + ((Math.floor(random() * 899_999) + vendorSalt(vendor.id)) % 899_999),
    6
  );

  /** @type {BuildContext} */
  const context = { baseDate, buyer: buildBuyer(seed), number, random, seed, vendor };

  let title = docType.label;
  let variantId = docType.id;
  /** @type {DocumentBlock[]} */
  let blocks;

  if (dense) {
    title = "Tax invoice";
    blocks = buildDenseInvoice(context);
  } else if (docType.id === "invoice") {
    blocks = buildInvoice(context);
  } else if (docType.id === "receipt") {
    blocks = buildReceipt(context);
  } else if (docType.id === "quotation") {
    blocks = buildQuotation(context);
  } else if (docType.id === "challan") {
    blocks = buildChallan(context);
  } else if (docType.id === "creditnote") {
    const note = buildAdjustmentNote(context);
    title = note.title;
    variantId = note.variantId;
    blocks = note.blocks;
  } else {
    title = "Statement";
    blocks = buildStatement(context);
  }

  return {
    blocks,
    dense,
    docTypeId: docType.id,
    docTypeLabel: docType.label,
    docVariantId: variantId,
    filenameBase: `${vendor.id}_${variantId}${dense ? "_dense" : ""}_${seed}`,
    footer: `${vendor.name} - ${vendor.email} - ${vendor.tagline}. ${SAMPLE_FOOTNOTE}`,
    seed,
    style: dense ? "dense" : "clean",
    subtitle: SUBTITLES[docType.id] ?? "",
    title,
    vendor
  };
}
