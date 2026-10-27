# Architecture

## Prompt caching, demystified

### Runtime flow

1. `index.html` loads `../../js/app-theme.js` (synchronous theme bootstrap), then the shared stylesheet at `../../css/style.css` followed by `./css/app.css`.
2. `js/app.js` calls `renderAppShell()` to mount the shared shell markup, then `initializeMatureApp({ run })`.
3. Inside `run`, `initAppShell({ onThemeChange })` wires the header (back button, brand, theme toggle) and scroll-to-top behavior. Each feature module then initializes itself in page order: navigation, tokenizer, embeddings, inference, attention, KV cache, cache hits, calculator. A theme change calls the `redraw()` that `initEmbeddings()` returns.

### Module map

- `modules/data.js`: static reference data: the toy BPE vocabulary (`WHOLE_TOKENS`, `SUB_PIECES`), the pre-computed 4-token, 3-dimension attention example (`ATTN_DATA`), hand-tuned 8-D word embeddings, demo scripts, and summary steps. Cluster colors are stored as shared-token names. The section nav comes from the `data-nav-label` attributes in `index.html`, not from this file.
- `modules/math.js`: pure functions with no DOM access: `bpeTokenize`, `hashToken`, `cosineSim`, `eucDist`, `softmax`, `savingsMonthly`, `formatTTL`, `verdictForSimilarity`, `project2D`. This is the unit-tested core.
- `modules/dom.js`: `byId`, `makeEl`, `clear`, `prefersReducedMotion`, `reserveSpace`, `longestText`, and a re-export of the shared `initSegmented`.
- Feature modules connect state to browser interactions. They build nodes with `makeEl` or `document.createElement` and bind events with `addEventListener`:
  - `navigation`: the shared section nav, the pipeline jump links, and the summary timeline
  - `tokenizer`: the text and token-ID views of `bpeTokenize`, with token, word, and character counts (characters are Unicode code points)
  - `embeddings`: the dimension explorer canvas and the similarity playground canvas
  - `inference`: the token-streaming simulator and its KV cache bar
  - `attention`: the five-step Q/K/V explorer, the attention grid, and the softmax sliders
  - `kv-cache`: the cache fill animation and the no-cache versus with-cache comparison
  - `cache-hits`: the cross-request log with a 300-second TTL, which evicts the oldest request after five
  - `calculator`: the presets, sliders, and cost figures from `savingsMonthly`

### Theming

Prompt Caching accents (`--pc-accent/warm/teal/indigo/rose`) are mapped in `css/app.css` onto the shared semantic text colors (`--color-amber-text/blue-text/green-text/purple-text/red-text`) in `css/style.css`. The matching `-bg` and `-border` tints are `color-mix()` blends of `--color-amber/blue/green/purple/red`. Surfaces, text, and borders flip automatically in dark mode. The two `<canvas>` demos resolve their colors from CSS variables through a per-theme palette cache (`createPaletteCache`) and are redrawn on `onThemeChange`, so they stay correct across themes without re-reading computed styles on every frame.

### Stable layout

Demos whose content changes reserve the room of their largest state, so no interaction moves the page below.

- `reserveSpace` adds hidden copies of every state to the live element's grid cell, which then measures as the tallest state at the current width. The inference token stream and status line, the KV-cache narration, and the dimension-explorer caption use it.
- The tokenizer keeps its text and token-ID views stacked in one cell and hides the inactive one.
- The KV-cache panes keep every row in the layout and hide the rows that are not cached yet.
- The attention step card renders every step once (also scrambled, unmasked, and with each calculation open), measures the tallest, and sets that as its `min-height`. It measures when the card comes within two screens of the viewport, and again when the width changes or web fonts finish loading.
- The cache-hit log has a fixed height and scrolls inside itself, so adding or evicting a request never changes the page height. The app scrolls only that list, never the page.

The inference, KV-cache, and cache-hit demos skip their timed animation under `prefers-reduced-motion: reduce` and show the final state at once.

### CSP compliance

The shared CSP is `default-src 'self'` with no `unsafe-inline`. Accordingly there are no inline `<style>`/`style="..."` attributes and no inline scripts or `onclick` handlers. Dynamic, value-driven styling (bar scales, attention-weight tints, matrix grid columns) is applied through the CSSOM (`element.style.*`), which CSP permits. The calculator and softmax bars scale with `transform: scaleX` from their left edge, so a slider drag animates on the compositor and never relayouts.
