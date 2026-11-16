# Architecture

## Runtime flow

1. `index.html` loads `../../js/app-theme.js` to apply the saved theme before first paint. It then loads the shared stylesheet at `../../css/style.css`, followed by `./css/app.css`.
2. `js/app.js` calls `renderAppShell()` to mount the shared shell markup, then calls `initializeMatureApp({ run })`.
3. Inside `run`, `initAppShell({ onThemeChange })` wires the header (back button, brand, theme toggle) and scroll-to-top. Each feature module then initializes in page order: navigation, tokenizer, embeddings, inference, attention, KV cache, cache hits, and calculator. A theme change calls the `redraw()` that `initEmbeddings()` returns.

## Module map

- `modules/data.js`: static reference data. It holds the toy BPE vocabulary (`WHOLE_TOKENS`, `SUB_PIECES`), the precomputed 4-token, 3-dimension attention example (`ATTN_DATA`), the hand-tuned 8-D word embeddings, demo scripts, and summary steps. Cluster colors are stored as shared-token names. The section nav reads the `data-nav-label` attributes in `index.html`, not this file.
- `modules/math.js`: pure functions with no DOM access: `bpeTokenize`, `hashToken`, `cosineSim`, `eucDist`, `softmax`, `savingsMonthly`, `formatTTL`, `verdictForSimilarity`, and `project2D`. This is the unit-tested core.
- `modules/dom.js`: `byId`, `makeEl`, `clear`, `prefersReducedMotion`, `reserveSpace`, `longestText`, and a re-export of the shared `initSegmented`.
- Feature modules connect state to browser interactions. They build nodes with `makeEl` or `document.createElement`, and they bind events with `addEventListener`:
  - `navigation`: the shared section nav, the pipeline jump links, and the summary timeline.
  - `tokenizer`: the text and token-ID views of `bpeTokenize`, with token, word, and character counts. Characters are Unicode code points.
  - `embeddings`: the dimension explorer canvas and the similarity playground canvas.
  - `inference`: the token-streaming simulator and its KV cache bar.
  - `attention`: the five-step Q/K/V explorer, the attention grid, and the softmax sliders.
  - `kv-cache`: the cache fill animation and the no-cache vs with-cache comparison.
  - `cache-hits`: the cross-request log with a 300-second TTL. It evicts the oldest request after five.
  - `calculator`: the presets, sliders, and cost figures from `savingsMonthly`.

## Theming

The `--pc-*` accents in `css/app.css` (`--pc-accent`, `--pc-warm`, `--pc-teal`, `--pc-indigo`, `--pc-rose`) map onto the shared semantic text colors (`--color-amber-text`, `--color-blue-text`, `--color-green-text`, `--color-purple-text`, `--color-red-text`) in `css/style.css`. The matching `-bg` and `-border` tints are `color-mix()` blends of `--color-amber`, `--color-blue`, `--color-green`, `--color-purple`, and `--color-red`. Surfaces, text, and borders switch with the theme automatically.

The two canvas demos read their colors from CSS variables through a per-theme palette cache (`createPaletteCache`). They redraw on `onThemeChange`.

## Stable layout

Demos whose content changes reserve the room of their largest state. No interaction moves the content below.

- `reserveSpace` adds hidden copies of every state to the live element's grid cell. The cell then measures as the tallest state at the current width. The inference token stream and status line, the KV-cache narration, and the dimension-explorer caption use it.
- The tokenizer stacks its text and token-ID views in one cell and hides the inactive one.
- The KV-cache panes keep every row in the layout and hide the rows that are not cached yet.
- The attention step card renders every step once, including the scrambled, unmasked, and expanded calculation states. It measures the tallest and sets that as its `min-height`. It measures when the card comes within two screens of the viewport, and again when the width changes or web fonts finish loading.
- The cache-hit log has a fixed height and scrolls inside itself. Adding or evicting a request does not change the page height. The app scrolls only that list, never the page.

The inference, KV-cache, and cache-hit demos skip their timed animation under `prefers-reduced-motion: reduce` and show the final state at once.

## CSP compliance

The shared CSP is `default-src 'self'` with no `unsafe-inline`. The page has no inline `<style>` or `style="..."` attributes, no inline scripts, and no `onclick` handlers. Dynamic, value-driven styling (bar scales, attention-weight tints, and matrix grid columns) goes through the CSSOM (`element.style.*`), which CSP allows.

The calculator and softmax bars scale with `transform: scaleX` from their left edge. See [decisions](decisions.md) for the reasoning.
