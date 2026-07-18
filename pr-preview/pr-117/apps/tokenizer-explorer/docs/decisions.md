# Decisions

## Why this is a conceptual simulator

The goal is to explain tokenization, temperature, top-p, and sampling, not to connect to a live tokenizer or model API. Local scenarios keep the artifact deterministic, portable, and easy to verify.

## Why token examples are canned

The tokenization card uses pre-split examples rather than a real tokenizer. Different BPE vocabularies differ, especially for non-English text and emoji, so the page labels them illustrative instead of implying exact production output. This also preserves the self-only CSP and avoids a large tokenizer vocabulary download.

## Why Chart.js is vendored

The former flexbox strips could stretch across the shell and made the distribution hard to read. A local Chart.js 4.4.1 bundle provides a bounded, fixed-height horizontal chart with exact-percent tooltips and smooth in-place updates. Its integrity record lives in `config/vendored_assets.json`, and the chart palette comes from shared CSS custom properties so theme changes stay consistent.

## Why the chart uses temperature-shaped probabilities

The blue dataset shows the distribution after temperature only, so each slider has a distinct visual effect: temperature changes bar lengths, while top-p flips excluded tokens into a disabled state (muted bars with an `off` label) without resizing anything. Renormalized draw chances appear in the tooltips and in the token pool below, which keeps the pre-cutoff probabilities from being mistaken for draw chances while making the disable-then-renormalize order explicit.

## Why draw helpers accept a random callback

`drawToken()` and `tallyDraws()` accept an injectable random callback. The app uses `Math.random`, while tests can use deterministic rolls to verify token selection and tally aggregation exactly.

## Why the shared app system is reused

The page should feel like one product family alongside the bond explainer. Shared tokens, chart-frame rules, header chrome, and theme behavior keep that cohesion while tokenizer-specific layout selectors stay in the app-local stylesheet.

## Deferred items

- More scenarios and domain-specific examples
- A selectable real tokenizer, if its vocabulary can remain local and clearly versioned
- API-backed model comparisons
