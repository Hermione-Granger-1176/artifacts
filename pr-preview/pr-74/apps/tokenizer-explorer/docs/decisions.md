# Decisions

## Why this is a conceptual simulator

The goal is to explain temperature and top-p, not to connect to a live tokenizer or model API. Hardcoded scenarios keep the artifact deterministic and easy to verify.

## Why scenario data is local

Static data avoids network dependencies, keeps the artifact portable, and makes browser tests straightforward.

## Why the shared app system is reused

The page should feel like one product family alongside the loan calculator. Shared tokens, header chrome, and theme behavior keep that cohesion while local CSS handles only tokenizer-specific layout.

## Why the app exposes a ready signal

`window.__ARTIFACT_READY__` is set after the first render so thumbnail generation can wait for tabs, bars, pills, and insight text to populate before taking a screenshot.

## Why active blue UI states are contrast-checked

The tokenizer relies on blue active tabs and slider-driven emphasis, so the browser test suite checks those blue note-surface states in both light and dark themes to guard against accidental contrast regressions.

## Deferred items

- More scenarios and domain-specific examples
- Real tokenizer vocabulary visualization
- API-backed model comparisons
