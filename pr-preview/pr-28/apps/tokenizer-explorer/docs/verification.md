# Verification

## Core formulas

- Temperature scaling divides logits by temperature before exponentiation
- Softmax normalizes the exponentials into probabilities that sum to `1`
- Top-p keeps adding sorted tokens until cumulative probability reaches the requested threshold

## Representative checks

Use these as regression checks after refactors:

1. Temperature `1.0`, top-p `0.70`, default scenario
   - The displayed top-p pill count should be small and led by the most likely token
2. Temperature `0.5`, same scenario
   - The leading token should gain relative probability versus the `1.0` baseline
3. Temperature `2.0`, top-p `1.0`
   - Tail tokens should visibly gain width and every token should remain in the candidate pool

## Edge cases

- Temperature `0.1` should strongly sharpen the distribution without throwing numerical errors
- Top-p `1.0` should keep every token in the pool
- A scenario with a single token should still produce one full-width bar and one winner pill

## Interpretation guardrails

- This app is illustrative, not a production tokenizer or model-serving client
- The probabilities are conceptual outputs from the scenario logits defined in `scenarios.js`
