# Decisions

## Vendor Document Generator

### One model, two renderers

The source artifact had two parallel implementations of every layout: one building HTML strings for the preview, one driving jsPDF for the text export. They had already drifted. Rather than port both, `buildDocument` now emits a typed block list that both renderers walk. Adding a document type means adding one builder, not two.

### Facts are recorded, not reconstructed

The obvious way to emit ground truth is to parse it back out of the rendered blocks. That would be a second implementation of every layout's meaning, which is exactly the duplication the one-model decision above exists to avoid, and it would silently start lying the day a builder changed a label. Instead every builder returns the structured values it already had, and `annotations.js` formats them. The sidecar and the page come from the same numbers or the build fails.

The same reasoning drives the `data-field` attribute rather than matching printed text in the annotator: the renderer knows what each node is, so it says so, and `annotate-boxes.js` stays a pure measurement pass with no layout knowledge at all.

### A field is null exactly when the page prints nothing

An extractor scored against a field that is not on the page is being punished for being right. So `facts` carries a property only when the document actually shows the thing: a clean invoice records no `buyerPhone` even though `buildBuyer` computed one, and a challan records `itemsPriced: false` even though `buildItems` priced every row.

The other half of the rule is that the key still appears, as an explicit `null`. Without that a consumer cannot tell "no PO number on this document" from "the generator has no idea about PO numbers", and those mean very different things when you are computing recall.

### Boxes are normalised, and one region per node

Pixel boxes would be wrong the moment anything scaled: the preview applies a CSS transform to fit the frame, and `capturePaper` rasterises at 2x. Normalising against the page's own rect makes both cancel out, and a consumer multiplies by whatever image dimensions they actually have.

A field printed in more than one place gets more than one region rather than a merged box. A two-line address occupies two boxes with a gap between them, and a box drawn around both would claim ink in the gap. The thin logo lockup is the same case: the vendor name is split across two spans, so it is two regions, because there is genuinely no single box on that page containing the whole name.

### Ground truth is a card, not a disclosure

The rail was already three cards and this adds a fourth, which the plan for this work suggested collapsing behind an "Advanced" disclosure to keep the default view calm. It is a plain card instead. Labelled output is the reason to use this app rather than any of the several existing invoice generators; hiding the controls for it would be hiding the headline.

### Vendor brand colours stay literal

`css/app.css` is fully token-derived, as the repo requires. The six vendor accents in `vendors.js` are raw hex, on purpose: they are the content of a generated document, not app chrome. Mapping them onto the shared bookmark-note palette would make all six businesses look like the same design system, which is exactly what makes a sample set useless for training an extractor to cope with visual variety. They reach the page through CSS custom properties, so no colour literal ever enters a stylesheet.

### A theme-independent paper palette

`--color-document-*` is defined once in `:root` and deliberately not overridden in the dark block. A preview of a page that will be exported to PDF has to keep looking like paper; a dark-mode invoice would misrepresent what the export contains.

### Classes and CSSOM instead of inline styles

Under `style-src 'self'` a browser drops inline `style` attributes, which the original relied on for every single element of every document. Rewriting the renderer to emit classes was unavoidable rather than cosmetic. CSSOM writes (`element.style.setProperty`) are not covered by CSP, which is what makes runtime vendor theming possible at all.

### Hand-written types for the vendored libraries

jspdf, jspdf-autotable, html2canvas, and jszip all ship their own `.d.ts`, and the repo's precedent (`config/types/chart-vendor.d.ts`) is to add the package as a devDependency and import its types. Here that would mean four heavyweight packages installed solely so `tsc` can read their type files. `config/types/pdf-vendor.d.ts` declares only the surface the app calls instead. If the app starts using more of an API, widen that file rather than reaching for `any`.

### The preview never scrolls; full size is a separate mode

A4 at 96dpi is 794x1123, larger than the stage on any laptop next to a 310px control rail, so the preview has to scale. The first version fitted on width alone and let the rest scroll, which put a scrollbar inside a panel that was already inside the scrolling document, and at 100% it clipped the page mid-column. Both are now gone: the frame is a fixed viewport-relative box, the scale is the smaller of the width and height ratios, and the whole page is always visible. Reading the page at its true size is a distinct mode, a modal `<dialog>` that fills the window, rather than a scrollbar.

Because a transform does not change the layout box, the wrapper is sized to the *scaled* page and the page is scaled from its top-left inside it. Scaling the wrapper would leave a full 794x1123 box in the layout, which overflows the frame and breaks centring.

The overlay moves the live paper element rather than cloning it, so the renderer and the exporters keep pointing at one page in either mode. Captures pin the zoom to 1 first, so every raster export is a true 794px page regardless of what the viewer is looking at.

### A statement carries a balance forward

The ledger opens with the balance brought in from the previous period, and a payment is only ever drawn against something outstanding and capped at it. Without the opening balance a ledger that happened to draw a payment first went negative, because there was no debt to settle: a statement of account cannot do that. The test that was supposed to catch it compared the banner against `Math.max(0, balance)`, so the clamp hid the negative rows from the assertion. It now walks the printed rows with no clamp at all.

### Sales tax is a flat 8.25%

The source used one flat rate and so does this. It is a plausible US combined state-and-local rate but it is not any particular jurisdiction's, and the app says so in the callout. Modelling real per-state rates would add a lookup table and a lot of correctness surface for no benefit to the actual purpose, which is producing pages with tax lines on them.

### Fiction-reserved contact details

Vendor phone numbers use the 555-01xx range reserved for fiction and every email domain ends in `.example`, which is reserved by RFC 2606. A test enforces both. Generated documents also carry a footer marking them as samples and not valid tax records. The point is that a generated page cannot accidentally point at, or be mistaken for, a real business's paperwork.

### The dense layout is invoice-only

Only invoices get the second treatment, because the dense line-level tax layout is a thing that exists for invoices specifically. The control is disabled rather than hidden for other types, so the option stays discoverable and the UI never silently ignores a setting.
