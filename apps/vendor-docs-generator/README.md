# Vendor Document Generator

A workbench for producing synthetic business paperwork: invoices, receipts, quotations, delivery challans, credit and debit notes, and account statements, from six fictional vendors that each look like a different company. Built for people who need labelled sample pages for document-AI, OCR, and extraction work and would rather not feed a model somebody's real invoices.

Every document is a pure function of one integer seed, so any sample can be reproduced exactly from its filename.

## Highlights

- Six fictional vendors, each with its own accent colour, typeface, logo treatment, letterhead layout, and product catalogue, so generated pages do not all look like the same template
- Six document types plus a second, much denser tax-invoice layout for invoices, giving 42 vendor/type/layout combinations before the seed varies anything
- Seeded generation: changing the vendor, type, or layout re-renders against the same seed so treatments can be compared side by side, and only **Generate new document** rolls a fresh one
- Two-column workbench: a sticky control rail beside an A4 stage with fit-width and actual-size preview
- Three export paths: a real text-layer PDF (searchable and selectable), a rasterised PDF that looks scanned, and a PNG
- Batch export to a single ZIP foldered as `vendor/type/`, optionally across all vendors and all types at once, with live progress
- Every page is footered as sample data, and every name, address, phone number, and tax identifier is invented

## Made with

- Claude
- jsPDF 2.5.1 and jspdf-autotable 3.8.2 (vendored)
- html2canvas 1.4.1 (vendored)
- JSZip 3.10.1 (vendored)

All four libraries are vendored under `js/vendor/` and pinned by SHA-256 in `config/vendored_assets.json`, which keeps the page's self-only Content-Security-Policy intact.

## Structure

```text
index.html
css/app.css
js/
├── app.js
├── modules/
│   ├── document-model.js
│   ├── exporters.js
│   ├── format.js
│   ├── paper-render.js
│   ├── pdf-render.js
│   ├── random.js
│   └── vendors.js
└── vendor/
    ├── html2canvas.min.js
    ├── jspdf.plugin.autotable.min.js
    ├── jspdf.umd.min.js
    └── jszip.min.js
docs/
```

## Docs

See `docs/` for architecture, verification, and implementation decisions.
