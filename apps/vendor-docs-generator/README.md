# Vendor Document Generator

A workbench for producing **labelled** synthetic business paperwork: invoices, receipts, quotations, delivery challans, credit and debit notes, and account statements, from six fictional vendors that each look like a different company. Built for people measuring a document-AI extractor who would rather not feed a model somebody's real invoices, and would rather not hand-label a test set either.

Rendering plausible paperwork is the easy half. Every page here also emits a JSON sidecar naming what each printed value is, generated from the same numbers the page was printed from, so the labels cannot drift out of agreement with the pixels. Download 500 documents and you have 500 scored examples, not 500 things to annotate.

Every document is a pure function of one integer seed, so any sample can be reproduced exactly from its filename.

## Highlights

- Six fictional vendors, each with its own accent colour, typeface, logo treatment, letterhead layout, and product catalogue, so generated pages do not all look like the same template
- Six document types plus a second, much denser tax-invoice layout for invoices, giving 42 vendor/type/layout combinations before the seed varies anything
- Seeded generation: changing the vendor, type, or layout re-renders against the same seed so treatments can be compared side by side, and only **Generate new document** rolls a fresh one
- Two-column workbench: a sticky control rail beside an A4 stage with fit-width and actual-size preview
- Ground truth per page: a frozen 35-key field schema plus 11 per-line keys, each carrying both the printed `text` and the normalised `value` (ISO dates, numeric money, fractional rates). A key is `null` exactly when the page prints nothing for it, so an extractor is never scored against a field that is not there
- Optional bounding boxes in normalised 0..1 page coordinates, at field level or word level, so the same run can train a layout model
- Arithmetic that holds: line amounts sum to the subtotal, and subtotal plus tax plus shipping equals the grand total, on every document the generator can produce
- Three export paths: a real text-layer PDF (searchable and selectable), a rasterised PDF that looks scanned, and a PNG. A fourth, JSON only, skips both renderers and is the fast path for iterating on an evaluation script
- Batch export to a single ZIP foldered as `vendor/type/`, optionally across all vendors and all types at once, with live progress, a `manifest.jsonl` for streaming, and a `README.txt` recording the schema and the exact settings the run used
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
│   ├── annotate-boxes.js
│   ├── annotations.js
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

## Ground truth

Each sidecar looks like this, trimmed:

```json
{
  "schema_version": "1.0",
  "seed": 414956,
  "vendor_id": "ironwood",
  "doc_type": "invoice",
  "style": "clean",
  "fields": {
    "document_number": { "text": "INV-403118", "value": "INV-403118" },
    "document_date":   { "text": "Mar 14, 2026", "value": "2026-03-14" },
    "po_number":       null,
    "grand_total":     { "text": "$4,558.14", "value": 4558.14 }
  },
  "line_items": [
    { "index": 0, "description": { "text": "Rebar #4 (20ft)", "value": "Rebar #4 (20ft)" }, "amount": { "text": "$382.80", "value": 382.8 } }
  ],
  "boxes": { "page": { "width": 794, "height": 1123, "unit": "normalised" }, "regions": [] },
  "boxes_apply_to": ["png", "pdf_raster"]
}
```

One caveat is stated on every payload rather than left to be discovered. Boxes are measured on the rendered HTML page, so they describe the PNG and the rasterised PDF. They do not describe the text-layer PDF, which jsPDF lays out independently in its own coordinate system.

## Docs

See `docs/` for architecture, verification, and implementation decisions.
