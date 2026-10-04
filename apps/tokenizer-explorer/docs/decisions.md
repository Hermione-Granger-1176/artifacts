# Decisions

## Why this is a conceptual simulator

The goal is to explain tokenization, temperature, top-p, and sampling, not to connect to a live tokenizer or model API. Local scenarios keep the artifact deterministic and portable. Tests can verify its calculations without API access.

## Why token examples are canned

The tokenization card uses pre-split examples rather than a real tokenizer. Different BPE vocabularies differ, especially for non-English text and emoji, so the page labels them illustrative instead of implying exact production output. This also preserves the self-only CSP and avoids a large tokenizer vocabulary download.

## Why the bars are plain DOM and not a canvas chart

The first version used a vendored Chart.js horizontal chart in its own card, with the pool and insight in two more cards. The playground layout folds those into one next-token list inside the main card. A row list handles what this view needs better than a canvas: each row can carry a struck-through token, a hatched cut bar, a "top P cut" label, and numeric columns that align with the header, all selectable and readable by assistive tech. Dropping the chart also removed the vendored Chart.js bundle, its manifest entry, and the palette cache from this app.

## Why the bars use temperature-shaped probabilities

The blue bar shows the distribution after temperature only, so each slider has a distinct visual effect: temperature changes bar lengths, while top-p flips tail tokens into a cut state (struck through, hatched, below the "top P cut" line) without resizing anything. The renormalized draw chances sit in the Draw column of the same row, which keeps the pre-cutoff probabilities from being mistaken for draw chances while making the cut-then-renormalize order explicit.

## Why the layout is a playground

The settings sit beside the text they change, the way LLM playgrounds do, so a slider and the bars it reshapes are visible together. One main card and one settings card use the same card style, padding, and header row, and every block in a column shares its left and right edge. The earlier pipeline strip, chart card, token-pool card, and insight box became the bar list, the "Order matters" key idea, and a single quiet insight line.

## Why the code window is folded

The "Order matters" key idea says the same thing in words, so the pseudocode sits under a "Show the code" disclosure in the settings card. It is reflowed with comments above each statement so it fits the narrow panel without horizontal scrolling.

## Why the whitespace toggle lives in the main card

The prompt chips and the tokenization examples both show leading spaces, so one toggle in the main card header drives both.

## Why draw helpers accept a random callback

`drawToken()` and `tallyDraws()` accept an injectable random callback. The app uses `Math.random`, while tests can use deterministic rolls to verify token selection and tally aggregation exactly.

## Why the shared app system is reused

The page shares the bond explainer's controls and theme. Shared tokens, control fields, the shared inset-pill segmented skin (`.is-inset`), header chrome, and theme behavior keep that cohesion while tokenizer-specific layout selectors stay in the app-local stylesheet.

## Deferred items

- More scenarios and domain-specific examples
- A selectable real tokenizer, if its vocabulary can remain local and clearly versioned
- API-backed model comparisons
