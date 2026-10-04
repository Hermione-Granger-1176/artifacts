# Vendor document generator

This app produces labeled synthetic business documents for evaluating document-AI extractors. Six fictional vendors provide distinct layouts for invoices, receipts, quotations, delivery challans, credit and debit notes, and account statements.

Each page can include a JSON sidecar with labels for the printed values. The page and sidecar use the same document model, so a batch does not require manual field annotation.

Every random choice is driven by one integer seed, while document dates are relative to the day of generation. The filename records the seed so samples remain identifiable. Exact replay in code also needs the original reference date, which is recoverable from the sidecar's `document_date` and the seed-derived date offsets.

## Features

The generator supports these outputs and controls:

- Six vendors and six document types. Invoices also have a dense tax layout, giving 42 vendor, type, and layout combinations.
- Seeded generation. Vendor, type, and layout changes retain the seed. **New document** selects a fresh seed.
- An A4 preview with fitted and full-size modes. Below about 1000px, the toolbar, page, and Output panel stack vertically.
- JSON field labels with printed text and normalized values. Unprinted fields are `null`.
- Optional field and word boxes in normalized page coordinates.
- Five scan presets and nine fine-tune sliders. Geometric effects also transform exported boxes.
- Clean and degraded image pairs from one capture.
- Text-layer PDF, rasterized PDF, and PNG exports. Lossy raster presets write JPEG files.
- ZIP batches across selected vendors and types, with optional sidecars, `manifest.jsonl`, and `README.txt`. JSON-only mode skips PDF and raster generation. It still renders each DOM preview for progress and requested box measurements.
- Partial archives when a batch stops. The README records completed and planned counts.
- Fictional contact details and a sample-data footer on every document.

[Architecture](docs/architecture.md) describes control mappings, rendering, and export paths.

## Made with

- Claude
- jsPDF 4.2.1 and jspdf-autotable 5.0.8 (vendored)
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

A shortened sidecar example shows the schema:

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

`boxes_apply_to` identifies the outputs that use the box coordinates. Boxes describe the rendered HTML page used for PNG and rasterized PDF exports. The text-layer PDF has an independent jsPDF layout.

## Scan degradation

`degradation` is `null` on a clean run. Otherwise it names the preset, the seed, every resolved setting, and the projective transform applied, as a 3x3 matrix over the same normalized coordinates the boxes use.

Skew, rotation, and keystone change the geometry. The exported boxes already include that transform. Each region has a `quad` with the four transformed corners and a `box` with their axis-aligned bounding rectangle.

```json
"degradation": {
  "preset": "phone",
  "seed": 414956,
  "settings": { "rotation": -2.11, "keystone": 0.09, "jpeg": 0.7, "...": "every resolved value" },
  "transform": [[0.998, -0.037, 0.019], [0.026, 0.998, -0.013], [0, -0.081, 1.041]],
  "applies_to": ["png", "pdf_raster"]
}
```

A lossy preset writes a `.jpg` file because the output uses JPEG encoding.

## Known limitations

The generator has three known limitations:

- **Batch memory.** JSZip holds each exported file in memory until it writes the archive. Large raster batches can exceed the tab's memory. The size estimate reports expected output size, but the app enforces no memory limit. Streaming output requires a different archive strategy.
- **Vendor and document compatibility.** Every vendor can issue every document type. A delivery challan can therefore contain service items. The arithmetic and layout are valid, but some combinations are implausible. Restricting them requires per-type catalogs or a compatibility table.
- **Reference date.** Dates are relative to the generation day. Exact replay requires the seed, degradation settings, and original reference date. The date can be reconstructed from `document_date` and the seeded offset, but the manifest does not record it directly.

## Documentation

The app documentation covers [architecture](docs/architecture.md), [verification](docs/verification.md), and [implementation decisions](docs/decisions.md).
