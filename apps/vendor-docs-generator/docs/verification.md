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

The same options rebuild a deep-equal model; different seeds produce different documents. The seeded generator is checked for reproducibility, for staying inside the open unit interval over 500 draws, and for normalising the seeds (`0`, the modulus) that would otherwise make it a fixed point.

### Renderers

`paper-render.test.js` renders into a fake DOM and asserts on the tree: all six logo treatments, the layout classes, per-column alignment, the emphasised totals row matching `emphasisIndex`, the dense-invoice grid and table footer, and that re-rendering replaces the page rather than stacking pages. It also asserts vendor branding arrives through `style.setProperty` rather than an inline style attribute, which is the property CSP depends on.

`pdf-render.test.js` renders into a recording jsPDF fake and asserts the text layer contains the letterhead, every line item, and the totals; that the accent bar is filled with the vendor's colour; that the `didParseCell` hooks emphasise exactly the rows the model marked; and that a page too short for the content spills onto a second page.

It also guards the three faults this renderer shipped. The letterhead and the title are asserted not to overlap for any vendor, type, or style, reconstructing both boxes from the sizes actually used, since the title shrinks to fit and the monogram tile shifts the name right. A long meta value is asserted to drop to its own line rather than overprint its label, with the test requiring that at least one seed in the sweep actually exercises the wrapping branch. The banner and callout are asserted to carry `theme: "plain"`: under the default striped theme, `alternateRowStyles` resolves to 245 on row index 0 and outranks both `styles` and `bodyStyles`, so those single-row tables painted flat grey and the statement's balance due printed white on near-white. That precedence was measured through `didParseCell`, not assumed. Each vendor is also asserted to letterhead in its own font family, which the PDF ignored entirely until now.

Both renderers are run across all 36 vendor/type combinations.

### Exports

`exporters.test.js` covers the download anchor lifecycle (attached before click, revoked on a later tick, data URLs passed through unrevoked), the aspect-ratio maths in `canvasToPdf`, and that the text-PDF path never rasterises while the image path never emits a text layer. Batch runs are asserted on ZIP folder structure, base64 PNG entries, capture counts per format, and progress reporting.

### Entry point

`app.test.js` boots the real entry point once against mocked DOM and library globals and drives every control: selection, the invoice-only dense toggle, seed rolling, the fitted scale, the full-size overlay (including that an export from inside it does not drag the page back to the frame), all three exports, a batch, the full 36-document cross product, and the missing-library path, which must surface a readable message and leave the button re-enabled.

The single-test shape is deliberate. `app.js` is a module with side effects, so re-importing it per assertion would both re-run the bootstrap and split its coverage across cache-busted URLs.

### In a real browser

`tests/browser/test_frontend_apps_browser_flows.py` runs the app in Chromium against the real vendored libraries, which is the only place the produced files are known to be well-formed rather than merely requested:

- The fitted preview is asserted to have zero overflow in both axes and to hold the whole page inside the frame, which is the property the layout exists to provide.
- The overlay is asserted to take the live paper element, show it at exactly 794px, and hand it back on close.
- A text PDF and a rasterised PDF both start with `%PDF-`, with the rasterised one larger; the PNG carries a PNG signature; the batch ZIP starts with `PK`, contains exactly one file under `vendor/type/`, and that file is itself a real PDF.
- The statement is checked in the rendered page for negative balances and for a `$-` anywhere in the text.
- `test_vendor_docs_generator_pdf_never_overprints_itself` instruments the real jsPDF, renders every vendor, type, and style across twelve seeds, and asserts no two drawn strings overlap and nothing lands off the page. The fake's text metrics are an approximation, so this is the only place the geometry is checked against the metrics that actually ship.

The app is also covered by the shared per-app smoke and axe passes. Every colour the document prints is held above 4.5:1 against the paper by `vendors.test.js` (accents, ink on paper, and ink on its own soft fill), because axe only ever sees whichever vendor happens to be selected.

### Not covered by tests

Visual fidelity of the exported PDF and PNG is checked by eye rather than asserted.

The preview and the PDF still lay out independently: jsPDF positions in A4 points while the preview lays out in CSS pixels. They now agree on the vendor's font, alignment and monogram, but nothing asserts that the two renderings of a seed look alike, and a change to one will not fail a test because of the other.
