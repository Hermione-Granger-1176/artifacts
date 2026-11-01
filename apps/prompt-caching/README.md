# Prompt caching, demystified

This interactive explainer follows LLM inference through tokenization, embeddings, attention, the key-value (KV) cache, and provider caching.

## Features

The page includes these interactive examples:

- Sticky section-progress nav (nine sections) with a clickable pipeline overview
- Inference simulator that streams tokens while the KV cache fills
- BPE-style tokenizer with text and token-ID views
- Embedding playground: cosine similarity and distance for two words, a 2D projection canvas, and a 1D, 2D, or 3D dimension explorer (drag to rotate in 3D)
- Attention step explorer with clickable matrix dot-products, a Q/K toggle with a weight scrambler, a causal mask toggle, a hoverable attention grid, and interactive softmax sliders
- KV-cache fill animation and no-cache vs with-cache computation comparison
- OpenAI and Anthropic comparison table, then a cross-request cache-hit visualizer with a live 5-minute TTL countdown
- Savings calculator for your own workload, with Hobby, Startup, and Scale presets
- Light and dark themes through the shared app theme

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

## Documentation

The app documentation covers [architecture](docs/architecture.md), [verification](docs/verification.md), and [implementation decisions](docs/decisions.md).
