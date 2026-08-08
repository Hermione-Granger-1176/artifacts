# Architecture

## Vendor Document Generator

The app is a small pipeline with one branch point at the end. A seed and a selection go in; a renderer-agnostic model comes out; two independent renderers consume that same model.

```text
{ vendorId, docTypeId, style, seed }
            │
            ▼
   document-model.js  ──uses──▶  vendors.js, random.js, format.js
            │
            ▼
   DocumentModel { header, blocks[] }
            │
      ┌─────┴──────┐
      ▼            ▼
paper-render.js   pdf-render.js
   (DOM)            (jsPDF)
      │              │
      └──────┬───────┘
             ▼
        exporters.js  ──▶  PNG · PDF · ZIP batch
```

### The model is the contract

`buildDocument` returns a `title`, a `subtitle`, a `footer`, and an ordered array of typed blocks (`parties`, `table`, `totals`, `stamp`, `keygrid`, `partypair`, `words`, `note`, `callout`, `chips`, `banner`, `signatures`, `signoff`). Each renderer is a switch over `block.kind`.

This is the structural change from the single-file original, which carried two hand-maintained copies of every layout: one that wrote HTML strings and one that drove jsPDF. Any fix to one had to be mirrored by hand in the other, and the two had already drifted. With one model, the preview and the searchable PDF cannot disagree about what a document says.

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

The text-PDF batch path never renders to the DOM at all: `renderPdf` writes straight from the model. Only the PNG and rasterised-PDF paths need `html2canvas`, and those run sequentially because they share one paper element. Because the fitted preview scales the paper with a CSS transform, `app.js` pins the zoom to 1 for the duration of any capture so every raster sample is a true 794px page, in either the inline frame or the full-size overlay.
