# ADR 0002: Use a shared app system with planner-driven thumbnail persistence

- Status: Accepted
- Date: 2026-03-26

## Context

The repository now contains mature app folders under `apps/` that share the same brand system, theme behavior, and navigation shell. At the same time, thumbnail generation and persistence need to stay strict enough that:

- trusted same-repo PRs can update thumbnails in the same PR branch,
- trusted `main` pushes can open or update a follow-up thumbnail PR,
- fork PRs, Dependabot PRs, docs-only changes, and metadata-only changes do not mutate source branches,
- preview cleanup and `gh-pages` deploy behavior remain isolated from source-branch persistence,
- expensive work such as Playwright thumbnail generation happens only once per run.

The earlier workflow shape mixed planning, build, deploy, and source-branch mutation inside one long path, which made trust boundaries and loop prevention harder to reason about.

## Decision

1. Mature apps share root-level styling from `css/style.css` and shell behavior from `js/app-theme.js` and `js/modules/app-shell.js`.
2. App-local JS lives inside each app folder and only owns app-specific runtime behavior. App-specific layout selectors live in the shared stylesheet and are scoped by `app-<slug>` body classes.
3. Workflow policy is driven by a single planner implemented in `scripts/build/thumbnail_plan.py` and exposed to workflows through `scripts/ci/workflow_helpers.py`.
4. Thumbnail generation runs once in the verified build path, and later jobs reuse the generated artifact instead of regenerating thumbnails.
5. Thumbnail persistence is deny-by-default and allows only three modes:
   - `none`
   - `pr-branch`
   - `followup-pr`
6. Pushes to `main` never write thumbnails directly back to `main`; they create or update a follow-up PR.
7. The merge of that follow-up thumbnail PR is recognized through PR provenance rather than commit-message heuristics, so loop prevention is stable under squash-merge settings.
8. Thumbnail persistence artifacts may contain only `apps/<slug>/thumbnail.webp` files plus planner metadata.

## Amendment (ADR 0004)

ADR 0004 split app-specific layout out of the shared stylesheet. Decision point 2 above should now be read as: app-specific layout lives in `apps/<slug>/css/app.css`, while the shared tokens, shell, and component families live in the generated shared stylesheet (`css/style.css`, built from `css/src/`). App-local JS still owns only app-specific runtime behavior as stated.

## Consequences

- Shared app styling is easier to evolve because the shared stylesheet owns the shell, tokens, and reusable component families, while each app-local `apps/<slug>/css/app.css` owns app-specific layout (see the ADR 0004 amendment above).
- Thumbnail generation more closely matches the real app runtime because it waits for app readiness and uses the shared app shell over HTTP.
- Workflow YAML is more readable because it delegates policy to tested helpers and keeps build, deploy, and persistence responsibilities separate.
- Source-branch mutation is tightly scoped to trusted runtime changes and validated thumbnail artifacts only.

## Out of scope

- This ADR does not change the strict publishing-platform requirements from ADR 0001.
- This ADR does not resolve unrelated dependency-audit policy decisions.
