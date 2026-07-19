# ADR 0005: Adopt a shared design-token and component system for mature apps

- Status: Accepted
- Date: 2026-07-18
- Amends: ADR 0004, per-artifact app stylesheets

## Context

ADR 0004 moved each app's layout into its own `apps/<slug>/css/app.css`, but the apps still carried their own colors, spacing values, type sizes, and near-duplicate component styling. Stat tiles, chips, toggles, callouts, meters, code windows, and section navs were re-implemented per app with slightly different values, and the same number-formatting, segmented-toggle, section-nav, and chart-theme logic was copied into several app folders.

The result was visual drift between apps that were meant to read as one product, plus no guardrail against an app stylesheet quietly reverting to hard-coded colors or off-scale sizes after it was authored.

## Decision

1. A shared token layer in `css/src/01-tokens.css` defines the artifact-app design tokens under `body.artifact-app` (with a `[data-theme="dark"] body.artifact-app` override): hue colors `--color-{blue,green,red,amber,purple}` each with a `-text` and `-emphasis` variant, note pastels `--note-{yellow,red,blue,green,amber,purple}`, surface and border tokens, `--color-text-on-accent`, a type scale (`--font-size-*` and `--tracking-label`), a spacing scale (`--space-1` through `--space-6` plus `--space-8`), radii (`--radius-{xs,sm,md,pill}`), and `--shadow-card`. In the dark scope every `--color-*-text` remaps to its `--color-*-emphasis` value and the note pastels get dark remaps, so token-based rules follow the theme automatically.
2. A shared component layer in `css/src/04-artifact-components.css` owns reusable `body.artifact-app` families: `.control-field`, `.stat-grid` / `.stat` (with `.is-center`, `.is-caps`, `.is-mono` modifiers), `.chip` (hue tones, `.is-mono`, solid `.is-solid-*`), `.segmented` (`.is-fused`, `.active`), `.meter` / `.meter-fill`, `.app-callout` hue tones, `.section-kicker`, plus shared buttons, inputs, tables, code windows, and `.section-nav`. Apps compose these families instead of restating them.
3. Shared app behavior lives in `js/modules/`: `formatting.js` (number formatting and parsing), `segmented.js` (`initSegmented`), `section-nav.js` (`initSectionNav`, `renderSectionNav`, `scrollToSection`), and `chart-theme.js` (theme-aware Chart.js palette helpers). Apps import these rather than re-implementing them.
4. All four mature apps (loan-amortization, bond-price-vs-rate, tokenizer-explorer, prompt-caching) are migrated onto the shared tokens, components, and modules. Each `app.css` keeps only app-specific dimensions, grids, visualisations, and component variants built on the tokens.
5. `scripts/lint/check_app_css_tokens.py`, exposed as `make lint-app-css-tokens` and wired into `lint` and `ci-web`, forbids color literals in `apps/*/css/*.css`: hex colors, color functions (`rgb()` / `rgba()` / `hsl()` / `oklch()` and friends) whose channels do not start from `var()` or `color-mix()`, `color-mix()` calls that mix no token, and named colors (`transparent` and `currentcolor` stay allowed). It also enforces token usage for `border-radius`, `font-size`, and `letter-spacing`, with small documented allowlists for deliberate sub-token values scoped to the one stylesheet that owns them.

## Consequences

- The apps read as one system, and a palette, spacing, or type change is a single edit in `css/src/01-tokens.css` rather than a sweep across four app folders.
- App stylesheets shrink toward app-specific layout, while a change to a shared token or component is intentional shared work in `css/src/`.
- The token lint keeps app CSS from drifting back to hard-coded colors or off-token sizes after it is authored.
- New shared UI behavior belongs in `js/modules/` and the `css/src/` component layer instead of being copied per app.
- Dark-theme handling is centralized in the token remaps, so authored rules do not need per-theme overrides for the shared palette.

## Out of scope

- This ADR does not change the app-local stylesheet split from ADR 0004; it builds on it.
- This ADR does not change the shared theme bootstrap or app shell behavior from ADR 0002.
