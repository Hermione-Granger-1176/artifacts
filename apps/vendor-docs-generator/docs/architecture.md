# Architecture

The Vendor document generator builds one model from the selected vendor, document type, layout, seed, and reference date. The HTML renderer, PDF renderer, and annotation builder consume that model.

## Module flow

The modules divide the pipeline as follows:

1. `document-model.js` uses `vendors.js`, `random.js`, and `format.js` to build document blocks and structured facts.
2. `paper-render.js` renders the blocks into the DOM. `pdf-render.js` renders them through jsPDF.
3. `annotations.js` converts facts into sidecar fields. `annotate-boxes.js` measures the DOM when boxes are requested.
4. `exporters.js` creates page downloads or ZIP batches. `degrade.js` supplies scan effects and coordinate transforms for raster output and annotations.

## Document model

`buildDocument` returns `title`, `subtitle`, `footer`, typed `blocks`, and `facts`. Block kinds include `parties`, `table`, `totals`, `stamp`, `keygrid`, `partypair`, `words`, `note`, `callout`, `chips`, `banner`, `signatures`, and `signoff`. Each renderer dispatches on `block.kind`.

The blocks contain display strings. `facts` preserves structured values before formatting: dates as `Date`, money as numbers, and line items as records. Both renderers and the sidecar use the same values, which prevents independent arithmetic or field definitions from diverging.

## Sidecar fields

`annotations.js` emits fields in `FIELD_KEYS` order. Every schema key is present. Fields not printed on the page are `null`, including prices on a challan even when the item builder has computed them.

Present fields carry the printed `text` and a normalized `value`. Dates use ISO values, money uses numbers, and rates use fractions.

## Annotation boxes

`paper-render.js` marks value nodes with `data-field`. `annotate-boxes.js` reads their rectangles through `getBoundingClientRect` and normalizes them against the page rectangle. Preview scaling and 2x capture scaling change both rectangles by the same factor, so normalized coordinates remain stable.

Repeated fields and multiline values produce separate regions in document order. The `boxes_apply_to` field identifies PNG and rasterized PDF outputs. DOM measurements do not describe the text-layer PDF, which jsPDF lays out independently in A4 points.

## Scan degradation

`planDegradation` computes settings and geometry from a seed and page size. `degradeCanvas` applies the plan to a raster. Fixed random draw order keeps geometry unchanged when a non-geometric effect is disabled.

Skew, rotation, and keystone produce a projective transform. `transformBoxes` applies that transform to regions and word boxes. Each region includes a `quad` of transformed corners and a `box` containing their axis-aligned bounds.

The matrix uses normalized page coordinates. `toPixelMatrix` converts it for the actual bitmap size. JSON-only exports can apply annotation geometry without rasterization.

Canvas 2D approximates keystone with four-pixel affine strips. Annotations retain the exact projective matrix. Lossy presets use JPEG encoding and write `.jpg` files.

## Determinism and reference dates

The seed and reference date determine the document model. `buildDocument` defaults `today` to the generation day, so exact replay later requires the original date. The sidecar's `document_date` and seeded offset can recover that date, but the manifest does not record it directly.

`random.js` provides a Lehmer generator. `Math.random` is used only by `rollSeed` and `planBatch` to choose new seeds. `format.js` avoids locale-dependent formatting so the same inputs produce the same text in browsers, Node tests, and thumbnail generation.

Random draw order is part of replay behavior. Drawing the day offset before the document number preserves earlier samples. Reordering those draws changes the generated documents.

## CSP and DOM rendering

The page uses a self-only CSP without `unsafe-inline`. The HTML renderer creates nodes through `createElement` and writes values through `textContent`. It emits classes instead of inline style attributes.

Vendor branding reaches the page through CSSOM custom properties such as `--vd-accent`, `--vd-accent-soft`, `--vd-ink`, and `--vd-font`. Scripts and styles are local files, and export libraries are vendored under `js/vendor/`.

## Color ownership

App controls in `css/app.css` use shared tokens. Printed pages use theme-independent `--color-document-*` tokens from `css/src/01-tokens.css`, so dark mode does not change exported paper colors.

Vendor accents in `vendors.js` are document content. They remain distinct literals applied through CSSOM instead of being mapped to the shared app palette.

## State and render passes

`app.js` stores vendor, document type, invoice layout, seed, scan preset, overrides, and output choices. `draw` rebuilds the page and caption. `syncOutput` derives visible output controls, label notes, pair availability, size estimates, and the primary button label.

`LABEL_LEVELS` maps label choices to ground truth, field boxes, and word boxes. `INCLUDE_SCOPES` maps batch scope to vendor and type selection. `DOCUMENT_TYPES` and `DEGRADE_PRESETS` provide control labels. `wireSegment` wraps `initSegmented` so programmatic changes also update selection highlights.

The layout has a toolbar, a fitted page stage, and a sticky Output panel. The panel's scope switch and footer stay visible while its middle scrolls. Its vendor swatch uses the same `--vd-accent` as the printed page.

## Export paths

`exporters.js` accesses UMD library globals through injected accessors. Tests supply recording fakes, and unavailable libraries produce a readable error.

Text PDFs render directly from the model. PNG and rasterized PDFs use `html2canvas` sequentially because they share one paper element. Raster capture temporarily sets zoom to 1, including when the page is in the full-size dialog.

A labeled batch writes one sidecar per page, a `manifest.jsonl` with one compact sidecar per line, and a `README.txt` with the schema and settings. JSON-only batches skip PDF and raster generation. The DOM stage still advances for progress and requested box measurements.

Pair mode applies to PNG output. `renderRaster` returns both the degraded image and its clean capture, so a pair does not require two captures. JSZip retains batch files in memory until it creates the archive.

The batch loop yields during synchronous formats so progress and stop controls can run. A stop completes the active document, writes the completed files, and records partial counts. [Decisions](decisions.md) explains these trade-offs. [Verification](verification.md) describes test coverage and its limits.
