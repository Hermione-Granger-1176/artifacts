# Prompt Caching, Demystified

## Purpose

A long-form, interactive explainer on how LLM prompt caching works. It walks the
inference pipeline from tokenizer to embeddings, attention, KV cache, and
providers. It shows that caching saves the attention mechanism's **K and V
matrices**, not the model's text output.

## Features

- Sticky section-progress nav with a clickable pipeline overview
- Inference simulator that streams tokens while the KV cache fills
- BPE-style tokenizer with text / token-ID views
- Embedding playground: cosine similarity + distance with a 2D projection canvas,
  plus a 1D/2D/3D dimension explorer
- Attention step explorer with clickable matrix dot-products, a hoverable
  attention grid, and interactive softmax sliders
- KV-cache fill animation and a no-cache / with-cache computation comparison
- Cross-request cache-hit visualiser with a live TTL countdown
- Savings calculator for your own workload
- Full light/dark theming via the shared app theme toggle

## Structure

- `index.html` - semantic layout inside the shared app shell with no inline styles or scripts
- `js/app.js` - entry point that wires the shared shell and the feature modules
- `js/modules/` - one module per concern:
  - `data.js` - static datasets (vocab, worked attention example, embeddings, scripts)
  - `math.js` - pure, unit-tested logic (tokenize, cosine, softmax, savings, projection)
  - `navigation.js`, `tokenizer.js`, `embeddings.js`, `inference.js`, `attention.js`,
    `kv-cache.js`, `cache-hits.js`, `calculator.js` - DOM glue for each demo
  - `dom.js` - small DOM helpers
- `docs/` - internal engineering notes

## Dependencies

- None. No CDN scripts or web fonts; styling resolves through `../../css/style.css`,
  satisfying the strict `'self'` CSP.

## Development

- Keep shared design decisions and app-specific layout selectors in the root stylesheet.
- Numerical logic lives in `math.js` and is covered by
  `tests/js/apps/prompt-caching/modules.test.js`.
- Credit: based on Sam Rose's deep-dive at ngrok.com/blog/prompt-caching, rewritten
  with original examples and interactive demos.
