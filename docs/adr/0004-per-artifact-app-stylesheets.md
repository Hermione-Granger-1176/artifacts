# ADR 0004: Split artifact-specific CSS into app-local stylesheets

- Status: Accepted
- Date: 2026-07-11
- Amends: ADR 0002, shared stylesheet decision

## Context

The shared `css/style.css` file grew past 5,000 lines. The Prompt Caching app accounted for about 43 percent of the file, and the root gallery shipped all app-specific CSS even though it did not use it.

Keeping every app layout in the shared file also made an app-local visual change look like a shared runtime change. That invalidated browser test and thumbnail work for every mature app, even when only one app's layout changed.

## Decision

1. The ordered `css/src/` source partials own shared font declarations, gallery styles, app tokens, shell rules, reusable app components such as surfaces, buttons, inputs, toggles, and callouts, accessibility utilities, and responsive rules. `make styles` deterministically bundles them into the single public `css/style.css` stylesheet.
2. Each mature app keeps only its app-specific composition and layout rules in `apps/<slug>/css/app.css`, loaded after `../../css/style.css` as a second stylesheet. These rules cover app-specific dimensions, grids, visualisations, and component variants rather than repeating shared component foundations.
3. App-specific selectors retain their existing `body.app-<slug>` scope.
4. `apps/<slug>/css/**` is classified as an app-scoped runtime change for CI test selection and thumbnail regeneration.
5. New mature apps are scaffolded with an app-local `css/app.css` starter file and its corresponding stylesheet link.

## Consequences

- The root gallery ships only the generated shared CSS it uses, with no browser-side stylesheet imports or app-specific CSS.
- App-local CSS changes scope CI and thumbnail work to the changed app.
- A common component change is intentional shared work in `css/src/`, while an app-local stylesheet stays focused on the structure and behaviour unique to that artifact.
- The generated public file still provides the gallery foundation tokens required by `scripts/build/generate_index.py`.
- Mature app pages make two stylesheet requests instead of one.
- Source partials are not deployed, so the source split has no additional runtime requests.

## Out of scope

- This ADR does not change the shared theme bootstrap or app shell behavior.
- This ADR does not change the thumbnail persistence model from ADR 0002.
