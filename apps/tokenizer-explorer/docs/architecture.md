# Architecture

## Page sections

- Header shell: back button, home logo, and shared theme toggle
- Intro: app title and the full tokenization-to-sampling story
- Sampler workbench (`#sec-sampling`): two top-aligned columns, a flexible main card and a 300px settings card
  - Main card: scenario type and the Show whitespace toggle in the header, the prompt as token chips with the completion blank inline, the Next token bar list (`#sec-distribution`) with the insight line, and a footer with Pick next token, Sample 100x, Reset, and the sample status
  - Settings card: scenario dropdown, temperature slider and note, top-p slider and note, presets segmented control, the "Order matters" key idea, and the sampling pseudocode under a "Show the code" disclosure
  - Below 900px the settings card stacks above the main card
- Tokenization card (`#sec-tokens`): pre-split illustrative examples with token and character counts, in a two-column grid on the same outer edges as the workbench
- Concepts: delegated accordion cards for tokens, temperature, nucleus sampling, and token-driven behavior

## Module map

- `js/app.js`
  - owns DOM caching, interaction handlers, selected-token state, sample tallies, preset highlighting, and the render loop
- `js/modules/scenarios.js`
  - exports the canned next-token scenario dataset
- `js/modules/sampling.js`
  - exports `softmax()`, greedy decoding at temperature zero, top-p selection, renormalized draws, and tally aggregation
- `js/modules/candidates.js`
  - `buildCandidateRows()` turns the sorted distribution into display rows (shaped odds, renormalized draw chance, cut flag, observed count)
  - `renderCandidateList()` owns the `<ul>` rows. Rows are created once and updated in place, and re-inserted only when the order changes, so bar widths can transition on slider moves. The list carries ARIA table roles so screen readers pair each value with its Token, Odds, Draw, or Seen header. The bars and the "top P cut" divider are hidden from screen readers because the Odds and Draw cells already carry the same values
- `js/modules/token-examples.js`
  - exports static illustrative token chunks, count and whitespace-display helpers, and `splitPromptTokens()` for the prompt chips
- `js/modules/render.js`
  - renders the scenario dropdown options, the prompt chips and completion blank, token examples, the insight line, and the sample status
- shared `js/modules/section-nav.js`
  - builds the sticky frosted section-progress nav and its IntersectionObserver scroll spy
  - shared repo-root module, also used by the prompt-caching app
- `js/modules/accordion.js`
  - provides delegated card-toggle behavior for concept cards

## Sampling data flow

1. The scenario dropdown, a slider, or a preset changes the active scenario or sampling settings.
2. `buildTopPSelection()` applies temperature to logits, softmaxes the result, ranks tokens, and retains the smallest cumulative top-p nucleus.
3. The surviving probabilities are renormalized into `adjustedProb`. Picks and 100-draw tallies both use that distribution.
4. `buildCandidateRows()` keeps the temperature-shaped probability as the bar and odds value, the renormalized value as the Draw column, and the tally as the Seen column and thin second bar.
5. The DOM renderer updates the prompt chips, bar rows, insight line, slider notes, preset highlight, and accessible sample-status copy.

## Layout model

- The page shell and header widen to 1200px (app-local), with the 700px gutter rule restated
- Both workbench cards share one padding, one gap, and one header row height. Inside the main card the header, prompt, bar list, and footer share one left and right edge. Inside the settings card every control field, the segmented control, the key idea, and the disclosure do the same
- Select, buttons, and the segmented track share one control height (`--tk-control-height`)
- Candidate rows and the column-label row share one grid template, so the token, bar, and number columns line up all the way down. The Seen column appears only after **Sample 100x**. On phones, the thin bar carries the tally instead

## Theme model

- `<html>` owns `data-theme="light|dark"`
- Shared shell behavior reads the same `theme` localStorage key as the root gallery
- All colors come from shared tokens, so a theme change needs no JavaScript work in this app
