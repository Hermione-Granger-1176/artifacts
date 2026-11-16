# Prompt caching, demystified

This interactive explainer follows an LLM request through tokenization, embeddings, attention, the key-value (KV) cache, and provider prompt caching.

## Features

- A sticky progress nav with nine sections and a clickable pipeline overview.
- Demos for token streaming, the KV cache, embeddings, attention, and cache hits.
- A comparison of OpenAI and Anthropic caching.
- A savings calculator for your own workload, with Hobby, Startup, and Scale presets.
- Light and dark themes through the shared app theme.

## Use the app

- Jump between sections with the progress nav, or click a stage in the pipeline overview.
- In the tokenizer, switch between the text and token-ID views.
- In the inference simulator, click **Generate** to stream tokens and **Reset** to start over.
- In the embedding playground, select words or word pairs and click **Swap**. Drag the 3D dimension explorer to rotate it.
- In the attention explorer, step through the calculation and click a matrix cell to see its dot product. Toggle the causal mask, hover the attention grid, and move the softmax sliders.
- In the KV-cache demo, click **Play** to watch the cache fill. Click **Reset** to start over, or use comparison mode to contrast no cache with a cache.
- In the cache-hit visualizer, click **Send** to add a request and **Clear** to reset the log. The TTL countdown shows when a cached prefix expires.
- Move the savings sliders to change the monthly cost totals.

## Made with

- Claude
- No runtime dependencies (vanilla HTML, CSS, ES modules, CSP-safe)

## Documentation

The app documentation covers [architecture](docs/architecture.md), [verification](docs/verification.md), and [implementation decisions](docs/decisions.md).
