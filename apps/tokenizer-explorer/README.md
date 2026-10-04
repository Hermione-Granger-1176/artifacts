# Tokenizer: Temperature & Top P Explorer

Interactive explainer for LLM tokenization and sampling. A playground-style workbench lets you adjust temperature and top-p against a next-token distribution, then shows BPE-style token splits and concept cards below.

## Highlights

- Two top-aligned columns: one main card (prompt, next-token bars, actions) and a settings card on the right that stacks above the main card below 900px
- The prompt is rendered as coloured token chips with the completion blank inline at the end of the line
- A single bar list shows every candidate: token, bar after temperature, odds, renormalized draw chance, and (after Sample 100x) the observed count with a thin second bar
- Tokens cut by top-p stay in the list, struck through, with a hatched bar below a labelled "top P cut" line
- Scenario dropdown, temperature and top-p sliders with live notes, and Precise, Chat, and Creative presets (including temperature zero for greedy decoding) as an inset-pill segmented control
- One "Order matters" key idea, plus the whole sampling step as pseudo-code folded under "Show the code"
- Show whitespace toggle in the main card header, which also applies to the tokenization examples
- Expandable concept cards on tokens, temperature, nucleus sampling, and token-driven behavior
- Sticky frosted progress nav with scroll spy

## Made with

- Claude

## Structure

```text
index.html
css/app.css
js/
├── app.js
└── modules/
    ├── scenarios.js
    ├── sampling.js
    ├── candidates.js
    ├── token-examples.js
    ├── render.js
    └── accordion.js
docs/
```

## Docs

See `docs/` for architecture, verification, and implementation decisions.
