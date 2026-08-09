# Vendor Document Generator

A workbench for producing **labelled** synthetic business paperwork: invoices, receipts, quotations, delivery challans, credit and debit notes, and account statements, from six fictional vendors that each look like a different company. Built for people measuring a document-AI extractor who would rather not feed a model somebody's real invoices, and would rather not hand-label a test set either.

Rendering plausible paperwork is the easy half. Every page here also emits a JSON sidecar naming what each printed value is, generated from the same numbers the page was printed from, so the labels cannot drift out of agreement with the pixels. Download 500 documents and you have 500 scored examples, not 500 things to annotate.

Every random choice is driven by one integer seed, while document dates are relative to the day of generation. The filename records the seed so samples remain identifiable. Exact replay in code also needs the original reference date, which is recoverable from the sidecar's `document_date` and the seed-derived date offsets. Phase 4 is the natural place to record it directly when locale date controls are added.

## Highlights

- Six fictional vendors, each with its own accent colour, typeface, logo treatment, letterhead layout, and product catalogue, so generated pages do not all look like the same template
- Six document types plus a second, much denser tax-invoice layout for invoices, giving 42 vendor/type/layout combinations before the seed varies anything
- Seeded generation: changing the vendor, type, or layout re-renders against the same seed so treatments can be compared side by side, and only **Generate new document** rolls a fresh one
- Two-column workbench: a sticky control rail beside an A4 stage with fit-width and actual-size preview
- Ground truth per page: a frozen 35-key field schema plus 11 per-line keys, each carrying both the printed `text` and the normalised `value` (ISO dates, numeric money, fractional rates). A key is `null` exactly when the page prints nothing for it, so an extractor is never scored against a field that is not there
- Optional bounding boxes in normalised 0..1 page coordinates, at field level or word level, so the same run can train a layout model
- Five scan-quality presets, from a clean render to a phone photo, with nine sliders behind them. Degradation is driven by the document seed, so a seed plus a preset reproduce the same wear, and geometry is reported as a transform that the boxes are run through before they are written
- Pair mode writes a degraded PNG output and its clean original from one seed, which is what makes "how much accuracy do I lose to scan quality" a question you can plot
- Arithmetic that holds: line amounts sum to the subtotal, and subtotal plus tax plus shipping equals the grand total, on every document the generator can produce
- Three export paths: a real text-layer PDF (searchable and selectable), a rasterised PDF that looks scanned, and a PNG. A fourth, JSON only, skips PDF and raster generation while the stage still advances through the batch as visible progress
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
│   ├── degrade.js
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
  "schema_version": "1.1",
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
  "boxes_apply_to": ["png", "pdf_raster"],
  "degradation": null
}
```

One caveat is stated on every payload rather than left to be discovered. Boxes are measured on the rendered HTML page, so they describe the PNG and the rasterised PDF. They do not describe the text-layer PDF, which jsPDF lays out independently in its own coordinate system.

## Scan degradation

`degradation` is `null` on a clean run. Otherwise it names the preset, the seed, every resolved setting, and the projective transform applied, as a 3x3 matrix over the same normalised coordinates the boxes use.

Skew, rotation, and keystone move the ink, so **the boxes have already been run through that transform**: they describe the degraded image, not the clean render it started from. Each region also gains a `quad` holding the four corners the ink actually landed on, while `box` stays the axis-aligned hull of that quad, so an evaluation script written against a clean run keeps working unchanged.

```json
"degradation": {
  "preset": "phone",
  "seed": 414956,
  "settings": { "rotation": -2.11, "keystone": 0.09, "jpeg": 0.7, "...": "every resolved value" },
  "transform": [[0.998, -0.037, 0.019], [0.026, 0.998, -0.013], [0, -0.081, 1.041]],
  "applies_to": ["png", "pdf_raster"]
}
```

A lossy preset writes a JPEG rather than a PNG, because that is the compression a real scanner applied and calling the result a PNG would be a lie about the file.

## Known limitations

Three things are deliberately unresolved. Each needs a product decision rather than a fix, so they are recorded here instead of being quietly worked around.

**The batch loop is synchronous.** JSON and text-PDF batches run their whole document loop without yielding, so at the 1,800-document maximum the browser can sit unresponsive even though the stage and the progress meter are being updated. The meter reports work that has already happened rather than work in flight. Fixing it means choosing a cooperative yielding policy (how often to yield, and against what budget) and having a performance test that would notice if it regressed. Yielding every document would be the safe default and the slowest one.

**Every document type is available to every vendor.** The type list is not filtered by what a vendor plausibly issues, so a delivery challan can carry service rows: Nimbus dispatching "Priority support SLA" against a package count. The arithmetic is right and the layout is right; the pairing is not. Resolving it needs either per-type catalogues or a vendor-to-type compatibility table, which is a content decision about how much of the cross product is worth keeping.

**The reference date is recoverable but not recorded.** Document dates are relative to the day of generation, so exact replay needs the seed, the degradation settings, and the original reference date. That date can be reconstructed from the sidecar's `document_date` plus the seed-derived day offset, but nothing writes it down. Recording it in `manifest.jsonl` and `README.txt`, or exposing it as a replay control, belongs with the locale and date work in phase 4 rather than as a standalone schema addition.

## Docs

See `docs/` for architecture, verification, and implementation decisions.
