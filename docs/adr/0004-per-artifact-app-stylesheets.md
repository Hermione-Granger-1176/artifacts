# ADR 0004: Split artifact-specific CSS into app-local stylesheets

- Status: Accepted
- Date: 2026-07-11
- Amends: ADR 0002, shared stylesheet decision

## Context

The shared `css/style.css` file grew past 5,000 lines. The Prompt Caching app accounted for about 43 percent of the file, and the root gallery shipped all app-specific CSS even though it did not use it.

Keeping every app layout in the shared file also made an app-local visual change look like a shared runtime change. That invalidated browser test and thumbnail work for every mature app, even when only one app's layout changed.

## Decision

1. `css/style.css` remains the shared stylesheet for font declarations, gallery styles, shared app tokens, and shared app shell rules.
2. Each mature app keeps its layout rules in `apps/<slug>/css/app.css`, loaded after `../../css/style.css` as a second stylesheet.
3. App-specific selectors retain their existing `body.app-<slug>` scope.
4. `apps/<slug>/css/**` is classified as an app-scoped runtime change for CI test selection and thumbnail regeneration.
5. New mature apps are scaffolded with an app-local `css/app.css` starter file and its corresponding stylesheet link.

## Consequences

- The root gallery ships only the shared CSS it uses.
- App-local CSS changes scope CI and thumbnail work to the changed app.
- The shared file still provides the gallery foundation tokens required by `scripts/build/generate_index.py`.
- Mature app pages make two stylesheet requests instead of one.

## Out of scope

- This ADR does not change the shared theme bootstrap or app shell behavior.
- This ADR does not change the thumbnail persistence model from ADR 0002.
