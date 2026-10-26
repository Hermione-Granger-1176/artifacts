# Frontend reference

## Root gallery entry points

- `index.html` loads the root gallery shell
- `css/src/` contains ordered self-hosted font declarations, gallery styling, shared app tokens, shared shell styling, reusable app components, utilities, and responsive rules. `make styles` bundles them into the public `css/style.css` asset. Each mature app keeps only app-specific composition and layout selectors in `apps/<slug>/css/app.css`, scoped by its body class.
- `js/gallery-config.js` provides generated tool/tag labels, display order, and the shared artifact path contract from `config/gallery_metadata.json` and `config/artifact_contract.json`
- `js/data.js` provides generated artifact metadata
- `js/app.js` bootstraps the runtime, validates generated bootstrap data, and calls `initializeGalleryApp`

## Shared app system

- `css/src/01-theme-light.css` and `css/src/01-theme-dark.css` own every themed color, line for line. In dark mode the desk turns graphite and the scrapbook keeps its daytime paper, card colors, and pencil. Those include the `body.artifact-app` hue colors with their `-text` and `-emphasis` variants, note pastels, surfaces, borders, and `--shadow-card`. `css/src/01-tokens.css` owns the tokens that stay the same in both themes: fonts, the bookmark-note palette, the printed-document palette, and the `body.artifact-app` type scale, spacing scale, and radii. The remaining ordered `css/src/` partials own root gallery styling, app shell styling, reusable components, utilities, and responsive behavior
- `css/src/04-artifact-components.css` is the shared artifact component layer: reusable `body.artifact-app` families such as `.control-field`, `.stat-grid` / `.stat`, `.chip`, `.segmented`, `.meter`, `.app-callout`, `.section-kicker`, buttons, inputs, tables, code windows, and `.section-nav`. Apps compose these rather than restating them
- `apps/<slug>/css/app.css` owns app-specific dimensions, grids, visualizations, and component variants, while reusable colors, controls, surfaces, and callouts stay in the shared stylesheet. It keeps the `body.app-<slug>` selector scope
- `js/app-theme.js` applies the saved mature-app theme before CSS loads
- `js/modules/app-shell.js` owns runtime theme toggling, back-button fallback behavior, and scroll-to-top behavior for app pages
- Mature app pages import `../../css/style.css` first and `./css/app.css` second, use `artifact-app` plus an `app-<slug>` body class, and keep app-local JavaScript inside `apps/<slug>/`

## JavaScript module responsibilities

The gallery modules divide responsibilities by feature.

The gallery modules under `js/modules/gallery/` are:

- `js/modules/gallery/gallery-app.js`: DOM wiring, event handlers, URL state, filtering, pagination, theme behavior, and book-scene integration
- `js/modules/gallery/catalog.js`: pure catalog helpers for search text, selection normalization, sorting, and pagination math
- `js/modules/gallery/config.js`: bootstrap data validation, generated config hydration, and label helpers
- `js/modules/gallery/detail-overlay.js`: detail panel lifecycle, open/close animation, and focus trapping (lazily loaded via dynamic import on first use)
- `js/modules/gallery/icons.js`: shared inline SVG icon markup
- `js/modules/gallery/inert.js`: background element inert/interactive toggling for overlay accessibility
- `js/modules/gallery/motion.js`: reduced-motion-aware scroll and animation helpers
- `js/modules/gallery/book-scene.js`: scrapbook cover intro, page turns (by button or by dragging a page), and the queue for page requests
- `js/modules/gallery/render.js`: HTML generation and DOM sync helpers for cards, detail content, desk-note filters, and pagination
- `js/modules/gallery/gallery-url.js`: URL state sync for gallery search, filters, and sort

The shared modules under `js/modules/` are:

- `js/modules/runtime.js`: startup status, error reporting, and guarded localStorage access
- `js/modules/app-runtime.js`: mature-app bootstrap with fatal error handling
- `js/modules/element-cache.js`: DOM element caching by ID
- `js/modules/app-shell.js`: runtime theme toggling, back-button fallback behavior, and scroll-to-top behavior for app pages
- `js/modules/html-escape.js`: `escapeHtml()` and `escapeAttribute()` helpers; the gallery `render.js` re-exports `escapeHtml()`, and app modules import the helpers they need directly
- `js/modules/formatting.js`: shared number formatting and parsing helpers (`formatCurrency()`, `formatPercent()`, `formatCompact()`, `formatDollarTick()`, `parseNumber()`), imported directly by app modules
- `js/modules/segmented.js`: `initSegmented()` wiring for segmented toggles, keeping the lone `.active` button and `aria-pressed` state in sync and calling back with the newly active button
- `js/modules/section-nav.js`: sticky section-progress nav (`initSectionNav()`, `renderSectionNav()`, `scrollToSection()`) with numbered nodes, a progress fill, and a scroll spy. Section tops are measured only when the layout changes, and each section becomes active when its top reaches a scanline at 35% of the viewport; sections the page cannot scroll that far split the last stretch of scrolling into equal shares, the final one included, so it is active before the bottom and stays active down to it. One progress number (the active section plus the way to the next) drives the nodes, the label, and a fill that runs node center to node center, styled by the shared `.section-nav` component rules. Sections are discovered from elements carrying an id plus a `data-nav-label` attribute, in document order; `initSectionNav()` also accepts an explicit `{ id, label }` list for callers that need one
- `js/modules/chart-theme.js`: theme-aware Chart.js helpers (`chartGlobal()` vendor global access, `cssValue()` / `cssAlpha()` custom property reads, `isDark()`, and `createPaletteCache()` per-theme palette caching) used by the chart-based apps
- `js/modules/frame-scheduler.js`: `createFrameScheduler()`, which coalesces repeated requests (such as slider input) into one callback on the next animation frame

The root filter UI is rendered as desk notes by `buildFilterNotes()` in `js/modules/gallery/render.js` and toggled in `js/modules/gallery/gallery-app.js`. At 900px or narrower the desk notes are hidden and `#filter-dropdowns` shows one multi-select dropdown per filter group, built by `buildFilterDropdowns()` from a list of groups, so a new group is one more entry. Each is a note button that counts its picks (in its label and its accessible name) and opens a native modal `<dialog>` checklist on the bottom edge of the screen: options carry the desk notes' colors and the number of artifacts that use them, picked options move to the top when the panel opens, a list longer than eight options gets a search box, and Clear resets that group. Options filter the gallery live through the same handler as the desk notes. Widening past 900px closes an open panel. On these screens the toolbar is centred: the search note on its own row, then the dropdowns and the sort note on a row under it. The reset note stays on the desk layout, because each panel clears its own group and the search clears itself.

## Search and sort

The search field appears above the book, beside sort and reset controls. `#search-count` shows the number of matches during a search. `#gallery-status` announces that result to screen readers. The `/` shortcut focuses the search field.

`.sort-toggle::after` supplies the visible label, "newest" or "oldest". The accessible button name includes the same label.

## Book scene

The gallery uses a post-bound scrapbook layout. Its closed cover includes a ribbon, binding posts, tabs, a title note, doodles, and placeholder snapshots. `--color-album-*` tokens define cover colors, and `assets/scrapbook/` contains the images.

The endpaper, settled pages, and turning leaf faces share the same ruled-paper pattern. `getAttachmentData()` in `render.js` selects tape, clips, or photo corners from the artifact ID, keeping each card's attachment consistent.

### Cover introduction

`startIntro()` releases the ribbon and starts the cover turn before the ribbon animation finishes. The cover rotates 180 degrees around the spine while the book moves to its centered-open position.

The left page stays hidden until the cover lands. The inside cover contains a copy of the first left page. After landing, the live page replaces that copy without a fade or position change.

### Page turns and requests

A turning leaf has two faces and matches the settled page dimensions. Its front shows the source page, its back shows the destination page, and the page underneath already contains destination content.

Dragging an outer edge or bottom corner moves the leaf with the pointer. Releasing beyond `DRAG_COMPLETE_THRESHOLD` (45%) completes the turn. An earlier release returns the leaf to its starting position. `.book-sheet` uses `touch-action: pan-y pinch-zoom` so horizontal drags turn pages while vertical scrolling and zoom remain available.

**Prev**, **Next**, and page-number requests share one queue. After the current transition, the queue uses the latest requested page. A request made during a drag remains selected after that drag ends.

Search, filter, sort, and history changes call `renderContent()`, which cancels an active turn before rendering. Completed, canceled, and failed animations remove temporary leaves and inline styles. The fallback listener on `#book-sheet` replaces broken thumbnails on turning leaves with the grid's placeholder.

Reduced-motion mode uses short cross-fades instead of 3D turns.

### Viewport fit

Above 900px wide, the open book fits the viewport height. `--book-chrome-y` reserves space for the header, search, and pagination. Book height stays between `--book-fit-min-height` (460px) and `--book-sheet-min-height` (800px).

`--book-spread-ratio` scales width with height to preserve page proportions. At viewport heights of 900px or less, header and control spacing shrink and desk notes become smaller. Captions scale with book width. A page turn that starts with the book's top above the screen scrolls it back into view.

### Notepad (900px and narrower)

Phones and tablets held upright get a one-page notepad bound at the top instead of the two-page book. `NOTEPAD_QUERY` in `book-scene.js` holds the breakpoint for both scripts, and must agree with the `max-width: 900px` notepad block in `css/src/06-responsive-and-motion.css`. The book scene listens for that query's `change` event, so only crossing the breakpoint ends an animation in flight.

- Each page holds one artifact (`NOTEPAD_ITEMS_PER_PAGE`): its photo, then the `.card-notes` under it, with the description written on the ruled lines and an open link. The book hides the notes and keeps them in the detail overlay. Crossing the breakpoint keeps the reader on the page that holds the first artifact they were looking at.
- The notepad fills the screen height below the search (`--notepad-chrome-y`). `.book-spine` becomes the wire binding, and the bottom edge shows one sliver per page still to come, from `--stack-right-n`.
- Pages flip like a desk calendar. `playFlipTurn()` swings a two-faced copy of a page on its top edge (a positive `rotateX` to 180 degrees, `FLIP_KEYFRAMES`): forward, the old page's bottom edge lifts toward the reader, the sheet swings up over the binding showing its plain back, and the back fades as it drops behind the pad (`FLIP_BACK_FADE_KEYFRAMES`), uncovering the next page, which is already rendered underneath. Back plays the same animation in reverse with the earlier page, which then takes the shown page's place. The flip is Web Animations on `transform` and `opacity` only, so the compositor runs it without a frame loop on the main thread. The leaf keeps its faces in 3D (`transform-style: preserve-3d`) and each face hides by `backface-visibility` when it turns away, so the leaf itself never animates `opacity`, which would flatten its faces. The sheet is drawn flat (`transform-style: flat`), so the cover and the leaf always paint over the page while `perspective` on the sheet and page still gives them depth.
- The intro slides the cover band down off the bottom edge, like an elastic closure, then turns the cover up over the binding with the same keyframes, showing its inside past upright (`playFlipIntro()`).
- A vertical swipe on the sheet turns the page: up for next, down for previous (`SWIPE_MIN_PX`). The sheet sets `touch-action: pan-x pinch-zoom` so those swipes reach the page. Phones on their side get the photo beside its notes and keep normal scrolling, so the arrows turn the page there.
- The toolbar is the centred one from the filter dropdowns above, and the pager is the previous and next arrows around `.page-counter`.

Interaction modules use guard clauses and lookup maps to separate event paths.


Invalid generated bootstrap data stops startup before gallery initialization. The runtime displays the error banner and reports the error globally.

## Test coverage

- `tests/js/home/`: root gallery tests such as bootstrap wiring, catalog helpers, overlay behavior, rendering, keyboard flows, and home-page runtime coverage
- `tests/js/common/`: shared app-system tests for runtime helpers, app shell behavior, theme bootstrap, motion helpers, inert handling, and element caching
- `tests/js/apps/bond-price-vs-rate/`: app-specific entry, pricing-math, and rendering coverage for the bond price vs rate app
- `tests/js/apps/loan-amortization/`: app-specific entry, DOM, and module coverage for the loan amortization app
- `tests/js/apps/prompt-caching/`: app-specific entry, DOM, and module coverage for the prompt caching app
- `tests/js/apps/tokenizer-explorer/`: app-specific entry and module coverage for the tokenizer explorer app
- `tests/js/apps/vendor-docs-generator/`: app-specific entry, document-model, annotation, degradation, rendering, and exporter coverage for the vendor docs generator app
- `tests/js/tooling/`: Node tests for JavaScript-based lint and maintenance tooling
- `tests/js/workflows/`: Node tests for the `deploy-site` and `verified-commit` GitHub composite-action modules
- `tests/browser/test_frontend_smoke.py`: browser smoke coverage for gallery load, invalid bootstrap data, search, desk-note filters, pagination, detail overlay, and `404.html`
- `tests/browser/test_frontend_accessibility.py`: Playwright + axe coverage for root light/dark themes, overlay state, no-results state, and `404.html`, plus explicit contrast assertions
- `tests/browser/test_frontend_browser_flows.py`: keyboard-only, mobile, reduced-motion, theme persistence, larger-catalog, and book-scene coverage (centered open book, leaf geometry, rapid turns, completed and sprung-back drags, laptop fit)
- `tests/browser/test_frontend_apps_smoke.py`: real app smoke coverage for mature app folders that opt into the shared app system
- `tests/browser/test_frontend_apps_accessibility.py`: Playwright + axe coverage for mature app shared-shell accessibility and contrast
- `tests/browser/test_frontend_apps_browser_flows.py`: mature app browser-flow coverage for app-specific interactions and theme behavior; each flow test skips when its app slug is outside `ARTIFACTS_BROWSER_APP_SLUGS`
- `tests/browser/test_frontend_webkit_smoke.py`: bounded WebKit cross-engine smoke coverage for the root gallery and every mature app entry page
- `tests/browser/test_frontend_visual.py`: local fixed-viewport visual baseline comparisons for the root gallery and mature app hero states; this suite is intentionally not part of blocking CI
- `tests/browser/test_frontend_live.py`: post-deploy browser verification for the published root and `404.html` when `ARTIFACTS_LIVE_SITE_URL` is set

## Accessibility notes for the root shell

- The root shell keeps keyboard focus visible across search, desk-note filters, pagination, overlay close/return, and the scroll-to-top control.
- `js/modules/gallery/gallery-app.js` keeps the theme toggle stateful with `aria-pressed`, updates the toggle label for the next theme, and announces result/theme changes through a dedicated live region.
- Artifact cards render as real `<button>` controls so keyboard and screen-reader semantics match the interaction model instead of relying on `role="button"` shims.
- `js/modules/gallery/render.js` gives the detail description a stable ID, and `js/modules/gallery/detail-overlay.js` uses it to describe the dialog while artifact links announce that they open in a new tab.
- `404.html` has explicit focus-visible styling so fallback navigation is keyboard-safe even outside the main app shell.
- `css/src/01-tokens.css` owns focus ring tokens. The relevant component, utility, and responsive partials own skip-link behavior and accessible contrast tuning for active pagination and detail CTA states.
- `tests/browser/frontend_helpers.py` fails browser suites on `pageerror`, unexpected `console.error`, failed requests, and HTTP 4xx/5xx responses, and can emit screenshots, traces, and runtime logs for CI artifacts.

## Local and CI checks

- Use [operations.md](operations.md) as the canonical workflow reference; the targets below are the frontend-specific checkpoints you will use most often.
- `make test-js` runs the JavaScript unit suite with Node's built-in test runner across `tests/js/home/`, `tests/js/common/`, `tests/js/apps/`, `tests/js/tooling/`, and `tests/js/workflows/`
- `make coverage-js` uses Node's built-in experimental coverage report, which covers all source files imported by tests while excluding `node_modules/` and `tests/`. Thresholds and exclusions are configured in `package.json`
- `make check-local` runs the non-browser local gate: formatting, linting, dead-code checks, non-browser Python tests, JavaScript unit tests, JavaScript source-to-test coverage lint, JavaScript coverage, dependency audits, artifact validation, and canonical generated-file drift checks
- `make test-browser-root` runs all root-gallery Playwright suites
- `make test-browser-root-smoke`, `make test-browser-root-accessibility`, and `make test-browser-root-flows` run the root smoke, accessibility, and browser-flow suites separately
- `make test-browser-apps` runs all mature app Playwright suites; set `ARTIFACTS_BROWSER_APP_SLUGS` to limit coverage to specific app slugs
- `make test-browser-apps-smoke`, `make test-browser-apps-accessibility`, and `make test-browser-apps-flows` run the mature app smoke, accessibility, and browser-flow suites separately
- `make test-browser-webkit-smoke` runs the bounded WebKit smoke pass across the root gallery and all mature apps; prepare WebKit with `make setup-playwright-webkit` first, or use the local runtime instructions in [operations.md](operations.md#browser-setup-without-sudo)
- `make check-web` runs both root and app browser suites plus thumbnail generation; use `make setup-all` first so Chromium is available
- `make test-visual` compares committed hero baselines, while `make visual-baselines` regenerates them after an intentional visual change; both are local, on-demand checks rather than blocking CI gates
- `make check` runs the full local release gate by combining `make check-local`, `make check-web`, index generation, and deployable site assembly
- `make test-browser` sets `ARTIFACTS_REQUIRE_BROWSER_TESTS=1`, so root and mature app browser suites must execute successfully instead of skipping when Chromium is unavailable
- `make test-browser-live` runs the published-site Playwright verification suite when `ARTIFACTS_LIVE_SITE_URL` is set
- The workspace uses Node's built-in coverage report. It has no Istanbul or nyc instrumentation dependencies
