# Verification

Node tests live in `tests/js/apps/vendor-docs-generator/`. `fake-dom.js`, `library-fakes.js`, and `app-test-support.js` provide test support. `make coverage-js` reports coverage and checks the thresholds in `package.json`.

## Printed arithmetic

`document-model.test.js` recalculates expected values from printed strings rather than calling the model's calculation helpers. Its assertions cover these cases:

- Each printed line amount equals quantity times unit price, rounded to cents.
- Clean-invoice subtotal, per-line rounded tax, and grand total match the printed rows. Clean and dense layouts agree across vendors and seeds.
- Dense-invoice tax and line totals match both the table footer and summary block.
- Amounts in words have the same cents as numeric totals.
- Statement balances start at the printed opening balance and follow each charge and payment. Individual rows and the final banner remain nonnegative without a clamp.
- Receipt subtotal plus tax equals the amount due, payment clears that amount, and balance equals zero.
- Challans report quantities and packages without a totals block. Remarks are distinct and include lot numbers.
- Price variation stays within 4% of the catalog price plus one rounding step. Subscription quantities use 1-3 units.

## Vendor variation and dates

For a shared seed, all vendors use the same buyer and issue date. Document numbers, item quantities, registration details, and statement ledgers vary by vendor.

Net-30 dates are 30 days after issue, and quotation expiry is 14 days after issue. Issue dates are within the preceding 180 days. Statement periods end no later than the generation date, contain all ledger rows, and preserve chronological order.

## Determinism

The same seed and reference date produce a deep-equal model. Different seeds produce different documents. Tests check reproducibility, values inside the open unit interval, and normalization of seeds that would otherwise produce a fixed point.

## Sidecar fields

`annotations.test.js` covers every vendor, document type, and invoice layout. It checks these schema properties:

- Fields match `FIELD_KEYS` in order. Line items and ledger rows contain their full key sets.
- Present fields contain exactly `text` and `value`, with nonempty text. Absent fields are `null`.
- Clean invoices omit `po_number`, `buyer_phone`, and `vendor_company_reg`. Dense invoices print all three.
- Challans omit prices. Statements have transactions and no line items.
- Line amounts, subtotal, tax, shipping, and grand total agree to the cent.
- ISO dates represent the printed calendar day. Money is numeric, rates are fractions, and addresses preserve display line breaks only in `text`.
- Every rendered `[data-field]` value appears in its sidecar entry. A changed label or formatting mismatch fails the test.

## Box coordinates

`annotate-boxes.test.js` uses a deterministic fake layout. It checks traversal and coordinate calculations, including these cases:

- Each labeled node produces one region in document order inside normalized page bounds.
- Scaling all rectangles preserves normalized boxes.
- Multiline addresses produce separate regions.
- Row fields use `line_items.<n>.<key>` or `transactions.<n>.<key>` paths.
- Blank cells produce no region.
- Requested word boxes stay within their regions and preserve their baselines.
- An unlaid-out page produces finite coordinates.

These tests do not prove that boxes overlap the correct text in a real browser. The browser tests below cover that behavior.

## HTML and PDF renderers

`paper-render.test.js` checks logo treatments, layout classes, alignment, emphasized rows, and rendered content. `pdf-render.test.js` records jsPDF calls and checks the letterhead, items, totals, vendor colors, fonts, table hooks, and pagination.

PDF regressions include overlapping letterhead and title, long metadata values that need a separate line, and single-row banners whose default striping could override their fill. Both renderers run across vendor and document-type combinations. Real PDF text geometry requires the browser test.

## Exports and batches

`exporters.test.js` checks download anchors, deferred URL revocation, data URLs, and PDF aspect ratios. Text PDFs do not rasterize, and raster exports do not emit a text layer.

Batch assertions cover folders, capture counts, progress, sidecars, `manifest.jsonl`, and `README.txt`. JSON batches contain only sidecars. Estimates increase with applicable raster, annotation, and pair settings and ignore settings that produce no output.

A degraded export captures once and retains the clean image for pair mode. Lossy scans use JPEG in rasterized PDFs and `.jpg` filenames. Pair mode writes the degraded image and clean PNG. Manifests record degradation settings, and JSON-only batches do not claim to contain clean-image pairs.

## Scan degradation

`degrade.test.js` checks preset completeness, slider ranges, seeded plans, and unchanged geometry when grain is disabled. Rotation varies within preset bounds and uses both signs.

Geometry tests cover corner bounds, the fixed center of rotation, projective keystone, normalized matrices across capture scales, and `toPixelMatrix`. `transformBoxes` moves regions and words, adds transformed corner quads, and derives their axis-aligned bounds. An identity transform returns the original object.

Small bitmap fixtures check brightness, contrast, clamping, ink bleed, seeded grain, vignette, banding, and thresholding. A recording canvas checks affine draws, four-pixel strips, blur order, preset-specific effects, and JPEG quality.

## Entry point and controls

`app.test.js` boots the entry point once with mocked DOM and library globals. It covers selection, invoice layout, new seeds, preview scale, dialog behavior, exports, batches, and readable errors for missing libraries.

Scan checks cover preset changes, fine-tune sliders, custom settings, pair availability, scan preview, and export metadata. The app is imported once because repeated side-effectful imports would rerun bootstrap and divide coverage across module URLs.

## Real browser checks

`tests/browser/test_frontend_apps_browser_flows.py` runs Chromium with the real vendored libraries. It checks the following behavior:

- The preview fits without overflow. The dialog moves the live page, displays it at 794px wide, and returns it on close.
- PDF, PNG, and ZIP downloads have valid signatures. ZIP paths contain the expected document files.
- Statements show no negative balances.
- Sidecars match the schema, vendor, printed subtotal, and absent clean-invoice fields.
- Boxes declare `boxes_apply_to` as `["png", "pdf_raster"]`, use a 794x1123 page, and remain within normalized bounds. Word boxes appear when requested.
- Labeled batches contain the page, sidecar, manifest, and README.
- `test_vendor_docs_generator_pdf_never_overprints_itself` instruments real jsPDF output across vendors, types, layouts, and seeds. Text rectangles do not overlap or leave the page.
- `test_vendor_docs_generator_boxes_land_on_the_ink_they_name` uses `elementFromPoint` to check each region against its marked DOM node. It also checks region text and word bounds in real layout.
- `test_vendor_docs_generator_degraded_boxes_follow_the_ink` counts dark pixels after a geometric transform. Transformed boxes must cover more of the shifted text than the original boxes.

Shared app smoke and axe suites also cover this app. `vendors.test.js` checks that each printed vendor color maintains at least 4.5:1 contrast against its background.

## Coverage limits

Visual fidelity of exported PDF and raster images requires manual review. DOM and PDF layouts use independent coordinate systems, and tests do not assert that the two images look identical.

Text-layer PDF boxes are not produced. `boxes_apply_to` records that limit. Consumers must use DOM boxes only with the listed raster outputs.

Tests cover degradation geometry, determinism, and arithmetic. The appearance of presets such as **bad fax** is reviewed through **Preview scan**. No reference renderer measures keystone strip approximation error.
