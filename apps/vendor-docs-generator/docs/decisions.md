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

### Labels are the headline, so they get a rung of their own

An earlier plan collapsed ground truth behind an "Advanced" disclosure to keep the default view calm. It never was one: labelled output is the reason to use this app rather than any of the several existing invoice generators, and hiding the controls for it would be hiding the headline. In the studio layout that decision survives as a section of its own in the Output panel, open by default, not as a fold.

### The studio layout: toolbar, stage, Output panel

The old rail stacked five equal cards (Document, Export, Ground truth, Scan quality, Batch) with a different control type on nearly every row, two blue primary buttons, and one decision ("what do I get out?") split across three cards. It was collapsed into an accordion to stop it outgrowing the stage, which fixed the height and left the zig zag. The layout is now three regions that each answer one question.

- **Toolbar, "what document?"** A vendor dropdown (with a swatch of the vendor's accent, set through CSSOM like the paper's own colours), the six type pills, the invoice layout toggle, the seed, and New document. The vendor is a dropdown on purpose: six brand dots read well but say nothing until hovered, and the dropdown reuses the shared select. The type pills use short names (`short` on `DOCUMENT_TYPES`) with the full name as a tooltip, and a second dropdown (`#vdDocTypeSelect`) takes over below 700px. Both stay in the DOM and agree through `setDocType`, so there is one state and two shapes.
- **Stage, "what does it look like?"** The fitted page, a caption line, and quiet fit and full-size controls. Nothing else sits on it. Fit-width scaling, the full-size dialog, and the scan preview are unchanged.
- **Output panel, "what do I get out?"** One card, with a This page / Batch switch pinned to the top and one primary button pinned to the bottom, so the two things that decide what a click does are always in view. Only the choices between them scroll. The panel is capped to the window and pins beside the page, which replaces the old pinned-stage arrangement: the panel is now the shorter column and the page never needs to follow it.

Below about 1000px the three regions stack as toolbar, page, output, and the panel stops pinning because there is no column left to pin beside. The app widens its own shell to 1232px (header included, so they keep one left edge) because three columns do not fit the shared 1000px.

### One ladder for labels, one control for scope

The Labels control is a single ladder, None / JSON / + Fields / + Words, standing for the three switches it replaced:

| Rung     | Ground truth | Field boxes | Word boxes |
| -------- | ------------ | ----------- | ---------- |
| None     | off          | off         | off        |
| JSON     | on           | off         | off        |
| + Fields | on           | on          | off        |
| + Words  | on           | on          | on         |

Each rung includes the one below it, so "word boxes without field boxes" and "boxes without labels", which the checkboxes allowed to be set and then had to grey out, are not reachable at all. `LABEL_LEVELS` in `app.js` is the whole mapping, and `annotate`, the batch, and the estimate read their three booleans from it, so exports are byte-identical to what the same three switches produced.

One old combination has no rung: ground truth off with boxes on, which meant "no sidecar beside page exports, but a JSON-only batch still carries boxes". A JSON batch is necessarily labelled, so choosing the JSON format lifts the ladder off None and disables that rung until another format is chosen. To get boxes in a JSON batch, pick + Fields.

The two batch checkboxes (all types, all vendors) became one Include control (This combo / All types / All vendors / Everything), via `INCLUDE_SCOPES`. They were never independent questions about a checkbox so much as one question about how wide the batch is.

### One primary button, and what it does

The page exports used to be three buttons (PDF, PNG, JSON) that each wrote the sidecar, so asking for both formats wrote it twice. There is now one Format control (PDF / PNG / Both, plus JSON in batch mode) and one primary button whose label follows the scope ("Download" or "Generate ZIP"). A page export writes the chosen formats and then one sidecar. The single-page "JSON only" action is kept, as a quiet button in the Labels header, because dropping it would remove a feature rather than regroup one; it only shows in page mode, where JSON is not a format.

Pair mode appears only when it applies: a degraded scan and a format that includes a PNG. The PDF type (text layer or rasterised) shows only when the format includes a PDF. Everything the panel shows or says is computed from state in `syncOutput`, so a change from any control or from code lands it in the same place.

### The stage no longer pins, and the frame sizes from the window

With the output panel as the shorter, pinned column there is no reason for the stage to follow it. The frame is `clamp(380px, 100vh - 300px, 1123px)`, where 300px is the header, intro, toolbar, and caption it gives up. At 1400x900 that fits the page at about 50% and leaves the panel's footer just below the fold until the first scroll, which is accepted: shrinking the frame to win those last pixels would shrink the preview for everyone.

The preview remains bound by height, not width. Making the page bigger on screen is a vertical problem (`--vd-frame-inset` and the length of the intro lede) and a separate decision from how the controls are grouped.

### Vendor brand colours stay literal

`css/app.css` is fully token-derived, as the repo requires. The six vendor accents in `vendors.js` are raw hex, on purpose: they are the content of a generated document, not app chrome. Mapping them onto the shared bookmark-note palette would make all six businesses look like the same design system, which is exactly what makes a sample set useless for training an extractor to cope with visual variety. They reach the page through CSS custom properties, so no colour literal ever enters a stylesheet.

### A theme-independent paper palette

`--color-document-*` is defined once in `:root` and deliberately not overridden in the dark block. A preview of a page that will be exported to PDF has to keep looking like paper; a dark-mode invoice would misrepresent what the export contains.

### Classes and CSSOM instead of inline styles

Under `style-src 'self'` a browser drops inline `style` attributes, which the original relied on for every single element of every document. Rewriting the renderer to emit classes was unavoidable rather than cosmetic. CSSOM writes (`element.style.setProperty`) are not covered by CSP, which is what makes runtime vendor theming possible at all.

### Hand-written types for the vendored libraries

jspdf, jspdf-autotable, html2canvas, and jszip all ship their own `.d.ts`, and the repo's precedent (`config/types/chart-vendor.d.ts`) is to add the package as a devDependency and import its types. Here that would mean four heavyweight packages installed solely so `tsc` can read their type files. `config/types/pdf-vendor.d.ts` declares only the surface the app calls instead. If the app starts using more of an API, widen that file rather than reaching for `any`.

### The preview never scrolls; full size is a separate mode

A4 at 96dpi is 794x1123, larger than the stage on any laptop next to a control column, so the preview has to scale. The first version fitted on width alone and let the rest scroll, which put a scrollbar inside a panel that was already inside the scrolling document, and at 100% it clipped the page mid-column. Both are now gone: the frame is a fixed viewport-relative box, the scale is the smaller of the width and height ratios, and the whole page is always visible. Reading the page at its true size is a distinct mode, a modal `<dialog>` that fills the window, rather than a scrollbar.

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

### Degradation reports its geometry, and the boxes are moved before they are written

Skew, rotation, and keystone move the ink; grain, blur, and JPEG do not. So `planDegradation` returns the projective transform before anything is painted, and the annotation path runs every box through it. The alternative, writing the boxes the DOM measured and letting a consumer work out that the page has since been tilted, would mean phase 3 quietly invalidating phase 2 while both halves kept passing their own tests. A browser test rasterises a real page, tilts it, and counts the ink inside each transformed box against the ink still inside the box it started from, because that is the only check that can actually fail if this rots.

Each region carries both shapes. `box` stays an axis-aligned rectangle so an evaluation script written against a clean run keeps working unchanged; `quad` carries the four corners. Only the quad would break every existing reader, and only the box would silently claim a tilted value is upright.

### Planning is separate from painting

`planDegradation` is pure arithmetic over a seed and a page size. `degradeCanvas` is the only part that touches a canvas. That split is what lets the JSON-only batch path, which never rasterises anything, still transform its boxes correctly. It also puts the geometry and the seeded choices somewhere they can be tested exactly rather than inferred from pixels.

The transform is normalised, so one plan serves both the 794x1123 layout page it was made against and the 1588x2246 capture it is applied to. The pixel matrix is derived at draw time from whatever bitmap is in hand.

### Keystone is a real projective map, drawn in strips

Tilting a page away from a lens narrows the far edge *and* foreshortens it. A horizontal squeeze would produce half of that, and a model trained on it would not have seen the other half. Canvas 2D cannot draw a projective transform in one call, so the page is drawn in four-pixel strips whose affine approximation is well under a pixel off, and the matrix handed to the annotations is the exact projective one. The approximation error sits far below the blur and grain applied immediately afterwards.

### Every stochastic value is drawn up front

Rotation, skew, the banding phase and period, and the light centre are all drawn from the seeded stream before any of them are used, and in a fixed order. Drawing them lazily would mean turning grain off changed how far the page tilted, which makes two runs that differ in one setting incomparable. Comparability across settings is the entire reason this feature exists.

Magnitudes are jittered by a quarter either way and the direction is a coin flip, so a preset teaches a model the effect rather than the preset.

### A lossy preset writes a JPEG, not a PNG

JPEG loss is the encoding, not an effect painted onto the bitmap. Asking the canvas for a lossy JPEG applies the same compression a real scanner does; baking it into a PNG would need an async round-trip through an `Image` and produce a worse result. The file extension follows the encoding rather than the button that produced it, because calling a JPEG a PNG is a lie about the file.

### The scan preview is a separate mode, not the live page

Degradation happens to the raster, and the boxes are measured off the DOM, so the live preview cannot show the effect without breaking the thing that makes the boxes correct. Choosing between five presets from their descriptions alone is guesswork, so **Preview scan** rasterises the current page, degrades it, and shows the image in the existing full-size overlay. One close path empties the overlay and returns the live page to the frame, so the two modes cannot disagree about where the page is.

### Nine sliders, folded away

The presets are the common case and the panel should stay calm. The custom knobs live behind a "Fine-tune" `<details>`, and they are built in `app.js` from the `DEGRADE_KNOBS` table rather than written into `index.html`, so the list of exposed settings has one home and adding one is a single edit. Touching any knob switches the preset to "custom", because the sidecar would otherwise name a preset the page was not rendered under.

### Stopping a batch keeps what it finished

A run that can be started and not stopped is a run that has to be waited out or killed with the tab, and killing the tab throws away work that was already done. So **Stop and keep what is done** ends the loop between documents and writes the archive anyway.

Three things follow from "between documents" rather than "immediately". The document in flight is completed rather than abandoned, so no half-written page reaches the ZIP. The archive is real output rather than a consolation prize: it is foldered, manifested, and labelled exactly like a full run. And the `README.txt` reports the count it actually holds plus the count that was planned, because an archive that claims 900 documents while holding 118 is the one failure this file exists to prevent. The filename carries `_partial` for the same reason.

Stopping before the first document finishes downloads nothing. An archive holding only a README describing an empty run is worse than no file.

### The stop button is what forced the loop to yield

The batch loop is `await`-free for text PDFs, because jsPDF is synchronous, and nearly so for JSON. A click cannot be delivered to a thread that never returns to the event loop, so a stop button on the old loop would have been unclickable for exactly as long as it was needed, then pointless. Yielding is not a companion improvement here, it is the feature.

It is time-sliced at 50ms rather than once per document. A trip through the task queue per document is real cost on a 900 document run and buys responsiveness below what anyone can perceive. The canvas formats already yielded inside `html2canvas`, so this only changes the two formats that never touched it.

Measured after the change: the full 900 document cross product runs in 0.8s as JSON and 4.5s as text PDFs, with the meter moving throughout. The earlier claim in the README, that these formats could leave the browser unresponsive at the maximum batch size, was written from reading the loop rather than timing it, and overstated the JSON case by a wide margin.
