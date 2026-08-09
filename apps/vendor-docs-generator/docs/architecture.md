# Architecture

## Vendor Document Generator

The app is a small pipeline with one branch point at the end. A seed and a selection go in; a renderer-agnostic model comes out; two independent renderers consume that same model; and a third consumer turns the model into labels rather than pixels.

```text
{ vendorId, docTypeId, style, seed }
            │
            ▼
   document-model.js  ──uses──▶  vendors.js, random.js, format.js
            │
            ▼
   DocumentModel { header, blocks[], facts }
            │
      ┌─────┴──────┬──────────────┐
      ▼            ▼              ▼
paper-render.js   pdf-render.js   annotations.js
   (DOM)            (jsPDF)          │  ▲
      │              │               │  │ boxes
      │              │               │  │
      │              │        annotate-boxes.js
      │              │          (reads the DOM back)
      └──────┬───────┴───────────────┘
             ▼
        exporters.js  ──▶  PNG/JPEG · PDF · JSON · ZIP batch
             │                   ▲
             ▼                   │ transform
        degrade.js  ─────────────┘
     (raster in, raster + matrix out)
```

### The model is the contract

`buildDocument` returns a `title`, a `subtitle`, a `footer`, an ordered array of typed blocks (`parties`, `table`, `totals`, `stamp`, `keygrid`, `partypair`, `words`, `note`, `callout`, `chips`, `banner`, `signatures`, `signoff`), and a `facts` record. Each renderer is a switch over `block.kind`.

This is the structural change from the single-file original, which carried two hand-maintained copies of every layout: one that wrote HTML strings and one that drove jsPDF. Any fix to one had to be mirrored by hand in the other, and the two had already drifted. With one model, the preview and the searchable PDF cannot disagree about what a document says.

### Facts, blocks, and the sidecar

The blocks are display strings. `facts` is the structured truth a builder had in hand *before* it stringified anything: dates as `Date`, money as numbers, line items as records. The app used to compute all of that, print it, and throw it away, which is why the output was 500 pages someone still had to label.

`annotations.js` walks `facts` into the wire schema. Two rules make it worth trusting:

- **A key is always present.** The payload is built by walking `FIELD_KEYS`, not by spreading whatever a builder happened to record, so a document type that knows nothing about `vehicle_number` still emits `"vehicle_number": null`. A consumer can distinguish "this page has no PO number" from "the generator forgot".
- **A key is non-null only when the page prints it.** A challan lists goods without prices, so its `unit_price` is null even though `buildItems` computed one. Scoring an extractor against a number that is not on the page is worse than not scoring it at all.

### Boxes

`paper-render.js` stamps `data-field` onto every node carrying a value; that attribute is the *only* coupling between the renderer and the annotation layer. `annotate-boxes.js` reads them back with `getBoundingClientRect`, so a new block type needs no change there.

Coordinates are normalised into the 0..1 page box rather than reported in pixels. That is what makes them survive the preview's fit-to-frame CSS transform, the export's 2x capture scale, and any future change to the 794x1123 page: both the element rect and the page rect scale together, so the ratio does not move.

A field printed in more than one place produces more than one region, in document order. A two-line address genuinely occupies two boxes, and merging them would claim a single box covering the gap between them that no ink lands in.

The caveat that matters is recorded on every payload as `boxes_apply_to`, not left in a doc: boxes are measured on the HTML page, so they describe the PNG and the rasterised PDF. `pdf-render.js` lays out independently in A4 points, so they do **not** describe the text-layer PDF. Emitting boxes for that would mean instrumenting the jsPDF cursor to report its own positions, which is real work and has not been done.

### Degradation, and why it reports a matrix

A corpus where every page is a pixel-perfect raster on pure white cannot tell you where an extractor breaks, because nothing in it is hard. `degrade.js` adds the axis that makes "how much accuracy do I lose to scan quality" measurable: the same seed rendered clean and rendered degraded, differing only in the pixels.

Two contracts matter more than any individual effect.

**Seeded.** Every stochastic choice is drawn from the document seed, in a fixed order, so a seed plus a preset always produces the same page and a dataset can be regenerated. Drawing every value up front is what makes the order fixed: turning grain off does not shift the tilt.

**It reports its geometry.** Skew, rotation, and keystone move the ink; grain, blur, and JPEG do not. `planDegradation` returns the projective transform before anything is painted, and `transformBoxes` runs every box through it. Without that, phase 3 would quietly corrupt phase 2, and both halves would still pass their own tests.

Planning is split from painting for a second reason: `planDegradation` is pure arithmetic over a seed and a page size, so the JSON-only batch path can move its boxes correctly without rasterising a single page.

The matrix is expressed in normalised page coordinates, which is what lets one plan serve both the 794x1123 layout page it was made against and the 1588x2246 capture it is applied to. `toPixelMatrix` scales it into whatever bitmap is actually in hand at draw time.

Canvas 2D cannot draw a projective transform in one call, so a keystoned page is drawn in four-pixel strips whose affine approximation is well under a pixel off. The matrix reported to the annotations is the exact projective one either way, and the approximation error sits far below the blur and grain applied immediately afterwards.

Each transformed region carries both shapes. `box` stays an axis-aligned `[x, y, width, height]` so an evaluation script written against a clean run keeps working; `quad` carries the four corners the ink actually landed on. Reporting only the quad would break every existing reader, and reporting only the box would silently claim a tilted value is upright.

JPEG loss is the encoding rather than a painted effect: asking the canvas for a lossy JPEG is the same compression a real scanner applies, and baking it into a PNG would need an async round-trip through an `Image` for a worse result. A lossy preset therefore writes `.jpg`.

### Determinism

Everything downstream of the seed is deterministic. `random.js` provides a Lehmer generator; `Math.random` appears only in `rollSeed` (a new document) and `planBatch` (choosing seeds for a batch). `format.js` deliberately avoids `toLocaleString` and `toLocaleDateString` so that a seed produces byte-identical text in the browser, in Node tests, and in the CI thumbnail run.

Draw order inside `buildDocument` is load-bearing: the day offset is drawn before the document number, so changing that order would silently renumber every previously generated sample.

### Content-Security-Policy and rendering

The page ships with `default-src 'self'; script-src 'self'; style-src 'self'`, with no `unsafe-inline`. Two consequences drive the renderer:

- **Inline `style` attributes never apply.** The original built each document out of `style="..."` strings, which would have rendered a completely unstyled page here. `paper-render.js` emits classes instead, and the six vendor brand values arrive as the `--vd-accent`, `--vd-accent-soft`, `--vd-ink`, and `--vd-font` custom properties set through CSSOM, which CSP does not police.
- **No inline `<script>` or `<style>`.** All behaviour lives in ES modules under `js/`, all styling in `css/app.css`, and the four export libraries are vendored under `js/vendor/` rather than pulled from a CDN.

`paper-render.js` also builds every node with `createElement` and `textContent`, never `innerHTML`, which the repo's ESLint rule requires and which makes the rendered content injection-proof by construction.

### Colour

App chrome in `css/app.css` is entirely token-derived. The printed page uses a separate, deliberately theme-independent set of `--color-document-*` tokens (`css/src/01-tokens.css`) so a preview of something that will be exported to PDF keeps looking like paper in dark mode. The six vendor accents are literals in `vendors.js` because they are document *content*, not app chrome: six businesses should not look like six shades of one design system.

### Export paths

`exporters.js` reaches the three UMD globals through injected accessors rather than touching `window` directly, so the module runs under Node in tests with recording fakes, and a script that failed to load produces a readable message instead of a `TypeError` inside a click handler.

A batch can also be labelled, in which case each document gets a `.json` sidecar beside it and the archive root gets a `manifest.jsonl` (every sidecar again, one compact object per line, because tooling that streams a dataset wants one file to read) and a `README.txt` recording the schema and the settings the run used. The `json` format skips both renderers entirely and is the fast path for iterating on an evaluation script.

Pair mode writes the degraded page and the clean original from a single capture, which is why `renderRaster` returns both rather than the caller rendering twice. Rendering is the slowest step in a batch, and doing it twice for two images of the same page would double it.

The text-PDF batch path never renders to the DOM at all: `renderPdf` writes straight from the model. Only the PNG and rasterised-PDF paths need `html2canvas`, and those run sequentially because they share one paper element. Because the fitted preview scales the paper with a CSS transform, `app.js` pins the zoom to 1 for the duration of any capture so every raster sample is a true 794px page, in either the inline frame or the full-size overlay.
