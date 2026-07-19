# Architecture

## Page sections

- Header shell: back button, home logo, and shared theme toggle
- Intro: app title and the full tokenization-to-sampling story
- Tokenization card: pre-split illustrative examples, token and character counts, token chips, and a whitespace toggle
- Sampling explorer: scenario tabs, a sentence with a temporary sampled completion, and a visible two-step pipeline
- Sampling controls: temperature, top-p, live values, greedy-decoding explanation, and presets
- Probability chart: a fixed-height Chart.js horizontal bar chart for theoretical and empirical probabilities
- Token pool: post-cutoff, renormalized probability pills and plain-language insight
- Concepts: delegated accordion cards for tokens, temperature, nucleus sampling, and token-driven behavior

## Module map

- `js/app.js`
  - owns DOM caching, interaction handlers, selected-token state, sample tallies, chart reuse, and the render loop
- `js/modules/scenarios.js`
  - exports the canned next-token scenario dataset
- `js/modules/sampling.js`
  - exports `softmax()`, greedy decoding at temperature zero, top-p selection, renormalized draws, and tally aggregation
- `js/modules/charts.js`
  - creates one horizontal Chart.js instance and updates it in place as the scenario or sliders change
  - builds its colors with the shared `chart-theme.js` cache and refreshes them on a theme change
- `js/modules/token-examples.js`
  - exports static illustrative token chunks plus count and whitespace-display helpers
- `js/modules/render.js`
  - renders tabs, the sentence completion, token examples, top-p pills, and explanatory copy
  - uses the shared chart-theme color helpers for dynamically colored pills
- shared `js/modules/section-nav.js`
  - builds the sticky frosted section-progress nav and its IntersectionObserver scroll spy
  - shared repo-root module, also used by the prompt-caching app
- `js/modules/accordion.js`
  - provides delegated card-toggle behavior for concept cards

## Sampling data flow

1. A tab, slider, or preset changes the active scenario or sampling settings.
2. `buildTopPSelection()` applies temperature to logits, softmaxes the result, ranks tokens, and retains the smallest cumulative top-p nucleus.
3. The surviving probabilities are renormalized into `adjustedProb`, the only distribution used for a pick or a 100-draw tally.
4. The chart updates the same Chart.js instance with adjusted theoretical percentages, zero-width muted exclusions, and optional observed percentages.
5. The DOM renderer updates the sentence, pills, insight, and accessible sample-status copy.

## Theme model

- `<html>` owns `data-theme="light|dark"`
- Shared shell behavior reads the same `theme` localStorage key as the root gallery
- Theme changes clear the app-local palette caches before the chart and pills render again
- The chart reads `--chart-tick`, `--chart-grid`, and shared palette variables rather than owning color constants
