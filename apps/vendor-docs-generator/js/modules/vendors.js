/**
 * Fictional vendor identities, their product catalogues, and the document
 * types the generator can produce.
 *
 * Every business, address, phone number, email, and tax identifier below is
 * invented for sample data. The phone numbers use the 555 range reserved for
 * fiction and the EINs are not issued numbers.
 *
 * The per-vendor colours and typefaces are deliberately raw literals rather
 * than shared design tokens: they are the *content* of a generated document
 * (six businesses that should look like six unrelated brands), not app chrome.
 * The app's own surfaces are token-derived in css/app.css; these values are
 * pushed onto the paper element as custom properties at render time.
 *
 * Each `accent` still has to clear 4.5:1 against white, because table headers
 * and stamps print white text on it. `vendors.test.js` enforces that.
 *
 * @module vendors
 */

/**
 * @typedef {{
 *   accent: string,
 *   accentSoft: string,
 *   addr: string,
 *   companyReg: string,
 *   email: string,
 *   font: string,
 *   id: string,
 *   ink: string,
 *   layout: "left" | "center" | "right",
 *   logoStyle: "block" | "leaf" | "mono" | "stripe" | "thin" | "stamp",
 *   name: string,
 *   phone: string,
 *   tagline: string,
 *   taxId: string
 * }} Vendor
 * @typedef {{ basePrice: number, desc: string, unit: string }} CatalogEntry
 * @typedef {{ id: string, label: string }} DocumentType
 */

/** @type {readonly Vendor[]} */
export const VENDORS = [
  {
    id: "apex",
    name: "Apex Industrial Supply",
    tagline: "Industrial fasteners and tooling",
    addr: "4120 Foundry Rd, Cleveland, OH 44114",
    email: "ar@apexindustrial.example",
    phone: "+1 216 555 0142",
    accent: "#1d4ed8",
    accentSoft: "#dbeafe",
    ink: "#0f172a",
    font: "'Helvetica Neue', Arial, sans-serif",
    logoStyle: "block",
    layout: "left",
    taxId: "EIN 34-2910187",
    companyReg: "REG-OH-4482017"
  },
  {
    id: "verde",
    name: "Verde Organic Foods",
    tagline: "Wholesale natural and organic",
    addr: "88 Greenmarket Way, Portland, OR 97209",
    email: "billing@verdefoods.example",
    phone: "+1 503 555 0199",
    accent: "#15803d",
    accentSoft: "#dcfce7",
    ink: "#14532d",
    font: "Georgia, 'Times New Roman', serif",
    logoStyle: "leaf",
    layout: "center",
    taxId: "EIN 81-4452009",
    companyReg: "REG-OR-1130664"
  },
  {
    id: "nimbus",
    name: "Nimbus Cloud Services",
    tagline: "Managed IT and hosting",
    addr: "201 Market St, Suite 1500, San Francisco, CA 94105",
    email: "accounts@nimbus.example",
    phone: "+1 415 555 0177",
    accent: "#7c3aed",
    accentSoft: "#ede9fe",
    ink: "#2e1065",
    font: "'Segoe UI', system-ui, sans-serif",
    logoStyle: "mono",
    layout: "right",
    taxId: "EIN 47-3320981",
    companyReg: "REG-CA-7729845"
  },
  {
    id: "harbor",
    name: "Harbor Freight Logistics",
    tagline: "Freight forwarding and 3PL",
    addr: "700 Dockside Blvd, Long Beach, CA 90802",
    email: "invoices@harborfl.example",
    phone: "+1 562 555 0118",
    accent: "#c2410c",
    accentSoft: "#ffedd5",
    ink: "#7c2d12",
    font: "'Arial Narrow', Arial, sans-serif",
    logoStyle: "stripe",
    layout: "left",
    taxId: "EIN 26-7781230",
    companyReg: "REG-CA-2065318"
  },
  {
    id: "lumen",
    name: "Lumen Office Interiors",
    tagline: "Commercial furniture and fit-out",
    addr: "15 Designer Mile, Chicago, IL 60607",
    email: "finance@lumeninteriors.example",
    phone: "+1 312 555 0163",
    accent: "#0f766e",
    accentSoft: "#ccfbf1",
    ink: "#134e4a",
    font: "Futura, 'Trebuchet MS', sans-serif",
    logoStyle: "thin",
    layout: "center",
    taxId: "EIN 92-1108774",
    companyReg: "REG-IL-8814200"
  },
  {
    id: "ironwood",
    name: "Ironwood Construction Materials",
    tagline: "Lumber, steel and aggregates",
    addr: "3300 Quarry Rd, Austin, TX 78744",
    email: "ar@ironwoodmat.example",
    phone: "+1 512 555 0150",
    accent: "#b45309",
    accentSoft: "#fef3c7",
    ink: "#451a03",
    font: "'Courier New', Courier, monospace",
    logoStyle: "stamp",
    layout: "left",
    taxId: "EIN 55-6620410",
    companyReg: "REG-TX-3390572"
  }
];

/**
 * Line-item catalogues, one per vendor, so a document's contents match the
 * business printed at the top of it. Reached through `catalogFor` rather than
 * exported directly, so the fallback for an unknown vendor lives in one place.
 * @type {Readonly<Record<string, readonly CatalogEntry[]>>}
 */
const CATALOGS = {
  apex: [
    { desc: "Hex bolt M12x60, zinc", unit: "box", basePrice: 4.2 },
    { desc: "Socket cap screw M8", unit: "box", basePrice: 6.8 },
    { desc: "Carbide drill bit set", unit: "set", basePrice: 58 },
    { desc: 'Torque wrench 1/2"', unit: "ea", basePrice: 129 },
    { desc: "Threadlocker 250ml", unit: "ea", basePrice: 18.5 },
    { desc: "Anchor bolt kit", unit: "kit", basePrice: 42 }
  ],
  verde: [
    { desc: "Organic quinoa 25kg", unit: "sack", basePrice: 92 },
    { desc: "Cold-pressed olive oil 5L", unit: "case", basePrice: 64 },
    { desc: "Raw almonds 10kg", unit: "box", basePrice: 88 },
    { desc: "Maple syrup 4L", unit: "case", basePrice: 71 },
    { desc: "Sea salt flakes 5kg", unit: "box", basePrice: 34 },
    { desc: "Dried cranberries 8kg", unit: "box", basePrice: 56 }
  ],
  nimbus: [
    { desc: "Managed hosting (Pro tier)", unit: "mo", basePrice: 420 },
    { desc: "Daily backup retention", unit: "mo", basePrice: 75 },
    { desc: "SSL certificate (wildcard)", unit: "yr", basePrice: 150 },
    { desc: "DDoS protection", unit: "mo", basePrice: 95 },
    { desc: "Priority support SLA", unit: "mo", basePrice: 180 },
    { desc: "Additional 1TB storage", unit: "mo", basePrice: 40 }
  ],
  harbor: [
    { desc: "Ocean freight FCL 40ft", unit: "ctr", basePrice: 2850 },
    { desc: "Customs clearance", unit: "shp", basePrice: 320 },
    { desc: "Drayage and haulage", unit: "shp", basePrice: 640 },
    { desc: "Warehousing (per pallet/mo)", unit: "plt", basePrice: 28 },
    { desc: "Container inspection", unit: "ea", basePrice: 85 },
    { desc: "Document handling fee", unit: "shp", basePrice: 55 }
  ],
  lumen: [
    { desc: "Ergonomic task chair", unit: "ea", basePrice: 389 },
    { desc: "Sit-stand desk 1600mm", unit: "ea", basePrice: 640 },
    { desc: "Acoustic panel set", unit: "set", basePrice: 275 },
    { desc: "Meeting table 8-seat", unit: "ea", basePrice: 1180 },
    { desc: "Storage credenza", unit: "ea", basePrice: 520 },
    { desc: "Installation and assembly", unit: "day", basePrice: 450 }
  ],
  ironwood: [
    { desc: "Structural lumber 2x6x12", unit: "pc", basePrice: 9.4 },
    { desc: "Rebar #4 (20ft)", unit: "pc", basePrice: 12.8 },
    { desc: "Portland cement 50lb", unit: "bag", basePrice: 8.2 },
    { desc: "Crushed aggregate", unit: "ton", basePrice: 26 },
    { desc: 'Plywood sheet 3/4"', unit: "sheet", basePrice: 47 },
    { desc: "Galvanized sheet steel", unit: "sheet", basePrice: 88 }
  ]
};

/** @type {readonly DocumentType[]} */
export const DOCUMENT_TYPES = [
  { id: "invoice", label: "Invoice" },
  { id: "receipt", label: "Receipt" },
  { id: "quotation", label: "Quotation" },
  { id: "challan", label: "Delivery challan" },
  { id: "creditnote", label: "Credit or debit note" },
  { id: "statement", label: "Statement of account" }
];

/** Flat sales-tax rate used across every priced document. */
export const TAX_RATE = 0.0825;

/**
 * Look up a vendor, falling back to the first one for an unknown id.
 * @param {string} vendorId - Vendor identifier.
 * @returns {Vendor} The matching vendor record.
 */
export function findVendor(vendorId) {
  return VENDORS.find((vendor) => vendor.id === vendorId) ?? VENDORS[0];
}

/**
 * Look up a document type, falling back to the first one for an unknown id.
 * @param {string} typeId - Document type identifier.
 * @returns {DocumentType} The matching document type record.
 */
export function findDocumentType(typeId) {
  return DOCUMENT_TYPES.find((type) => type.id === typeId) ?? DOCUMENT_TYPES[0];
}

/**
 * Read a vendor's catalogue.
 * @param {string} vendorId - Vendor identifier.
 * @returns {readonly CatalogEntry[]} Catalogue entries for that vendor.
 */
export function catalogFor(vendorId) {
  return CATALOGS[vendorId] ?? CATALOGS.apex;
}
