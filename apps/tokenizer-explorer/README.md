# Tokenizer: Temperature & Top P Explorer

Interactive explainer for LLM next-token probabilities, temperature scaling, and top-p sampling.

## Features

- Compare multiple prompt scenarios across writing, code, factual, and chat contexts
- Adjust temperature and top-p to see how the candidate distribution reshapes in real time
- Inspect token bars, surviving top-p candidates, and plain-language guidance
- Read expandable concept cards explaining tokens, temperature, and nucleus sampling
- Share the same header, theme model, and design system as the rest of the mature app suite

## Structure

- `index.html` - app shell, semantic content, metadata, and header
- `../../css/style.css` - shared site stylesheet, including tokenizer layout and visual selectors
- `js/app.js` - bootstrap, tab selection, and render loop orchestration
- `js/modules/scenarios.js` - scenario dataset
- `js/modules/sampling.js` - softmax and top-p selection logic
- `js/modules/render.js` - DOM rendering for tabs, bars, pills, and insights
- `js/modules/accordion.js` - delegated concept-card expansion behavior
- `docs/` - architecture notes, verification references, and implementation decisions

## Dependencies

- No runtime dependencies beyond browser-native HTML, CSS, and ES modules

## Development notes

- Keep authored colors in `rgb()` and `rgba()` form only
- Reuse the shared bookmark-note token system before adding new colors
- Preserve the conceptual behavior of the sliders and top-p cutoff when refactoring markup or structure
