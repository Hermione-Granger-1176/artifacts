# Verification

## Core formulas

- Temperature scaling divides logits by temperature before exponentiation
- Temperature `0` returns a one-hot greedy distribution without dividing by zero
- Softmax normalizes the temperature-adjusted exponentials into probabilities that sum to `1`
- Top-p keeps adding sorted tokens until the cumulative pre-cutoff probability reaches the requested threshold
- The retained nucleus is renormalized before a draw or tally, so its adjusted probabilities also sum to `1`

## Representative checks

Use these as regression checks after refactors:

1. Temperature `1.0`, top-p `0.70`, default scenario
   - `mat` should lead the sorted distribution
   - the blue bars show post-temperature probabilities and should sum to `100%` across all candidates
   - the muted `off` bars keep their pre-cutoff length, and their tooltips say they are disabled by top-p
2. Temperature `0`, any top-p value, default scenario
   - only the highest-logit token remains in the nucleus
   - the control note says the model always picks the top token, greedy decoding
   - repeated picks always select `mat`
3. Temperature `2.0`, top-p `1.0`
   - every token rejoins the pool and no token label includes `off`
4. Sample 100x at temperature `1.0`, top-p `1.0`
   - amber observed bars appear beside the blue bars and track the renormalized pool values
   - the amber counts in tooltips sum to `100`
   - Reset samples removes the amber dataset without recreating the chart

## End-to-end math check

For the default scenario at temperature `1.0`, the top two logits are `4.2` for `mat` and `3.1` for `floor`. Relative to `mat`, their softmax terms are `exp(0) = 1` and `exp(-1.1) ≈ 0.3329`. Including all eight relative terms gives a denominator of about `1.5560`, so the uncut probabilities are about `64.3%` for `mat` and `21.4%` for `floor`. At top-p `0.70`, `mat` does not cross the threshold alone, but `mat` plus `floor` does. The chart keeps showing `64.3%` and `21.4%`, while the pool and the chart tooltips show the renormalized draw chances of about `75.0%` and `25.0%`.

## Token example checks

- Every example's `tokens.join("")` must equal its source `text`
- Token count is the array length and character count uses Unicode code points
- When whitespace is shown, each leading space becomes a middle dot inside its chip

## Interpretation guardrails

- This app is illustrative, not a production tokenizer or model-serving client
- The token examples teach common BPE patterns but do not claim to match one vendor vocabulary
- The probabilities are conceptual outputs from the local scenario logits in `scenarios.js`
