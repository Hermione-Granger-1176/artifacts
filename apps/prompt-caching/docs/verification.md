# Verification

This reference describes automated coverage, numerical examples, and manual checks for Prompt caching, demystified.

## Automated checks

The tests cover these parts of the app:

- `tests/js/apps/prompt-caching/modules.test.js` checks every `math.js` export and the integrity of `data.js`. Assertions cover vocabulary order, attention rows that sum to approximately 1, embedding completeness, and section and summary data.
- `tests/js/apps/prompt-caching/dom.test.js` checks interactions, including stable cached K and V vectors as later tokens are added.
- `make coverage-js` reports coverage against the repository thresholds in `package.json`.
- `make check-local` runs lint, tests, coverage, dependency audits, artifact validation, and generated-file checks.

## Numerical examples

The calculation fixtures use these expected results:

- Savings: 2,000 tokens per request, 500 requests per day, and 30 days produce 30 million tokens per month. At $3 per million tokens, the uncached cost is $90. With 80% cached at $0.30 per million, the cost is `0.2 * 30 * 3 + 0.8 * 30 * 0.30 = $25.20`. Savings equal $64.80 per month. These are simulator assumptions, not a current provider quote.
- Softmax: weights sum to 1, and the largest score has the largest weight.
- Cosine similarity: identical vectors produce 1, orthogonal vectors produce 0, and opposite vectors produce a negative value.
- Character count: the app counts Unicode code points. A standalone emoji counts as one character.

The savings model omits cache-write costs and expiry. [Decisions](decisions.md) explains the steady-state assumption and its limits at low request volumes.

## Manual browser checks

[Workspace operations](../../../docs/operations.md) gives the commands for browser verification. The manual checklist covers the following behavior:

- No CSP violations, inline styles or scripts, or CDN font requests appear in the console.
- Both themes render correctly. The dimension explorer and similarity plot redraw after a theme change.
- The inference demo supports **Generate** and **Reset**.
- The tokenizer switches between text and token IDs.
- The embedding demo supports word and pair selection and **Swap**.
- Attention controls support step navigation, matrix clicks, masking, grid hover, and softmax sliders.
- The KV-cache demo supports **Play**, **Reset**, and comparison mode.
- The cache-hit demo supports **Send**, **Clear**, and the TTL countdown.
- Savings sliders update the calculated totals.

CI generates thumbnails. Local development does not require checked-in thumbnails.
