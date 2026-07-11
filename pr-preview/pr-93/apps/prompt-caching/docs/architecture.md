# Architecture

## Prompt Caching, Demystified

### Runtime flow

1. `index.html` loads `js/app-theme.js` (synchronous theme bootstrap), then the
   shared stylesheet at `../../css/style.css` followed by `./css/app.css`.
2. `js/app.js` calls `renderAppShell()`, then `initializeMatureApp({ run })`.
3. Inside `run`, `initAppShell({ onThemeChange })` mounts the header (back / brand /
   theme toggle) and scroll-to-top, then each feature module initialises itself.

### Module map

- `modules/data.js`: frozen reference data: section list, toy BPE vocabulary, the
  pre-computed 4×3 attention example, hand-tuned 8-D word embeddings, demo scripts,
  and summary steps. Cluster colours are stored as shared-token names.
- `modules/math.js`: pure functions with no DOM access: `bpeTokenize`, `hashToken`,
  `cosineSim`, `eucDist`, `softmax`, `savingsMonthly`, `formatTTL`,
  `verdictForSimilarity`, `project2D`. This is the unit-tested core.
- `modules/dom.js`: `byId`, `cssVar`, `makeEl`, `clear`.
- Feature modules (`navigation`, `tokenizer`, `embeddings`, `inference`,
  `attention`, `kv-cache`, `cache-hits`, `calculator`) are thin DOM glue. They read
  state, build nodes via `createElement`, and bind events with `addEventListener`.

### Theming

Prompt Caching accents (`--pc-accent/warm/teal/indigo/rose`) are mapped in
`css/app.css` onto the shared semantic palette
(`--color-amber/blue/green/purple/red`) in `css/style.css`.
Surfaces, text, and borders flip automatically in dark mode. The two `<canvas>`
demos resolve their colours from CSS variables at draw time and are redrawn on
`onThemeChange`, so they stay correct across themes.

### CSP compliance

The shared CSP is `default-src 'self'` with no `unsafe-inline`. Accordingly there
are no inline `<style>`/`style="…"` attributes and no inline scripts or `onclick`
handlers. Dynamic, value-driven styling (bar widths, attention-weight tints, grid
columns) is applied through the CSSOM (`element.style.*`), which CSP permits.
