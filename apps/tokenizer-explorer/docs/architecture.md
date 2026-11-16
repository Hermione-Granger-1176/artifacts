# Architecture

## Page sections

- Header shell: back button, home logo, and shared theme toggle.
- Intro: the app title and the tokenization-to-sampling story.
- Sampler workbench (`#sec-sampling`): two top-aligned columns, a flexible main card and a 300px settings card.
  - Main card: the scenario type and the **Show whitespace** toggle in the header. The prompt appears as token chips with the completion blank inline. The next-token bar list (`#sec-distribution`) comes next, with the insight line. A footer holds **Pick next token**, **Sample 100x**, **Reset**, and the sample status.
  - Settings card: the scenario dropdown, the temperature slider and note, the top-p slider and note, the presets segmented control, the "Order matters" key idea, and the sampling pseudocode under a "Show the code" disclosure.
  - Below 900px the settings card stacks above the main card.
- Tokenization card (`#sec-tokens`): pre-split illustrative examples with token and character counts, in a two-column grid on the same outer edges as the workbench.
- Concepts: delegated accordion cards for tokens, temperature, nucleus sampling, and token-driven behavior.

## Module map

- `js/app.js`
  - owns DOM caching, interaction handlers, the selected-token state, sample tallies, preset highlighting, slider notes, and the render loop.
  - clears the picked-token highlight after 1.8 seconds. It also clears the highlight whenever a slider, preset, or scenario changes the distribution.
- `js/modules/scenarios.js`: the canned next-token scenario dataset.
- `js/modules/sampling.js`
  - `softmax()` returns a one-hot greedy distribution at temperature zero or below.
  - `buildTopPSelection()` ranks tokens, keeps the top-p nucleus, and renormalizes it.
  - `drawToken()` and `tallyDraws()` sample from the renormalized nucleus. They take an injectable random callback.
- `js/modules/candidates.js`
  - `buildCandidateRows()` turns the sorted distribution into display rows: shaped odds, renormalized draw chance, cut flag, and observed count.
  - `renderCandidateList()` owns the `<ul>` rows. Rows are created once and updated in place. They are re-inserted only when the order changes, which lets the bar widths transition on slider moves. The list uses ARIA table roles, so screen readers pair each value with its Token, Odds, Draw, or Seen header. The bars and the "top P cut" divider are hidden from screen readers. The Odds and Draw cells carry the same values.
- `js/modules/token-examples.js`: the static illustrative token chunks, the count and whitespace-display helpers, and `splitPromptTokens()` for the prompt chips.
- `js/modules/render.js`
  - renders the scenario dropdown options, the prompt chips and completion blank, the token examples, the insight line, and the sample status.
  - `renderPromptReserve()` and `renderCopyReserves()` fill the hidden copies that reserve height. `insightReserveCopies()` builds the insight texts for them.
- `../../../js/modules/section-nav.js`: the sticky section-progress nav and its IntersectionObserver scroll spy. The prompt-caching app shares this module.
- `js/modules/accordion.js`: delegated card-toggle behavior for the concept cards.

## Sampling data flow

1. The scenario dropdown, a slider, or a preset changes the active scenario or sampling settings.
2. `buildTopPSelection()` applies temperature to the logits, softmaxes the result, ranks the tokens, and keeps the smallest cumulative top-p nucleus.
3. The surviving probabilities are renormalized into `adjustedProb`. Picks and 100-draw tallies both use that distribution.
4. `buildCandidateRows()` keeps the temperature-shaped probability as the bar and odds value. It puts the renormalized value in the Draw column and the tally in the Seen column and the thin second bar.
5. The DOM renderer updates the prompt chips, bar rows, insight line, slider notes, preset highlight, and the accessible sample-status text.

## Layout model

- The page shell, header, and section nav widen to 1200px. The app sets `--shell-max-width: 1200px`, and the shared shell rules read it, including the 700px gutter rule.
- Below 900px the workbench is one column. Below 700px the tokenization examples are one column too. Below 480px the cards use tighter padding, and **Pick next token** takes a full row.
- Both workbench cards share one padding, one gap, and one header row height. Inside the main card, the header, prompt, bar list, and footer share one left and right edge. Inside the settings card, every control field, the segmented control, the key idea, and the disclosure share those edges.
- The select, the buttons, and the segmented track share one control height (`--tk-control-height`).
- The candidate rows and the column-label row share one grid template, so the token, bar, and number columns line up down the list. The Seen column has content only after **Sample 100x**. Its track is reserved above 480px. At 480px and below, the track is dropped and the thin bar carries the tally. The Seen cells stay in the DOM, visually hidden.

## Layout stability

- Nothing below the prompt moves while the user works. The prompt, the insight line, and the sample status each share one grid cell with hidden copies of every possible text (`renderPromptReserve()` and `renderCopyReserves()`). Each is as tall as its longest text at the current width.
- The "top P cut" divider is drawn over the top edge of the first cut row. The completion blank keeps one border box and the width of the longest candidate word. The whitespace toggle holds both labels in one grid cell.
- The slider notes reserve two lines, so the sliders below them do not move.
- Below 900px the settings card sits above the main card on screen but after it in the markup. The main card sets `overflow-anchor: none`. See [decisions](decisions.md) for the layout reasoning.

## Theme model

- `<html>` owns `data-theme="light|dark"`.
- The shared shell reads the same `theme` localStorage key as the root gallery.
- All colors come from shared tokens. A theme change needs no JavaScript in this app.
