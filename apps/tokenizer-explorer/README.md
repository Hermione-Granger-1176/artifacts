# Tokenizer: Temperature & Top P Explorer

Interactive explainer for the path from text chunks to a sampled LLM continuation. It first shows illustrative BPE-style token splits, then lets visitors adjust a next-token distribution with temperature and top-p sampling.

## Features

- Compare multiple prompt scenarios across writing, code, factual, and chat contexts
- Inspect canned tokenization examples, character counts, token counts, and visible leading whitespace
- Follow the sampling order: temperature reshapes scores, then top-p cuts and renormalizes the candidate pool
- Read a bounded horizontal Chart.js probability chart with muted excluded tokens and exact-percent tooltips
- Pick one next token or run 100 draws to compare the observed tally with the temperature-shaped bars and the renormalized pool
- Use Precise, Chat, and Creative presets, including temperature zero for greedy decoding
- Read expandable concept cards about tokens, temperature, nucleus sampling, and behavior that follows from token chunks
- Jump between sections with the sticky frosted progress nav, which tracks scroll position with numbered nodes
- Read the scenario prompt and the condensed sampling pseudocode inside macOS-style code windows with traffic-light dots
- Share the same header, theme model, and design system as the rest of the mature app suite

## Structure

- `index.html` - app shell, semantic content, local Chart.js vendor loading, and controls
- `../../css/style.css` - shared site stylesheet, tokens, chart frame, and app shell selectors
- `css/app.css` - tokenizer layout, fixed chart height, token chips, and responsive selectors
- `js/app.js` - bootstrap, UI state, interaction handlers, and render orchestration
- `js/modules/scenarios.js` - canned next-token scenario data
- `js/modules/sampling.js` - softmax, greedy decoding, top-p renormalization, draws, and tally aggregation
- `js/modules/charts.js` - persistent horizontal Chart.js probability chart and theme-aware palette handling
- `js/modules/token-examples.js` - illustrative pre-split text chunks and count helpers
- `js/modules/render.js` - DOM rendering for tabs, sentences, token examples, pills, and narrative insight
- `../../js/modules/section-nav.js` - shared sticky section-progress nav with scroll spy, also used by prompt-caching
- `js/modules/accordion.js` - delegated concept-card expansion behavior
- `js/vendor/chart.umd.min.js` - vendored Chart.js 4.4.1 bundle, pinned in `config/vendored_assets.json`
- `docs/` - architecture notes, verification references, and implementation decisions

## Dependencies

- Chart.js 4.4.1 is vendored locally for the probability chart
- All other behavior uses browser-native HTML, CSS, and ES modules

## Development notes

- Keep app CSS colors token-derived through `var()` or a `color-mix()` over shared tokens. Raw hex, named colors, and literal-channel color functions are rejected by `make lint-app-css-tokens`
- Reuse the shared bookmark-note token system before adding new colors
- Preserve the order of operations: temperature first, top-p second, then sample from the renormalized nucleus
- Keep token examples explicitly illustrative. This artifact does not ship a real tokenizer or a model-serving client
