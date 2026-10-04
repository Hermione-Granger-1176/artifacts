# Decisions

These decisions explain the document model, annotation schema, rendering, and export behavior of the Vendor document generator.

## One model for both renderers

The original artifact maintained separate layouts for the HTML preview and jsPDF export. Those implementations had diverged. `buildDocument` now returns typed blocks that both renderers consume, so a new document type needs one builder.

Builders also return structured `facts`. `annotations.js` formats those facts for the sidecar instead of reconstructing them from display strings. The renderer marks each value with `data-field`, and `annotate-boxes.js` measures the marked nodes without knowledge of individual layouts.

## Explicit absent fields

An extractor cannot recover a value that the page does not print. Builders therefore record facts only for visible fields. A clean invoice omits `buyerPhone`, and a challan records `itemsPriced: false` even though its item builder computes prices.

The sidecar still includes every schema key. An absent value is `null`, which distinguishes an unprinted field from a missing schema entry.

## Normalized boxes with one region per node

The preview scales the page with CSS, and raster capture uses a 2x scale. Box coordinates divide the element rectangle by the page rectangle, so both scale factors cancel. Consumers multiply normalized coordinates by their output image dimensions.

Repeated fields and multiline addresses produce separate regions. Combining them would include gaps that contain no text. The vendor logo follows the same rule when its name spans multiple nodes.

## Visible label controls

Labeled output is the app's main purpose. Its controls remain visible in the Output panel instead of being hidden behind an advanced-settings disclosure.

## Toolbar, stage, and Output panel

The earlier layout split export choices across several cards and had two primary buttons. The current layout groups controls by their effect:

- The toolbar selects the vendor, document type, invoice layout, and seed. **New document** generates a new seed.
- The stage shows the fitted page, its caption, and controls for fit and full-size preview.
- The Output panel selects scope and output settings. Its scope switch and primary button remain visible while the middle scrolls.

The vendor dropdown names each vendor and shows its accent swatch. Document-type pills use the `short` labels in `DOCUMENT_TYPES`, with full names as tooltips. Below 700px, `#vdDocTypeSelect` replaces the pills. Both controls use `setDocType` and share state.

Below about 1000px, the toolbar, page, and output stack vertically, and the Output panel stops sticking. The app widens its shell and header to 1232px to accommodate the desktop layout.

## Label levels and batch scope

`LABEL_LEVELS` maps four choices to the former annotation switches:

| Level    | Ground truth | Field boxes | Word boxes |
| -------- | ------------ | ----------- | ---------- |
| None     | off          | off         | off        |
| JSON     | on           | off         | off        |
| + Fields | on           | on          | off        |
| + Words  | on           | on          | on         |

Each level includes the previous level. Boxes therefore always include labels, and word boxes always include field boxes. Annotation, batch export, and size estimation all read the same mapping.

A JSON batch always contains labels. Selecting JSON moves the level away from **None** and disables that choice until the format changes. **+ Fields** adds boxes to a JSON batch.

`INCLUDE_SCOPES` maps **This combo**, **All types**, **All vendors**, and **Everything** to the batch's vendor and type selections.

## One primary export button

The Format control selects PDF, PNG, or both. Batch mode also supports JSON. **Download** exports the current page, and **Generate ZIP** exports a batch. A page export writes its selected formats and one sidecar.

The **JSON only** action remains in the Labels header for single-page mode. Pair mode appears only for a degraded scan whose format includes PNG. The PDF type appears only when the format includes PDF. `syncOutput` derives all visible choices and button labels from state.

## Fitted preview and full-size dialog

An A4 page at 96dpi is 794x1123px. The preview scales to fit both width and height, so it needs no internal scrollbar. The frame height uses `clamp(380px, 100vh - 300px, 1123px)`. The 300px allowance covers the header, introduction, toolbar, and caption.

The wrapper uses the scaled page dimensions, while the page scales from its top-left corner. Scaling the wrapper itself would leave the full page dimensions in the layout and overflow the frame.

Full-size mode moves the live page into a `<dialog>`. It does not clone the page, so rendering and exports continue to use the same element. Raster capture temporarily sets zoom to 1 to preserve the 794px layout width.

## Vendor colors and the paper palette

App controls use shared design tokens. Vendor accents in `vendors.js` are document content and remain distinct literal colors. Mapping them to the app palette would remove the visual variation that the sample dataset needs. CSSOM custom properties apply those values without color literals in app stylesheets.

The shared `--color-document-*` tokens have no dark-theme override. Exported documents retain their paper palette in both themes, so the preview reflects the export.

## Classes and CSSOM under CSP

The page's `style-src 'self'` policy blocks inline style attributes. `paper-render.js` uses classes, while `element.style.setProperty` applies runtime vendor values through CSSOM. Scripts, styles, and export libraries are local files.

## Types for vendored libraries

`config/types/pdf-vendor.d.ts` declares the library methods the app calls. Installing four export packages only for their bundled types would add dependencies that runtime exports do not need. Extend the declarations when the app uses more methods, rather than substituting `any`.

## Statement balances

A statement starts with an opening balance. Each payment is capped at the outstanding balance. Without an opening balance, a first-row payment could make the ledger negative.

The regression test walks the printed rows without a clamp. Clamping the expected final balance to zero had hidden negative rows in the earlier test.

## Fixed sales-tax assumption

The generator uses a flat 8.25% rate for synthetic examples. It represents no particular jurisdiction, and the app states that limitation. Real jurisdiction rates would add data and validation work unrelated to the document-extraction examples.

## Fictional contact details

Vendor phone numbers use the fictional 555-01xx range, and email domains end in `.example`. Tests enforce both. Every document has a sample-data footer so generated pages do not identify a real business or claim to be valid tax records.

## Invoice-only dense layout

Only invoices support the second layout. For other document types, the control remains visible but disabled so the app does not silently ignore the selected option.

## Geometry in degradation output

Skew, rotation, and keystone change text positions. Grain, blur, and JPEG encoding do not. `planDegradation` returns the projective transform before raster rendering, and the annotation path applies it before writing boxes.

Each region retains an axis-aligned `box` for existing consumers and adds a `quad` with the transformed corners. The browser test measures dark pixels inside transformed and original boxes to detect incorrect geometry.

## Separate degradation planning and rendering

`planDegradation` uses only a seed and page size. `degradeCanvas` applies the plan to a canvas. JSON-only batches can therefore transform annotations without rasterizing pages.

The transform uses normalized page coordinates. One plan serves both the 794x1123 layout and the 1588x2246 capture. The pixel matrix is derived from the actual bitmap dimensions at draw time.

## Projective keystone rendering

A projective tilt narrows the far edge and shortens the far half of a page. A horizontal squeeze reproduces only the first effect.

Canvas 2D cannot apply a projective transform in one call. The renderer approximates it with four-pixel affine strips, while annotations use the exact projective matrix. Visual approximation quality is reviewed manually.

## Fixed random draw order

The seeded stream draws rotation, skew, banding, and light-position values before applying effects. Disabling grain therefore does not change rotation. This makes runs that differ in one setting comparable.

Effect magnitudes vary by up to a quarter around the preset value, with randomized direction. Samples vary within a preset instead of repeating one fixed effect.

## JPEG encoding for lossy presets

Lossy output uses the canvas's JPEG encoder and a `.jpg` extension. Re-encoding that result as PNG would add an asynchronous image round trip without restoring the lost detail.

## Separate scan preview

The live DOM provides annotation measurements. **Preview scan** captures and degrades that page, then shows the resulting image in the full-size dialog. Closing the dialog removes the scan image and returns the live page to its frame.

## Presets with optional fine-tuning

The common choices are presets. Nine custom sliders remain under **Fine-tune**. `app.js` builds them from `DEGRADE_KNOBS`, so settings and their controls have one definition. Moving a slider changes the preset to **custom**, which keeps the sidecar description accurate.

## Partial batches

**Stop and keep what is done** ends generation between documents. The active document completes before the archive is written, so partial files do not enter the ZIP.

A partial archive retains normal folders, labels, and manifest entries. Its `README.txt` records both completed and planned counts, and its filename includes `_partial`. Stopping before any document finishes produces no download.

## Yielding during synchronous exports

Text PDF and JSON exports can complete without an asynchronous operation. A loop that never returns to the event loop prevents the stop button from receiving clicks.

The batch loop yields after 50ms of work. Yielding once per document would add task-queue overhead to every page. Raster exports already yield inside `html2canvas`. [Verification](verification.md) records coverage of export and stop behavior.
