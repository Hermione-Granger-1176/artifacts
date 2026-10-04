# Verification

## Core formulas

- Temperature scaling divides logits by temperature before exponentiation
- Temperature `0` returns a one-hot greedy distribution without dividing by zero
- Softmax normalizes the temperature-adjusted exponentials into probabilities that sum to `1`
- Top-p keeps adding sorted tokens until the cumulative pre-cutoff probability reaches the requested threshold
- The retained nucleus is renormalized before a draw or tally, so its adjusted probabilities also sum to `1`

## Representative checks

The regression scenarios have these expected results:

1. Temperature `1.0`, top-p `0.70`, default scenario
   - `mat` leads the Next token list
   - the Odds column shows post-temperature probabilities and sums to `100%` across all eight rows
   - rows below the "top P cut" line are struck through, have hatched bars that keep their pre-cutoff length, and show `cut` in the Draw column
2. Temperature `0`, any top-p value, default scenario
   - only the highest-logit token remains in the nucleus
   - the control note says the model always picks the top token, greedy decoding
   - repeated picks always select `mat`
3. Temperature `2.0`, top-p `1.0`
   - every token rejoins the pool and no row sits below a "top P cut" line
4. Sample 100x at temperature `1.0`, top-p `1.0`
   - a thin amber bar and a Seen count appear in every row, tracking the Draw column values
   - the Seen counts sum to `100`
   - Reset removes the Seen column and the thin bars
5. Layout
   - at 1280px wide the main card and the settings card tops align, and the header, prompt, bar list, and footer share one left and right edge in the main card
   - the completion blank sits on the same line as the last prompt chip
   - below 900px the settings card sits above the main card
   - the tokenization card spans the left edge of the main card to the right edge of the settings card

## End-to-end math check

For the default scenario at temperature `1.0`, the top two logits are `4.2` for `mat` and `3.1` for `floor`. Relative to `mat`, their softmax terms are `exp(0) = 1` and `exp(-1.1) ≈ 0.3329`. Including all eight relative terms gives a denominator of about `1.5560`, so the uncut probabilities are about `64.3%` for `mat` and `21.4%` for `floor`. At top-p `0.70`, `mat` does not cross the threshold alone, but `mat` plus `floor` does. The Odds column keeps showing `64.3%` and `21.4%`, while the Draw column shows the renormalized draw chances of about `75.0%` and `25.0%`, and the top-p note reads "Keeps 2 of 8 tokens, 86% of the odds."

## Token example checks

- Every example's `tokens.join("")` must equal its source `text`
- Token count is the array length and character count uses Unicode code points
- When whitespace is shown, each leading space becomes a middle dot inside its chip, in both the examples and the prompt chips

## Interpretation limits

- This app is illustrative, not a production tokenizer or model-serving client
- The token examples teach common BPE patterns but do not claim to match one vendor vocabulary
- The probabilities are conceptual outputs from the local scenario logits in `scenarios.js`
