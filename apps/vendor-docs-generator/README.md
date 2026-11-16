# Vendor document generator

This app generates labeled synthetic business documents for testing document-AI extractors. Six fictional vendors provide distinct layouts for invoices, receipts, quotations, delivery challans, credit and debit notes, and account statements.

Each document can come with a JSON sidecar that labels its printed values. The page and sidecar come from one document model, so a batch needs no manual annotation.

One integer seed drives the random choices in each document. Document dates are relative to the day of generation. The filename records the seed. See [Known limitations](#known-limitations) for what exact replay needs.

## Features

- Six vendors and six document types. Invoices also have a dense tax layout, which gives 42 vendor, type, and layout combinations.
- Seeded generation. Changing the vendor, type, or layout keeps the seed. **New document** picks a new seed.
- An A4 preview with fitted and full-size modes.
- JSON field labels with printed text and normalized values. Unprinted fields are `null`.
- Optional field and word boxes in normalized page coordinates.
- Five scan presets and nine fine-tune sliders. Geometric effects also transform the exported boxes.
- Clean and degraded image pairs from one capture.
- Text-layer PDF, rasterized PDF, and PNG exports. Lossy raster presets write JPEG files.
- ZIP batches of 1 to 50 copies per vendor and type combination, with 10 by default. A batch covers the current combination, all types, all vendors, or everything.
- Partial archives when a batch stops. The filename ends in `_partial.zip`.
- Fictional contact details and a sample-data footer on every document.

## Use the app

- Pick a vendor and a document type in the toolbar. For invoices, pick a layout. Click **New document** for a new seed.
- Click **Preview scan** to see the page with the current scan preset applied.
- Pick a scan preset, or open **Fine-tune** to adjust the nine sliders. Moving a slider switches the preset to custom.
- In the Output panel, choose the labels, the format (PDF, PNG, or both), and the scope. Click **Download** to export the current page, or **Generate ZIP** to export a batch.
- Click **Stop and keep what is done** to end a batch between documents. The finished documents go into a `_partial.zip` archive.

## Made with

- Claude
- jsPDF and jspdf-autotable (vendored)
- html2canvas (vendored)
- JSZip (vendored)

All four libraries are vendored under `js/vendor/` and pinned by SHA-256 in `config/vendored_assets.json`.

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

`boxes_apply_to` lists the outputs that use the box coordinates: PNG and rasterized PDF. The text-layer PDF has its own jsPDF layout, so the boxes do not describe it. `boxes` and `boxes_apply_to` are `null` when the Labels level is JSON. In `boxes.page`, `width` and `height` are the layout size in CSS pixels. Region coordinates are fractions of that page.

## Scan degradation

`degradation` is `null` on a clean run. Otherwise it names the preset, the seed, every resolved setting, and the projective transform. The transform is a 3x3 matrix over the same normalized coordinates as the boxes.

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

A lossy preset writes a `.jpg` file, because the output uses JPEG encoding.

## Known limitations

The generator has three known limitations:

- **Batch memory.** JSZip holds each exported file in memory until it writes the archive. Large raster batches can exceed the tab's memory. The size estimate reports expected output size, but the app sets no memory limit.
- **Vendor and document compatibility.** Every vendor can issue every document type. A delivery challan can therefore list service items. The arithmetic and layout stay valid, but some combinations are implausible.
- **Reference date.** Dates are relative to the generation day. Exact replay needs the seed, the degradation settings, and the original reference date. The sidecar's `document_date` and the seeded offset can recover that date, but the manifest does not record it.

## Documentation

The app documentation covers [architecture](docs/architecture.md), [verification](docs/verification.md), and [implementation decisions](docs/decisions.md).
