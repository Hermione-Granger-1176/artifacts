# Prompt Caching, Demystified

A long-form interactive explainer on how LLM prompt caching works. Walks the inference pipeline from tokenizer to embeddings, attention, KV cache, and providers.

## Highlights

- Sticky section-progress nav with clickable pipeline overview
- Inference simulator that streams tokens while the KV cache fills
- BPE-style tokenizer with text and token-ID views
- Embedding playground: cosine similarity, 2D projection canvas, 1D/2D/3D dimension explorer
- Attention step explorer with clickable matrix dot-products, hoverable attention grid, interactive softmax sliders
- KV-cache fill animation and no-cache vs with-cache computation comparison
- Cross-request cache-hit visualiser with live TTL countdown
- Savings calculator for your own workload
- Full light/dark theming via shared app theme

## Made with

- Claude
- No runtime dependencies (vanilla HTML, CSS, ES modules, CSP-safe)

## Structure

```text
index.html
css/app.css
js/
├── app.js
└── modules/
    ├── data.js
    ├── math.js
    ├── navigation.js
    ├── tokenizer.js
    ├── embeddings.js
    ├── inference.js
    ├── attention.js
    ├── kv-cache.js
    ├── cache-hits.js
    ├── calculator.js
    └── dom.js
docs/
```

## Docs

See `docs/` for architecture, verification, and implementation decisions.
