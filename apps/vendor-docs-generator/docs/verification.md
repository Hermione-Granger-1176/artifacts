# Verification

The Node tests are in `tests/js/apps/vendor-docs-generator/`. The support files there are `fake-dom.js`, `library-fakes.js`, and `app-test-support.js`. The browser tests run Chromium with the vendored libraries.

## Re-check

- Node tests: `make test-js`. Coverage thresholds from `package.json`: `make coverage-js`.
- Browser flows: `make test-browser-apps-flows ARGS="-k vendor_docs_generator"`.

Browser targets need Chromium. Run `make setup-playwright` once.

## Printed arithmetic

`document-model.test.js` recalculates expected values from the printed strings, not from the model's helpers. It checks these cases:

- Each printed line amount equals the quantity times the unit price, rounded to cents.
- Clean-invoice subtotal, per-line rounded tax, shipping, and grand total match the printed rows. Clean and dense layouts agree across vendors and seeds.
- Dense-invoice tax and line totals match both the table footer and the summary block.
- Amounts in words have the same cents as the numeric totals.
- Statement balances start at the printed opening balance and follow each charge and payment. Rows and the final banner stay nonnegative without a clamp.
- A receipt's subtotal plus tax plus shipping equals the amount due. The payment clears that amount, and the balance is zero.
- Challans report quantities and packages without a totals block. Remarks are distinct and include lot numbers.
- Price variation stays within 4% of the catalog price plus one rounding step. Monthly and yearly units use quantities from 1 to 3.
- Shipping is charged on goods, and it is zero on pages that list only services.

`format.test.js` checks that `roundCents` rounds each half cent away from zero, using the value's shortest decimal string. `522.295` gives `522.30`, and `-2.675` gives `-2.68`. Whole and two-decimal amounts pass through unchanged. The test compares `roundCents` with an exact BigInt reference at and next to every seventh half cent up to $20,000. `document-model.test.js` checks each line's 8.25% tax against integer-cent arithmetic for every amount below $10,000.

## Vendor variation and dates

For a shared seed, all vendors use the same buyer and issue date. Document numbers, item quantities, registration details, and statement ledgers vary by vendor.

Net-30 dates fall 30 days after issue. Quotation expiry falls 14 days after issue. Issue dates fall within the preceding 180 days. Statement periods end no later than the generation date, contain all ledger rows, and keep chronological order.

## Determinism

The same seed and reference date produce a deep-equal model. Different seeds produce different documents. Tests check reproducibility, that generated values fall in the open unit interval, and that seeds which would produce a fixed point are normalized.

## Sidecar fields

`annotations.test.js` covers every vendor, document type, and invoice layout. It checks these properties:

- Fields match `FIELD_KEYS` in order. Line items and ledger rows contain their full key sets.
- Present fields contain exactly `text` and `value`, with nonempty text. Absent fields are `null`.
- Clean invoices omit `po_number`, `buyer_phone`, and `vendor_company_reg`. Dense invoices print all three.
- Challans omit prices. Statements have transactions and no line items.
- Line amounts, subtotal, tax, shipping, and grand total agree to the cent.
- ISO dates match the printed calendar day. Money is numeric, and rates are fractions. Addresses keep their display line breaks only in `text`.
- Every rendered `[data-field]` value appears in its sidecar entry. A changed label or a formatting mismatch fails the test.

## Box coordinates

`annotate-boxes.test.js` uses a deterministic fake layout. It checks these cases:

- Each labeled node produces one region in document order, inside the normalized page bounds.
- Scaling all rectangles keeps the normalized boxes unchanged.
- Multiline addresses produce separate regions.
- Row fields use `line_items.<n>.<key>` or `transactions.<n>.<key>` paths.
- Blank cells produce no region.
- Requested word boxes stay within their regions and keep their baselines.
- A page with no rendered size, such as a hidden or detached page, throws an error. It writes no `[0, 0, 0, 0]` boxes. The app test shows the error in the status line and writes no file.

These tests do not show that boxes overlap the right text in a browser. The browser checks below do.

## HTML and PDF renderers

`paper-render.test.js` checks logo treatments, layout classes, alignment, emphasized rows, and rendered content. `pdf-render.test.js` records jsPDF calls and checks the letterhead, items, totals, vendor colors, fonts, table hooks, and pagination.

The PDF tests cover three regressions: a letterhead that overlaps the title, long metadata values that need their own line, and single-row banners whose default striping overrides their fill. Both renderers run across every vendor and document type combination. Real PDF text geometry needs the browser test.

## Exports and batches

`exporters.test.js` checks download anchors, deferred URL revocation, data URLs, and PDF aspect ratios. Text PDFs do not rasterize, and raster exports emit no text layer. The `planBatch` tests cover the vendor, type, and count cross product, unique seeds that wrap inside the seed range, and the dense-invoice mix.

Batch assertions cover folders, capture counts, progress, sidecars, `manifest.jsonl`, and `README.txt`:

- An unlabeled batch writes no sidecars, manifest, or README. A JSON batch contains only sidecars.
- A stopped batch keeps the finished documents and reports the cut. Stopping before the first document gives an empty archive, and the app skips the download.
- A long batch yields to the event loop, so a stop click can land.
- Estimates grow with the applicable raster, annotation, and pair settings. They ignore settings that produce no output.

A degraded export captures once and keeps the clean image for pair mode. Lossy scans use JPEG in rasterized PDFs and `.jpg` filenames. Pair mode writes the degraded image and a clean PNG. Manifests record the degradation settings. JSON-only batches do not claim clean-image pairs.

## Scan degradation

`degrade.test.js` checks preset completeness, slider ranges, seeded plans, and unchanged geometry when grain is disabled. Rotation varies within the preset bounds and uses both signs.

The geometry tests cover corner bounds, the fixed center of rotation, projective keystone, normalized matrices across capture scales, and `toPixelMatrix`. `transformBoxes` moves regions and words, adds the transformed corner quads, and derives their axis-aligned bounds. An identity transform returns the original object.

Small bitmap fixtures check brightness, contrast, clamping, ink bleed, seeded grain, vignette, banding, and thresholding. A recording canvas checks affine draws, four-pixel strips, blur order, preset-specific effects, and JPEG quality.

## Entry point and controls

`app.test.js` boots the entry point once, with mocked DOM and library globals. It covers selection, the invoice layout, new seeds, preview scale, dialog behavior, exports, batches, and readable errors for missing libraries.

The scan checks cover preset changes, fine-tune sliders, custom settings, pair availability, the scan preview, and export metadata.

## Real browser checks

`tests/browser/test_frontend_apps_browser_flows.py` (`-k vendor_docs_generator`) runs these checks:

- The preview fits without overflow. The dialog moves the live page, shows it at 794px wide, and returns it on close.
- The Output panel stays inside the window while the page scrolls, including in batch mode with the fine-tune sliders open. Below 1000px the toolbar, page, and panel stack. Below 700px the document-type dropdown replaces the pills.
- PDF, PNG, and ZIP downloads have valid signatures. ZIP paths contain the expected document files.
- Statements show no negative balances.
- Sidecars match the schema, the vendor, the printed subtotal, and the absent clean-invoice fields.
- Boxes declare `boxes_apply_to` as `["png", "pdf_raster"]`, use a 794x1123 page, and stay within normalized bounds. Word boxes appear when requested.
- Labeled batches contain the page, sidecar, manifest, and README.
- `test_vendor_docs_generator_batch_can_be_stopped_mid_run` starts a 900-document text-PDF batch and clicks **Stop and keep what is done**. It checks the `_partial.zip` name, the status line, the matching sidecar and manifest counts, and the README's planned count.
- `test_vendor_docs_generator_pdf_never_overprints_itself` instruments real jsPDF output across vendors, types, layouts, and seeds. Text rectangles do not overlap or leave the page.
- `test_vendor_docs_generator_boxes_land_on_the_ink_they_name` uses `elementFromPoint` to check each region against its marked DOM node. It also checks the region text and word bounds in the real layout.
- `test_vendor_docs_generator_degraded_boxes_follow_the_ink` counts dark pixels after a geometric transform. The transformed boxes must cover more of the shifted text than the original boxes.

The shared smoke and axe suites also cover this app. `vendors.test.js` checks that each accent keeps at least 4.5:1 contrast against the white text printed on it. It also checks that each vendor ink stays legible on paper and on its soft fill, the fictional phone and email ranges, and the flat sales-tax rate. `random.test.js` and `format.test.js` cover the seeded generator, the money and date helpers, and the amount-in-words text.

## Coverage limits

Visual fidelity of exported PDF and raster images needs manual review. The DOM and PDF layouts use independent coordinate systems. Tests do not assert that the two images look identical.

Text-layer PDF boxes are not produced. `boxes_apply_to` records that limit. Consumers must use DOM boxes only with the listed raster outputs.

Tests cover degradation geometry, determinism, and arithmetic. The appearance of presets such as **bad fax** is reviewed through **Preview scan**. No reference renderer measures the keystone strip approximation error.
