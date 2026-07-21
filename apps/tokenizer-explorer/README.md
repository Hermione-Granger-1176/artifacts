# Tokenizer: Temperature & Top P Explorer

Interactive explainer for LLM tokenization and sampling. Shows BPE-style token splits, then lets you adjust a next-token distribution with temperature and top-p sampling.

## Highlights

- Scenario prompts across writing, code, factual, and chat contexts
- Temperature reshapes scores, top-p cuts and renormalizes the candidate pool
- Bounded Chart.js probability chart with muted excluded tokens and tooltips
- Precise, Chat, and Creative presets including temperature zero for greedy decoding
- 100-draw tally vs temperature-shaped bars vs renormalized pool comparison
- Expandable concept cards on tokens, temperature, nucleus sampling
- Sticky frosted progress nav with scroll spy
- Scenario prompt and sampling pseudocode in macOS-style code windows

## Made with

- Claude
- Chart.js 4.4.1 (vendored)

## Structure

```text
index.html
css/app.css
js/
├── app.js
├── modules/
│   ├── scenarios.js
│   ├── sampling.js
│   ├── charts.js
│   ├── token-examples.js
│   ├── render.js
│   └── accordion.js
└── vendor/
    └── chart.umd.min.js
docs/
```

## Docs

See `docs/` for architecture, verification, and implementation decisions.
