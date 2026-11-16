# Architecture

The Vendor document generator builds one model from the selected vendor, document type, layout, seed, and reference date. The HTML renderer, the PDF renderer, and the annotation builder all read that model.

## Module flow

1. `document-model.js` uses `vendors.js`, `random.js`, and `format.js` to build document blocks and structured facts.
2. `paper-render.js` renders the blocks into the DOM. `pdf-render.js` renders them through jsPDF.
3. `annotations.js` converts facts into sidecar fields. `annotate-boxes.js` measures the DOM when boxes are requested.
4. `exporters.js` creates page downloads or ZIP batches. `degrade.js` supplies scan effects and the coordinate transforms for raster output and annotations.

## Document model

`buildDocument` returns `title`, `subtitle`, `footer`, typed `blocks`, and `facts`. Block kinds include `parties`, `table`, `totals`, `stamp`, `keygrid`, `partypair`, `words`, `note`, `callout`, `chips`, `banner`, `signatures`, and `signoff`. Each renderer dispatches on `block.kind`.

The blocks contain display strings. `facts` keeps the structured values before formatting: dates as `Date`, money as numbers, and line items as records. Both renderers and the sidecar read the same values.

## Sidecar fields

`annotations.js` emits fields in `FIELD_KEYS` order. Every schema key is present. A field that the page does not print is `null`, including the prices on a challan even when the item builder has computed them.

Present fields carry the printed `text` and a normalized `value`. Dates use ISO values, money uses numbers, and rates use fractions.

## Annotation boxes

`paper-render.js` marks value nodes with `data-field`. `annotate-boxes.js` reads their rectangles through `getBoundingClientRect` and normalizes them against the page rectangle. Preview scaling and 2x capture scaling change both rectangles by the same factor, so dividing by the page rectangle cancels that factor.

Repeated fields and multiline values produce separate regions in document order. The `boxes_apply_to` field identifies the PNG and rasterized PDF outputs. DOM measurements do not describe the text-layer PDF, which jsPDF lays out independently in A4 points.

## Scan degradation

`planDegradation` computes the settings and the geometry from a seed and a page size. `degradeCanvas` applies the plan to a raster. The random draw order is fixed.

Skew, rotation, and keystone produce a projective transform. `transformBoxes` applies that transform to regions and word boxes. Each region gets a `quad` of transformed corners and a `box` containing their axis-aligned bounds.

The matrix uses normalized page coordinates. `toPixelMatrix` converts it to the actual bitmap size. JSON-only exports can apply the annotation geometry without rasterizing the page.

Canvas 2D approximates keystone with four-pixel affine strips. Annotations keep the exact projective matrix. Lossy presets use JPEG encoding and write `.jpg` files.

## Determinism and reference dates

The seed and the reference date determine the document model. `buildDocument` defaults `today` to the generation day, so exact replay needs the original date. The sidecar's `document_date` and the seeded offset can recover that date, but the manifest does not record it.

`random.js` provides a Lehmer generator. `Math.random` runs only in `rollSeed`, which picks a new seed, and in `planBatch`, which picks batch seeds and mixes dense invoices into about 40% of invoice samples. `format.js` uses no locale-dependent formatting.

The order of the random draws is part of replay behavior. Changing it changes the generated documents. For example, the day offset is drawn before the document number.

## CSP and DOM rendering

The page uses a self-only CSP without `unsafe-inline`. The HTML renderer creates nodes with `createElement` and writes values with `textContent`. It emits classes instead of inline style attributes.

Vendor branding reaches the page through CSSOM custom properties such as `--vd-accent`, `--vd-accent-soft`, `--vd-ink`, and `--vd-font`. Scripts and styles are local files, and the export libraries are vendored under `js/vendor/`.

## Color ownership

App controls in `css/app.css` use shared tokens. Printed pages use the theme-independent `--color-document-*` tokens from `css/src/01-tokens.css` at the repo root, so dark mode does not change the exported paper colors.

Vendor accents in `vendors.js` are document content. They reach the page through CSSOM and do not map to the app palette.

## State and render passes

`app.js` stores the vendor, document type, invoice layout, seed, scan preset, overrides, and output choices. `draw` rebuilds the page and its caption. `syncOutput` derives the visible output controls, the label notes, pair availability, size estimates, and the primary button label.

`LABEL_LEVELS` maps the label choices to ground truth, field boxes, and word boxes. `INCLUDE_SCOPES` maps the batch scope to vendor and type selections. `DOCUMENT_TYPES` and `DEGRADE_PRESETS` provide control labels, and `DEGRADE_KNOBS` defines the nine fine-tune sliders. `wireSegment` wraps `initSegmented`, so programmatic changes also update the selection highlight.

`degradationFor` plans the scan for one document, or returns `null` for a clean run. `annotate` measures the boxes on the live paper, moves them through that plan, and builds the sidecar. Both the single-page export and the batch loop call them.

## Layout and stability

The layout has a toolbar, a fitted page stage, and a sticky Output panel. The panel's scope switch and footer stay visible while its middle scrolls. Its vendor swatch uses the same `--vd-accent` as the printed page.

Below about 1000px the three regions stack, and the panel stops sticking. Below 700px the document-type pills give way to `#vdDocTypeSelect`.

Controls that appear and disappear keep their space:

- The estimate, the progress meter, and the status line each keep their row. The meter and the stop button use `visibility: hidden` while idle, and the status line is empty.
- The PDF type control and the pair option are dimmed, not hidden, when they do not apply.
- The seed chip holds the width of the widest seed.
- The caption reserves two lines below 600px, three below 380px, and four below 340px, so a longer scan name does not move the page.

## Export paths

`exporters.js` reads the UMD library globals through injected accessors. Unavailable libraries produce a readable error.

Text PDFs render directly from the model. PNG and rasterized PDFs use `html2canvas` one at a time, because they share one paper element. Raster capture sets the zoom to 1 temporarily, including when the page is in the full-size dialog.

A labeled batch writes one sidecar per page, a `manifest.jsonl` with one compact sidecar per line, and a `README.txt` with the schema and settings. A batch with Labels set to None writes none of the three. JSON-only batches skip PDF and raster generation. The DOM stage still advances for progress and requested box measurements.

Pair mode applies to PNG output. `renderRaster` returns both the degraded image and its clean capture, so a pair needs one capture. JSZip keeps batch files in memory until it creates the archive.

The batch loop yields during synchronous formats, so progress and stop controls keep working. A stop completes the active document, writes the completed files, and records the partial counts. [Decisions](decisions.md) explains these trade-offs. [Verification](verification.md) describes test coverage and its limits.
