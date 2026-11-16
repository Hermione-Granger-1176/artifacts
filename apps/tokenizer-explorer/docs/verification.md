# Verification

This page lists the sampling rules, the expected results of the regression scenarios, and the commands that run the checks.

## Core formulas

- Temperature scaling divides the logits by the temperature before exponentiation.
- Temperature `0` returns a one-hot greedy distribution without dividing by zero.
- Softmax normalizes the temperature-adjusted exponentials into probabilities that sum to `1`.
- Top-p keeps adding sorted tokens until the cumulative pre-cutoff probability reaches the threshold.
- The retained nucleus is renormalized before a draw or tally, so its adjusted probabilities also sum to `1`.

## Representative checks

The regression scenarios have these expected results:

1. Temperature `1.0`, top-p `0.70`, default scenario
   - `mat` leads the Next token list.
   - The Odds column shows post-temperature probabilities and sums to `100%` across all eight rows.
   - Rows below the "top P cut" line are struck through. Their hatched bars keep their pre-cutoff length, and the Draw column shows `cut`.
2. Temperature `0`, any top-p value, default scenario
   - Only the highest-logit token remains in the nucleus.
   - The control note says the model always picks the top token, which is greedy decoding.
   - Repeated picks always select `mat`.
3. Temperature `2.0`, top-p `1.0`
   - Every token rejoins the pool, and no row sits below a "top P cut" line.
4. Sample 100x at temperature `1.0`, top-p `1.0`
   - A thin amber bar and a Seen count appear in every row. They track the Draw column values.
   - The Seen counts sum to `100`.
   - Reset removes the Seen column and the thin bars.
5. Layout at 1280px
   - The main card and the settings card tops align. The header, prompt, bar list, and footer share one left and right edge in the main card.
   - The completion blank sits on the same line as the last prompt chip.
   - The tokenization card spans from the left edge of the main card to the right edge of the settings card.
   - Below 900px, the settings card sits above the main card.
6. Phone layout at 390px
   - The page has no horizontal scroll. The candidate rows show Token, bar, Odds, and Draw columns.
   - After Sample 100x, the Seen column is hidden and the thin amber bars carry the tally.
7. Layout stability
   - Switching between all six scenarios, moving either slider, and clicking **Pick next token**, **Sample 100x**, and **Reset** does not move the buttons or sliders below the changed text.

## Automated tests

- `tests/js/apps/tokenizer-explorer/sampling.test.js` covers softmax, greedy ties, top-p renormalization, injected-random draws, and the hand-checked default scenario percentages below.
- `tests/js/apps/tokenizer-explorer/modules.test.js` covers the scenario data, token examples, candidate rows, table roles, and hidden reserve copies. It checks that every slider setting lands on a reserved insight line.
- `tests/js/apps/tokenizer-explorer/app.test.js` loads `app.js` against mocks. It drives the sliders, presets, scenario select, pick, tally, reset, and whitespace toggle.

## End-to-end math check

For the default scenario at temperature `1.0`, the top two logits are `4.2` for `mat` and `3.1` for `floor`. Relative to `mat`, their softmax terms are `exp(0) = 1` and `exp(-1.1) ≈ 0.3329`. All eight relative terms give a denominator of about `1.5560`. The uncut probabilities are therefore about `64.3%` for `mat` and `21.4%` for `floor`.

At top-p `0.70`, `mat` alone does not reach the threshold, but `mat` plus `floor` does. The Odds column keeps showing `64.3%` and `21.4%`. The Draw column shows the renormalized draw chances of about `75.0%` and `25.0%`. The top-p note reads "Keeps 2 of 8 tokens, 86% of the odds."

## Token example checks

- Each example's `tokens.join("")` equals its source `text`.
- The token count is the array length. The character count uses Unicode code points.
- When whitespace is shown, each leading space becomes a middle dot inside its chip, in both the examples and the prompt chips.

## Interpretation limits

- The app is illustrative. It is not a production tokenizer or a model-serving client.
- The token examples teach common BPE patterns. They do not claim to match one vendor's vocabulary.
- The probabilities are conceptual outputs from the local scenario logits in `scenarios.js`.

## Re-check

- Node tests: `make test-js`. Coverage thresholds: `make coverage-js`.
- Browser flows: `make test-browser-apps-flows ARGS="-k tokenizer_explorer"`.

Browser targets need Chromium. Run `make setup-playwright` once.
