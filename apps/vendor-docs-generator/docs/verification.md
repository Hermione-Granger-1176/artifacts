# Verification

## Vendor Document Generator

Tests live in `tests/js/apps/vendor-docs-generator/`, with `fake-dom.js` and `library-fakes.js` as local support and `app-test-support.js` extending the shared app-entry mocks. Every source file under `js/` is at 100% line and function coverage.

### The arithmetic is checked against the document, not against the helper

The money maths is the part that would be quietly wrong in a way nobody notices, so `document-model.test.js` re-derives it from the strings the document actually prints rather than calling the same helper the model called:

- **Line amounts.** Every row's printed amount must equal its printed quantity times its printed unit price, to the cent, for every vendor.
- **Clean invoice totals.** The subtotal is re-summed from the printed row amounts, the tax re-computed as the sum of the per-line rounded tax, and the grand total re-added; all three must match the printed totals block. Tax is defined as the sum of the lines rather than the rate applied once to the subtotal, because the dense layout has to print a tax column that adds up. Applying the rate once made the two treatments of one seed disagree by a cent, and a sweep over six vendors and forty seeds now asserts they agree.
- **Dense invoice.** Per-line tax is re-derived from each printed assessable value, each line total re-added, and both are summed and checked against the table footer *and* against the separate summary block, which have to agree with each other.
- **Amount in words.** The spelled-out grand total must end in the same cents as the numeric one.
- **Statement ledger.** The running balance is walked from the printed opening balance through the printed charges and payments and compared row by row, and the balance-due banner is checked against the final balance with no clamp. A sweep over all six vendors and 59 seeds confirms no individual row ever shows a negative balance, not merely that the banner does not.
- **Receipt.** The printed subtotal must equal the sum of the printed line amounts, subtotal plus tax must equal the amount due, amount paid must clear it, and the balance must be zero. The subtotal and tax rows are the point: the receipt used to jump from the table straight to a total that silently included 8.25%.
- **Challan.** Quantity chips are re-counted from the table, packages are asserted to be at least one per line rather than exactly the row count, every row's remark is asserted distinct and lot-numbered, and the document is asserted to carry no totals block at all, since a dispatch note must not price the goods.

Price jitter is checked to stay within 4% of the catalogue list price plus one rounding step, and subscription units (`mo`, `yr`) are checked to be quantified 1-3 rather than in the wide range used for physical goods.

### One seed, six vendors

The seed owns the commercial event and the vendor owns its own paperwork, and both halves are asserted. For one seed across all six vendors the buyer and the issue date must be identical, which is what makes the side-by-side comparison the About section promises a real comparison. The document number, the quantity vector, the company registration, and the whole statement ledger must all differ, because those belong to the issuing vendor. Every one of them used to be seed-only, so six vendors printed one invoice number, one quantity vector, and a byte-identical ledger.

### Dates

Net-30 terms are asserted to be exactly 30 days from the issue date, quotations exactly 14, and issue dates are asserted to be backdated within the last 180 days and never in the future.

Statements get their own sweep over six vendors and thirty seeds: the printed period must end on or before the generated date, every ledger row must fall inside the printed period and never after the generated date, and the rows must be in chronological order. The period label used to be a quarter drawn from the seed with no relationship to either the rows or the generated date, so a statement generated in March routinely carried a Q4 heading over a ledger running into June.

### Determinism

The same seed and reference date rebuild a deep-equal model; different seeds produce different documents. The seeded generator is checked for reproducibility, for staying inside the open unit interval over 500 draws, and for normalising the seeds (`0`, the modulus) that would otherwise make it a fixed point.

### Ground truth

`annotations.test.js` sweeps every vendor by every type by both invoice treatments and asserts the three rules the schema promises:

- **Completeness.** Every payload's `fields` key set is deep-equal to `FIELD_KEYS`, in order, and every line item and ledger row carries its full key set. A non-null field always has exactly `text` and `value`, and never an empty `text`, because an empty string would be a third state between "absent" and "present".
- **Honesty.** A clean invoice is asserted to have no `po_number`, no `buyer_phone` and no `vendor_company_reg`; the dense treatment of the same document is asserted to have all three. A challan is asserted to price nothing and a statement to have an empty `line_items` and a populated `transactions`.
- **Arithmetic.** Over 6 vendors by 7 treatments by 6 seeds, the line amounts must sum to the subtotal and subtotal plus tax plus shipping must equal the grand total, both to the cent. Where per-line tax is printed, it must sum to the document tax and each line total must be its own amount plus its own tax.

Normalisation is checked too: dates are ISO in `value` and the document's own format in `text`, money is a number, a rate is a fraction under 1 while its text ends in `%`, and the buyer address keeps its line break in `text` and loses it in `value`. A separate sweep rebuilds each ISO date and asserts it names the same calendar day the page prints, which is the bug `toISOString` would have introduced west of Greenwich.

The strongest of these closes the loop between the two outputs: for every combination the page is rendered, every `[data-field]` node is collected, and each node's text must appear in the sidecar entry for that field. A renamed label or a re-formatted value fails this immediately.

### Boxes

`annotate-boxes.test.js` measures a deterministic fake layout, so it can prove the walk and the arithmetic but not the pixels:

- Every labelled node becomes exactly one region, in document order, and every box lies inside the 0..1 page.
- Scaling every rect by 0.593, the way the fitted preview does, must produce byte-identical boxes. Without normalising against the page's own rect this is the test that would fail at any zoom other than 100%.
- A two-line address must produce two regions, with the second below the first.
- Row-scoped fields must be addressed as `line_items.<n>.<key>` and `transactions.<n>.<key>`.
- A blank ledger cell must produce no region at all, because the sidecar reports that field as null and a box for it would be a box around nothing.
- Word boxes are absent unless asked for, and when present each word must lie inside its own region and share its baseline.
- A page that was never laid out must still produce finite coordinates rather than filling the payload with `Infinity`.

Whether those boxes land on the right ink is a question only a browser can answer, and is asked in the browser suite below.

### Renderers

`paper-render.test.js` renders into a fake DOM and asserts on the tree: all six logo treatments, the layout classes, per-column alignment, the emphasised totals row matching `emphasisIndex`, the dense-invoice grid and table footer, and that re-rendering replaces the page rather than stacking pages. It also asserts vendor branding arrives through `style.setProperty` rather than an inline style attribute, which is the property CSP depends on.

`pdf-render.test.js` renders into a recording jsPDF fake and asserts the text layer contains the letterhead, every line item, and the totals; that the accent bar is filled with the vendor's colour; that the `didParseCell` hooks emphasise exactly the rows the model marked; and that a page too short for the content spills onto a second page.

It also guards the three faults this renderer shipped. The letterhead and the title are asserted not to overlap for any vendor, type, or style, reconstructing both boxes from the sizes actually used, since the title shrinks to fit and the monogram tile shifts the name right. A long meta value is asserted to drop to its own line rather than overprint its label, with the test requiring that at least one seed in the sweep actually exercises the wrapping branch. The banner and callout are asserted to carry `theme: "plain"`: under the default striped theme, `alternateRowStyles` resolves to 245 on row index 0 and outranks both `styles` and `bodyStyles`, so those single-row tables painted flat grey and the statement's balance due printed white on near-white. That precedence was measured through `didParseCell`, not assumed. Each vendor is also asserted to letterhead in its own font family, which the PDF ignored entirely until now.

Both renderers are run across all 36 vendor/type combinations.

### Exports

`exporters.test.js` covers the download anchor lifecycle (attached before click, revoked on a later tick, data URLs passed through unrevoked), the aspect-ratio maths in `canvasToPdf`, and that the text-PDF path never rasterises while the image path never emits a text layer. Batch runs are asserted on ZIP folder structure, base64 PNG entries, capture counts per format, and progress reporting.

A labelled batch is asserted to write one sidecar per page plus `manifest.jsonl` and `README.txt`, with the manifest holding one compact object per document in generation order and the README recording the format and PDF mode the run actually used. An unlabelled batch must write neither root file. The `json` format is asserted to produce nothing but sidecars, which is the whole point of the fast path. The size estimate is asserted to grow monotonically as rasterisation, labels, boxes and word boxes are switched on, to ignore box settings entirely when no labels are being written, to grow again for grain and for pair mode, to shrink for a lossy scan, and to charge nothing for pair mode when there is no scan to pair with.

A degraded run is asserted to render the page once and keep the clean capture beside the degraded one, rather than capturing twice; a clean run must hand back the capture itself rather than copying it. A rasterised PDF built from a lossy scan must declare `JPEG` to jsPDF. Pair mode applies to PNG outputs, downloads the degraded page and the original, and downloads only one file when there is nothing to degrade. A degraded PNG batch is asserted to write `.jpg`, `.clean.png`, and `.json` per document, to record the preset in the README, and to carry the degradation block through into the manifest. A JSON-only batch cannot advertise a clean pair that it did not write.

### Scan degradation

`degrade.test.js` covers the parts that can be checked exactly rather than looked at.

Every preset is asserted to resolve to a settings object with the same shape and no holes, and to be clean only if it is the clean preset. Every slider in `DEGRADE_KNOBS` is asserted to name a real setting and to bracket the value every preset sets for it, so a preset can never put a knob outside its own range.

Determinism is asserted directly: the same seed and preset produce a byte-identical plan, a different seed does not, and turning grain off leaves the rotation and the transform untouched. Rotation is swept across sixty seeds and asserted to stay within a quarter either way of the preset's nominal, to take both signs, and to vary rather than snapping to a handful of values.

The geometry is checked against its own definition. A rotated page is asserted to keep all four corners inside the unit square with the centre a fixed point, which is what the fit scale exists to guarantee. A keystone is asserted to make the near edge wider *and* the far half shorter, and to leave a non-zero bottom row, because a squeeze would pass the first check and fail the second. One plan made against the 794x1123 layout page and another against the 1588x2246 capture must give the *same* normalised matrix and different pixel matrices, and `toPixelMatrix` must reconcile them.

`transformBoxes` is asserted to move both regions and word boxes, to emit a `quad` whose first corner is the projected origin, and to keep `box` as the exact axis-aligned hull of that quad. The identity must return the input object unchanged rather than copying it.

The pixel pass is run over two-pixel and forty-pixel bitmaps small enough to assert on by hand: brightness and contrast are checked against the arithmetic they claim to perform, including clamping at white; ink bleed must drag a near-black pixel further toward black and leave a paper-white one alone; grain must be identical across the three channels of a pixel, different between neighbouring pixels, and reproducible from a seed; vignette must darken by distance from the light and banding by row; a hard threshold must push either side of the cut further apart.

Canvas work is asserted through a recording context: an affine page draws the source once, a keystoned page draws one strip per four rows with no gap and no overrun, the blur filter is lifted before the dust is painted, each artifact appears only for the presets that ask for it, and a lossy preset asks the canvas for `image/jpeg` at the quality it named.

### Entry point

`app.test.js` boots the real entry point once against mocked DOM and library globals and drives every control: selection, the invoice-only dense toggle, seed rolling, the fitted scale, the full-size overlay (including that an export from inside it does not drag the page back to the frame), all three exports, a batch, the full 36-document cross product, and the missing-library path, which must surface a readable message and leave the button re-enabled.

It also drives the scan controls end to end: a slider per exposed setting is built at boot, pair mode is disabled while the preset is clean, choosing a preset swaps the note, and touching a knob flips the select to "custom" and updates its readout. **Preview scan** must capture the page, open the overlay with an image rather than the live page, and leave the page back in its frame on close. With a lossy preset and pair mode on, a single-page export must write the JPEG, the clean PNG, and one sidecar; a batch must do the same inside the archive, record the preset in the README, and emit a degradation block whose seed matches the page's own.

The single-test shape is deliberate. `app.js` is a module with side effects, so re-importing it per assertion would both re-run the bootstrap and split its coverage across cache-busted URLs.

### In a real browser

`tests/browser/test_frontend_apps_browser_flows.py` runs the app in Chromium against the real vendored libraries, which is the only place the produced files are known to be well-formed rather than merely requested:

- The fitted preview is asserted to have zero overflow in both axes and to hold the whole page inside the frame, which is the property the layout exists to provide.
- The overlay is asserted to take the live paper element, show it at exactly 794px, and hand it back on close.
- A text PDF and a rasterised PDF both start with `%PDF-`, with the rasterised one larger; the PNG carries a PNG signature; the batch ZIP starts with `PK`, contains exactly one PDF under `vendor/type/`, and that file is itself a real PDF.
- The statement is checked in the rendered page for negative balances and for a `$-` anywhere in the text.
- A page export writes two files, so the flow collects downloads through a standing listener and asserts on both. The sidecar is parsed and checked against the page it describes: the schema version, the vendor, a null `po_number` on a clean invoice, and the line amounts re-summed against the printed subtotal.
- With boxes on, the payload is asserted to declare `boxes_apply_to` as `["png", "pdf_raster"]`, report the page as 794x1123, and carry more than twelve regions all inside the unit square. Turning on word boxes must add a `words` array to every region.
- The batch ZIP is asserted to contain the page, its sidecar, a one-line `manifest.jsonl`, and a `README.txt`.
- `test_vendor_docs_generator_pdf_never_overprints_itself` instruments the real jsPDF, renders every vendor, type, and style across twelve seeds, and asserts no two drawn strings overlap and nothing lands off the page. The fake's text metrics are an approximation, so this is the only place the geometry is checked against the metrics that actually ship.
- `test_vendor_docs_generator_boxes_land_on_the_ink_they_name` is the answer to the question the Node box tests cannot ask. For all 42 combinations it renders the real page, converts every normalised box back to viewport coordinates, and calls `elementFromPoint` at the centre of it. Whatever is under that point must be the element carrying that exact `data-field`. It also re-checks every region's text against the sidecar in a real layout, and asserts every word box stays inside its region.

- `test_vendor_docs_generator_degraded_boxes_follow_the_ink` is the check that stops degradation quietly invalidating the boxes. It renders a real page, rasterises it through the real `html2canvas`, tilts it with geometry only (no grain or blur to blunt the measurement), and then counts dark pixels inside every transformed box against the ink still inside the box the DOM measured. Every transformed box has to sit on ink, and the transformed set has to cover measurably more of the tilted page's ink than the untransformed one. Replacing the transform with the identity makes nine regions land on blank paper, which is what the assertion is for.

The app is also covered by the shared per-app smoke and axe passes. Every colour the document prints is held above 4.5:1 against the paper by `vendors.test.js` (accents, ink on paper, and ink on its own soft fill), because axe only ever sees whichever vendor happens to be selected.

### Not covered by tests

Visual fidelity of the exported PDF and PNG is checked by eye rather than asserted.

Box coordinates for the **text-layer PDF** are not merely untested, they are not produced: `pdf-render.js` lays out in its own coordinate system and the payload says so in `boxes_apply_to`. Nothing stops someone applying DOM boxes to a text PDF anyway; the field is the only thing telling them not to.

Degradation is verified for geometry, determinism, and arithmetic, but whether a "bad fax" actually looks like a bad fax is a judgement made by eye through **Preview scan**, not an assertion. The strip approximation for keystone is argued to be sub-pixel rather than measured against a reference renderer.

The preview and the PDF still lay out independently: jsPDF positions in A4 points while the preview lays out in CSS pixels. They now agree on the vendor's font, alignment and monogram, but nothing asserts that the two renderings of a seed look alike, and a change to one will not fail a test because of the other.
