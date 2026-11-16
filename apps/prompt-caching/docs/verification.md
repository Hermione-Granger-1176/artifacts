# Verification

This page lists the automated checks, the expected numerical results, and the manual browser checks for Prompt caching, demystified.

## Automated checks

- `tests/js/apps/prompt-caching/modules.test.js` checks every `math.js` export and the integrity of `data.js`. Assertions cover the vocabulary order, attention rows that sum to about 1, the Q, K, and score matrices matching the rounded products of their inputs, embedding completeness, summary data, and the nine anchored nav stages in `index.html`.
- `tests/js/apps/prompt-caching/dom.test.js` drives every demo through a DOM harness with controllable timers. It checks interactions, stable cached K and V vectors as tokens are added, the space each demo reserves for its largest state, the attention card's measurement timing, the reduced-motion paths, and the redraw of the embedding canvases on a theme change.
- `tests/browser/test_frontend_apps_browser_flows.py` (`-k prompt_caching`) runs the calculator, attention, and embedding flows in a browser.

## Re-check

- Node tests: `make test-js`. Coverage thresholds: `make coverage-js`.
- Browser flows: `make test-browser-apps-flows ARGS="-k prompt_caching"`.
- Full local gate: `make check-local`.

Browser targets need Chromium. Run `make setup-playwright` once.

## Numerical examples

- Savings: 2,000 tokens per request, 500 requests per day, and 30 days give 30 million tokens per month. At $3 per million tokens, the uncached cost is $90. With 80% cached at $0.30 per million, the cost is `0.2 * 30 * 3 + 0.8 * 30 * 0.30 = $25.20`. Savings are $64.80 per month. These are simulator assumptions, not a current provider price.
- Softmax: weights sum to 1, and the largest score has the largest weight.
- Cosine similarity: identical vectors give 1, orthogonal vectors give 0, and opposite vectors give a negative value.
- Character count: the app counts Unicode code points. A standalone emoji counts as one character.

The savings model omits cache-write costs and expiry. [Decisions](decisions.md) explains the steady-state assumption and its limits at low request volumes.

## Manual browser checks

The [operations guide](../../../docs/operations.md) covers browser setup. Check the following:

- The console shows no CSP violations, inline styles or scripts, or font requests to a CDN.
- Both themes render correctly. The dimension explorer and the similarity plot redraw after a theme change.
- **Generate** and **Reset** work in the inference demo.
- The tokenizer switches between text and token IDs.
- The embedding demo supports word and pair selection and **Swap**.
- Attention controls support step navigation, matrix clicks, masking, grid hover, and softmax sliders.
- **Play**, **Reset**, and comparison mode work in the KV-cache demo.
- **Send**, **Clear**, and the TTL countdown work in the cache-hit demo.
- The savings sliders update the calculated totals.

Thumbnails come from CI. See [thumbnail policy](../../../docs/operations.md#thumbnail-policy).
