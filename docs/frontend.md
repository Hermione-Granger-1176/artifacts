# Frontend reference

## Root gallery entry points

- `index.html` loads the root gallery shell
- `css/src/` contains ordered self-hosted font declarations, gallery styling, shared app tokens, shared shell styling, reusable app components, utilities, and responsive rules. `make styles` bundles them into the public `css/style.css` asset. Each mature app keeps only app-specific composition and layout selectors in `apps/<slug>/css/app.css`, scoped by its body class.
- `js/gallery-config.js` provides generated tool/tag labels, display order, and the shared artifact path contract from `config/gallery_metadata.json` and `config/artifact_contract.json`
- `js/data.js` provides generated artifact metadata
- `js/app.js` bootstraps the runtime, validates generated bootstrap data, and calls `initializeGalleryApp`. Invalid bootstrap data stops startup before gallery initialization, and the runtime shows the error banner and reports the error globally
- `js/boot-guard.js` is a classic script that runs before the module. If `data-runtime-status` on `<html>` is still not `ready` or `error` after 8 seconds (`DEFAULT_TIMEOUT_MS`), it shows `#runtime-error` with a load-failure message, so a failed module download leaves a visible error instead of an empty grid

## Shared app system

- `css/src/01-theme-light.css` and `css/src/01-theme-dark.css` own every themed color, line for line. They hold the `body.artifact-app` hue colors with their `-text` and `-emphasis` variants, the note pastels, surfaces, borders, and `--shadow-card`. In dark mode the desk turns graphite, and the scrapbook keeps its daytime paper, card colors, and pencil
- `css/src/01-tokens.css` owns the tokens that stay the same in both themes: fonts, the bookmark-note palette, the printed-document palette, and the `body.artifact-app` type scale, spacing scale, and radii. The remaining ordered `css/src/` partials own root gallery styling, app shell styling, reusable components, utilities, and responsive behavior
- `css/src/04-artifact-components.css` is the shared artifact component layer: reusable `body.artifact-app` families such as `.control-field`, `.stat-grid` / `.stat`, `.chip`, `.segmented`, `.meter`, `.app-callout`, `.section-kicker`, buttons, inputs, tables, code windows, and `.section-nav`. Apps compose these rather than restating them
- `apps/<slug>/css/app.css` owns app-specific dimensions, grids, visualizations, and component variants, while reusable colors, controls, surfaces, and callouts stay in the shared stylesheet. It keeps the `body.app-<slug>` selector scope
- `js/app-theme.js` applies the saved mature-app theme before CSS loads
- Mature app pages import `../../css/style.css` first and `./css/app.css` second, use `artifact-app` plus an `app-<slug>` body class, and keep app-local JavaScript inside `apps/<slug>/`

## JavaScript module responsibilities

The gallery modules divide responsibilities by feature.

The gallery modules under `js/modules/gallery/` are:

- `js/modules/gallery/gallery-app.js`: DOM wiring, event handlers, URL state, filtering, filter dropdowns, pagination, page size, the notepad swipe, theme behavior, and book-scene integration
- `js/modules/gallery/catalog.js`: pure catalog helpers for search text, selection normalization, sorting, and pagination math
- `js/modules/gallery/config.js`: bootstrap data validation, generated config hydration, and label helpers
- `js/modules/gallery/detail-overlay.js`: detail panel lifecycle, open/close animation, and focus trapping (imported dynamically on the first card click or the first pointer entry into the grid)
- `js/modules/gallery/icons.js`: shared inline SVG icon markup
- `js/modules/gallery/inert.js`: background element inert/interactive toggling for overlay accessibility
- `js/modules/gallery/motion.js`: the reduced-motion check and the scroll helpers that respect it
- `js/modules/gallery/book-scene.js`: the cover intro, page turns (a leaf for the book, a flip for the notepad), page drags, and the queue for page requests
- `js/modules/gallery/render.js`: HTML generation for cards, detail content, desk-note filters, filter dropdowns, and pagination
- `js/modules/gallery/gallery-url.js`: reads and writes the `q`, `tool`, `tag`, `sort`, and `page` URL parameters

The shared modules under `js/modules/` are:

- `js/modules/runtime.js`: startup status, error reporting, and guarded localStorage access
- `js/modules/app-runtime.js`: mature-app bootstrap with fatal error handling
- `js/modules/element-cache.js`: DOM element caching by ID
- `js/modules/app-shell.js`: `renderAppShell()` fills the `data-app-shell` slots with the shared header, runtime-error banner, and scroll-to-top control. `initAppShell()` wires theme toggling, the back button (with a fallback when the referrer is not a same-origin page), and scroll-to-top
- `js/modules/html-escape.js`: `escapeHtml()` and `escapeAttribute()`. The gallery `render.js` re-exports `escapeHtml()`, and app modules import the helpers they need directly
- `js/modules/dom-sync.js`: `setText()` and `setAttr()`, which write to the DOM only when the value changed, and `createElement()`, which builds an element with its class, text, attributes, and children
- `js/modules/meter.js`: `setMeterValue()` fills a `.meter-fill` through its `scale` property, so a change needs no layout
- `js/modules/formatting.js`: shared number formatting and parsing helpers (`formatCurrency()`, `formatPercent()`, `formatCompact()`, `formatDollarTick()`, `parseNumber()`), imported directly by app modules
- `js/modules/segmented.js`: `initSegmented()` wiring for segmented toggles, keeping the lone `.active` button and `aria-pressed` state in sync and calling back with the newly active button
- `js/modules/section-nav.js`: sticky section-progress nav (`initSectionNav()`, `renderSectionNav()`, `scrollToSection()`) with numbered nodes, a progress fill, and a scroll spy. `initSectionNav()` discovers sections from elements that carry an id and a `data-nav-label` attribute, in document order, or takes an explicit `{ id, label }` list. It measures section tops only when the layout changes. A section becomes active when its top reaches a scanline at 35% of the viewport height. Sections the page cannot scroll that far share the last stretch of scrolling equally, the final one included, so the last section is active before the bottom and stays active down to it. One progress number (the active section plus the way to the next) drives the nodes, the label, and a fill that runs from node center to node center, styled by the shared `.section-nav` component rules
- `js/modules/chart-theme.js`: theme-aware Chart.js helpers (`chartGlobal()` vendor global access, `cssValue()` / `cssAlpha()` custom property reads, `isDark()`, and `createPaletteCache()` per-theme palette caching) used by the chart-based apps
- `js/modules/frame-scheduler.js`: `createFrameScheduler()`, which coalesces repeated requests (such as slider input) into one callback on the next animation frame
- `js/modules/offscreen-draws.js`: `createOffscreenDraws()`, which holds chart redraws while a canvas is off screen and runs the latest one when it scrolls near the viewport

## Filters

`buildFilterNotes()` in `js/modules/gallery/render.js` renders the filters as desk notes: tool notes on one side of the book and tag notes on the other, each group starting with an All note. `js/modules/gallery/gallery-app.js` toggles them. Each tool and tag keeps one color across its desk note, its dropdown option, and its detail capsule.

At 900px or narrower the desk notes are hidden, and `#filter-dropdowns` shows one multi-select dropdown per filter group. `buildFilterDropdowns()` builds them from a list of groups, so a new group is one more entry.

- Each dropdown is a note button that shows its pick count and puts the count in its accessible name, such as "Tags, 2 selected". It opens a native modal `<dialog>` checklist on the bottom edge of the screen.
- Options carry the desk notes' colors and the number of artifacts that use them. Picked options move to the top when the panel opens. A group with more than eight options gets a search box. Clear resets the group, and Done, the close button, a tap on the backdrop, or Escape closes the panel.
- Options filter the gallery live through the same click handler as the desk notes.
- Widening past 900px closes an open panel.
- The toolbar is centered: the search note on its own row, then the dropdowns and the sort note on a row under it. The reset note stays on the desk layout, because each panel clears its own group and the search field clears itself.

## Search and sort

On the desk layout the search note sits above the book, beside the sort and reset notes. `#search-count` shows "N found" or "nothing yet" while a search is active. `#gallery-status` announces the result to screen readers. The `/` shortcut focuses the search field when no text field has focus and the detail overlay is closed.

The search runs `SEARCH_DELAY_MS` (400ms) after the last keystroke, so a typed word usually runs one search instead of one per key. Enter searches at once, and an emptied field shows every artifact at once. Each search starts at page 1.

`.sort-toggle::after` supplies the visible label, "newest" or "oldest". The accessible button name is "Sort by newest first" or "Sort by oldest first".

Search text, filters, sort order, and page live in the URL as `q`, `tool`, `tag`, `sort`, and `page`. Only non-default values appear. Each change pushes a history entry, and Back and Forward restore the state.

### Layout stability

Search, filter, and sort changes do not move the controls or the page:

- `html` reserves the scrollbar gutter, so opening the overlay does not shift the page sideways.
- `.search-clear` fades out when the field is empty but keeps its slot, and `.search-count` keeps its line and width while empty.
- `.sort-toggle` renders both labels in one grid cell, with the hidden one setting the width, so the note keeps the same width after a sort change.
- `.filter-reset` is positioned beside the sort note, outside the row's flow, and only fades in while a filter is active.
- `renderPagination()` always renders the row. With a single page every control is disabled and a blank slot stands in for a second page tag. A page-number row longer than seven slots stays seven slots wide, so Prev and Next do not move.
- `renderContent()` skips the grid write when the markup is unchanged, which leaves card hover states and thumbnails alone. `--card-thumb-ratio` sizes image slots before the images load.

## Book scene

The gallery uses a post-bound scrapbook layout. Its closed cover includes a ribbon, binding posts, tabs, a title note, doodles, and placeholder snapshots. `--color-album-*` tokens define cover colors, and `assets/scrapbook/` contains the images.

The endpaper, settled pages, and turning leaf faces share the same ruled-paper pattern. `getAttachmentData()` in `render.js` selects tape, clips, or photo corners from the artifact ID, keeping each card's attachment consistent.

### Cover introduction

`startIntro()` runs once, after the first render. It waits 500ms, then the ribbon slides off. When the ribbon is 55% of the way off (`RIBBON_LEAD`), the cover starts to turn, so the two motions run together. The cover rotates 180 degrees around the spine while the book moves to its centered-open position.

The book's shadow opens with the cover on the compositor. `.book-shadow` in `css/src/02-gallery.css` holds a soft-edged mask whose edge sits on the spine while the book is closed. The intro slides the masked box and the shadow inside it (`::before`) home in opposite directions, so only the mask edge moves and only transforms animate. The page-stack edges animate their depth only once the book is open, so they take their first depth without growing in.

The left page stays hidden until the cover lands. The inside cover contains a copy of the first left page, which `setPosition()` refreshes if a search or filter re-renders the grid during the swing. After landing, the live page replaces that copy without a fade or position change.

The intro always ends with the book open, even if an animation fails or the layout crosses the notepad breakpoint and aborts it.

### Page turns and requests

A turning leaf has two faces and matches the settled page dimensions. Its front shows the source page and its back shows the destination page. A ghost page under the leaf shows the destination page's slice on that side. The live pages stay untouched until the turn lands, so a spring-back only removes the leaf.

`leafPose()` gives the leaf's angle and shading for any turn progress. A drag applies it on each pointer move. A button or page-number turn samples it in 24 steps (`leafTurnSamples()`) into Web Animations keyframes (`leafTurnTracks()`), with the ease-in-out curve baked into the sampled progress values, and plays them with linear easing over `LEAF_TURN_MS` (680ms). The compositor plays the curve without a main-thread frame loop. Halfway appears twice in the samples, so the shading still switches there at once.

A drag starts within 36px of a page's outer edge or within 72px of its bottom corner (`EDGE_ZONE_PX`, `CORNER_ZONE_PX`). The leaf follows the pointer. Releasing beyond `DRAG_COMPLETE_THRESHOLD` (45%) completes the turn, and an earlier release returns the leaf to its starting position. A corner press that moves less than 5px (`TAP_SLOP_PX`) turns the page. Both endings finish with a short eased tween. Drags are off in the notepad layout, in reduced-motion mode, and when the press starts on a card. `.book-sheet` uses `touch-action: pan-y pinch-zoom` so horizontal drags turn pages while vertical scrolling and zoom remain available.

**Prev**, **Next**, and page-number requests share one queue. Requests made during a turn collapse into the latest one, which plays after the current transition. A request made during a drag remains selected after that drag ends. Prev and Next step from the latest requested page, so rapid presses keep stepping.

Search, filter, sort, and history changes call `renderContent()`, which cancels an active turn before rendering. Completed, canceled, and failed animations remove temporary leaves and inline styles. The fallback listener on `#book-sheet` replaces broken thumbnails on turning leaves with the grid's placeholder.

A page turn that starts with the book's top above the screen scrolls it back into view first (`scrollBookIntoView()`), so a tall phone page never leaves the reader at the end of the new page.

Reduced-motion mode uses short cross-fades instead of 3D turns, and the intro cross-fades too.

### Viewport fit

Above 900px wide, the open book fits the viewport height. `--book-chrome-y` reserves space for the header, search, and pagination. Book height stays between `--book-fit-min-height` (460px) and `--book-sheet-min-height` (800px).

`--book-spread-ratio` scales width with height to preserve page proportions. At viewport heights of 900px or less, header and control spacing shrink and desk notes become smaller. Captions scale with book width.

### Notepad (900px and narrower)

Phones and tablets held upright get a one-page notepad bound at the top instead of the two-page book. `book-scene.js` exports the breakpoint as `NOTEPAD_QUERY`. `gallery-app.js` imports it for the page size and the filter dropdowns, and it must equal the `max-width: 900px` notepad block in `css/src/06-responsive-and-motion.css`. Both scripts listen for the query's `change` event. Crossing the breakpoint settles a turn in flight and aborts a running intro, and a resize that stays on one side of it leaves animations alone.

- Each page holds one artifact (`NOTEPAD_ITEMS_PER_PAGE` in `gallery-app.js`): its photo, then the `.card-notes` under it, with the description written on the ruled lines and an open link. The book hides the notes and keeps them in the detail overlay. Crossing the breakpoint keeps the reader on the page that holds the first artifact they were looking at.
- The notepad fills the screen height below the search (`--notepad-chrome-y`), between 23rem and 50rem tall. `.book-spine` becomes the wire binding, and the bottom edge shows one sliver per page still to come, from `--stack-right-n`.
- Pages flip like a desk calendar. `playFlipTurn()` swings a two-faced copy of a page on its top edge (a positive `rotateX` to 180 degrees, `FLIP_KEYFRAMES`, 620ms). Going forward, the old page's bottom edge lifts toward the reader, the sheet swings up over the binding showing its plain back, and the back fades as it drops behind the pad (`FLIP_BACK_FADE_KEYFRAMES`), uncovering the next page, which is already rendered underneath. Going back plays the same animation in reverse with the earlier page, which then takes the shown page's place.
- The flip is Web Animations on `transform` and `opacity` only, so the compositor runs it without a main-thread frame loop. The leaf keeps its faces in 3D (`transform-style: preserve-3d`), and each face hides by `backface-visibility` when it turns away, so the leaf itself never animates `opacity`, which would flatten its faces. The sheet is drawn flat (`transform-style: flat`), so the cover and the leaf always paint over the page, while `perspective` on `.book-sheet` and `.book-inner` still gives them depth.
- The intro slides the cover band down off the bottom edge, like an elastic closure. When the band is 55% off, the cover turns up over the binding with the same keyframes and shows its inside past upright (`playFlipIntro()`, 900ms).
- A vertical swipe on the sheet turns the page: up for next, down for previous. The travel must reach `SWIPE_MIN_PX` (40px in `gallery-app.js`) and exceed the sideways travel. The sheet sets `touch-action: pan-x pinch-zoom` so those swipes reach the page. A swipe that turned the page does not also open the card it ended on. Phones on their side get the photo beside its notes and keep normal scrolling, so the arrows turn the page there.
- The toolbar is the centered one described under Filters, and the pager is the previous and next arrows around `.page-counter`.

## Test coverage

- `tests/js/home/`: root gallery tests for bootstrap wiring, config validation, catalog helpers, the book scene, overlay behavior, rendering, and keyboard flows
- `tests/js/common/`: tests for shared modules and bootstrap scripts, such as runtime helpers, the app shell, theme bootstrap, `boot-guard.js`, motion and inert helpers, element caching, and chart and section-nav helpers
- `tests/js/apps/bond-price-vs-rate/`: app-specific entry, pricing-math, and rendering coverage for the bond price vs rate app
- `tests/js/apps/loan-amortization/`: app-specific entry, DOM, and module coverage for the loan amortization app
- `tests/js/apps/prompt-caching/`: app-specific entry, DOM, and module coverage for the prompt caching app
- `tests/js/apps/tokenizer-explorer/`: app-specific entry and module coverage for the tokenizer explorer app
- `tests/js/apps/vendor-docs-generator/`: app-specific entry, document-model, annotation, degradation, rendering, and exporter coverage for the vendor docs generator app
- `tests/js/tooling/`: Node tests for JavaScript-based lint and maintenance tooling
- `tests/js/workflows/`: Node tests for the `deploy-site` and `verified-commit` GitHub composite-action modules
- `tests/browser/test_frontend_smoke.py`: browser smoke coverage for gallery load, invalid bootstrap data, search, desk-note filters, pagination, the detail overlay, and `404.html`
- `tests/browser/test_frontend_accessibility.py`: Playwright and axe coverage for root light and dark themes, overlay state, no-results state, the book after its open and turn animations, and `404.html`, plus explicit contrast assertions
- `tests/browser/test_frontend_browser_flows.py`: keyboard-only, mobile, reduced-motion, theme persistence, larger-catalog, and book-scene coverage (centered open book, leaf geometry, rapid turns, completed and sprung-back drags, laptop fit, notepad flips, resizing across the notepad breakpoint mid-turn, search and filters during a turn or the intro, and stable toolbar notes)
- `tests/browser/test_frontend_apps_smoke.py`: real app smoke coverage for mature app folders that opt into the shared app system
- `tests/browser/test_frontend_apps_accessibility.py`: Playwright and axe coverage for mature app shared-shell accessibility and contrast
- `tests/browser/test_frontend_apps_browser_flows.py`: mature app browser-flow coverage for app-specific interactions and theme behavior. Each flow test skips when its app slug is outside `ARTIFACTS_BROWSER_APP_SLUGS`
- `tests/browser/test_frontend_webkit_smoke.py`: bounded WebKit cross-engine smoke coverage for the root gallery and every mature app entry page
- `tests/browser/test_frontend_visual.py`: local fixed-viewport visual baseline comparisons for the root gallery and mature app hero states. This suite is intentionally not part of blocking CI
- `tests/browser/test_frontend_live.py`: post-deploy browser verification for the published root and `404.html` when `ARTIFACTS_LIVE_SITE_URL` is set

## Accessibility notes for the root shell

- The root shell keeps keyboard focus visible across search, desk-note filters, filter dropdowns, pagination, overlay close and return, and the scroll-to-top control.
- `js/modules/gallery/gallery-app.js` keeps the theme toggle stateful with `aria-pressed`, updates the toggle label for the next theme, and announces result and theme changes through the `#gallery-status` live region.
- Artifact cards render as real `<button>` controls so keyboard and screen-reader semantics match the interaction model instead of relying on `role="button"` shims.
- `js/modules/gallery/render.js` gives the detail description a stable ID, and `js/modules/gallery/detail-overlay.js` uses it to describe the dialog while artifact links announce that they open in a new tab.
- Each filter dropdown button sets `aria-haspopup="dialog"` and `aria-expanded`, and its panel is a modal `<dialog>` labelled by its title. After a filter click, focus stays on the option or desk note that was pressed.
- `404.html` has explicit focus-visible styling so fallback navigation is keyboard-safe even outside the main app shell.
- `css/src/01-tokens.css` owns focus ring tokens. The relevant component, utility, and responsive partials own skip-link behavior and accessible contrast tuning for active pagination and detail CTA states.
- `tests/browser/frontend_helpers.py` fails browser suites on `pageerror`, unexpected `console.error`, failed requests, and HTTP 4xx/5xx responses, and can emit screenshots, traces, and runtime logs for CI artifacts.

## Local and CI checks

- [Operations](operations.md) is the canonical workflow reference. The targets below are the frontend checkpoints you use most often.
- `make test-js` runs the JavaScript unit suite with Node's built-in test runner across `tests/js/home/`, `tests/js/common/`, `tests/js/apps/`, `tests/js/tooling/`, and `tests/js/workflows/`
- `make coverage-js` uses Node's built-in experimental coverage report, which covers all source files imported by tests while excluding `node_modules/` and `tests/`. Thresholds and exclusions are configured in `package.json`
- `make check-local` is an alias for `make ci`, the non-browser local gate. It runs Python and web formatting, linting, type checks, and dead-code checks, the Python and JavaScript tests, JavaScript source-to-test coverage lint and coverage floors, dependency audits, artifact validation, and the generated-file drift check. `make ci-fast` runs most of them in parallel and leaves out the per-file coverage floors
- `make test-browser-root` runs all root-gallery Playwright suites
- `make test-browser-root-smoke`, `make test-browser-root-accessibility`, and `make test-browser-root-flows` run the root smoke, accessibility, and browser-flow suites separately
- `make test-browser-apps` runs all mature app Playwright suites. Set `ARTIFACTS_BROWSER_APP_SLUGS` to limit them to specific app slugs
- `make test-browser-apps-smoke`, `make test-browser-apps-accessibility`, and `make test-browser-apps-flows` run the mature app smoke, accessibility, and browser-flow suites separately
- `make test-browser-webkit-smoke` runs the bounded WebKit smoke pass across the root gallery and all mature apps. Run `make setup-playwright-webkit` first, or follow the local runtime instructions in [operations.md](operations.md#browser-setup-without-sudo)
- `make check-web` runs both root and app browser suites plus thumbnail generation. Run `make setup-all` first so Chromium is available
- `make test-visual` compares committed hero baselines, while `make visual-baselines` regenerates them after an intentional visual change. Both are local, on-demand checks, not blocking CI gates
- `make check` runs the full local release gate by combining `make check-local`, `make check-web`, index generation, and deployable site assembly
- Every `make test-browser*` target runs through `scripts/ci/run_browser_tests.py`, which sets `ARTIFACTS_REQUIRE_BROWSER_TESTS=1`, so browser suites must run instead of skipping when Chromium is unavailable
- `make test-browser-live` runs the published-site Playwright verification suite when `ARTIFACTS_LIVE_SITE_URL` is set
- The workspace uses Node's built-in coverage report. It has no Istanbul or nyc instrumentation dependencies
