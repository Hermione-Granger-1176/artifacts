# ADR 0007: Keep themed colors in line-matched light and dark files

- Status: Accepted
- Date: 2026-10-05
- Amends: ADR 0006, shared design tokens and component system

## Context

ADR 0006 put the app tokens in `css/src/01-tokens.css`, with a `[data-theme="dark"] body.artifact-app` override for the dark values. Components and app stylesheets also added their own `[data-theme="dark"]` color rules. Dark colors ended up spread across `01-tokens.css`, `02-gallery.css`, `04-artifact-components.css`, and three app stylesheets, so a dark-theme redesign had to find and change each of them.

## Decision

1. `css/src/01-theme-light.css` and `css/src/01-theme-dark.css` own every color that changes with the theme, for both the gallery (`:root`) and the apps (`body.artifact-app`).
2. The two files declare the same tokens on the same lines, so a diff between them shows only the values. `scripts/build/generate_styles.py` fails `make styles` when a line declares different tokens in the two files.
3. `css/src/01-tokens.css` keeps the tokens that stay the same in both themes: fonts, the bookmark-note palette, the printed-document palette, card colors, the type and spacing scales, and radii.
4. Components and app stylesheets do not write `[data-theme="dark"]` color rules. A color that differs by theme becomes a themed token in both files.

## Consequences

- A theme redesign changes values in one file and leaves component rules alone.
- Adding a themed color takes two edits, one line in each theme file.
- The dark selectors outrank the light ones, so the order of the two files in `css/style.css` does not matter.

## Out of scope

- This ADR does not change the token families, the component layer, or the app CSS token lint from ADR 0006.
