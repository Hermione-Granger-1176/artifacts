# Maintenance Notes

This document covers long-term stability contracts and recurring upkeep. It does not repeat day-to-day commands or recovery runbooks.

- See [`workspace.md`](workspace.md) for file ownership and generated-output ownership.
- See [`architecture.md`](architecture.md) for the current runtime, build, and CI/CD design.
- See [`operations.md`](operations.md) for exact commands, troubleshooting, and recovery steps.

## Stability contracts

- `Makefile` remains the supported entry point for normal local workflows and the primary entry point for shared CI verification gates.
- Tool scope should live in its owning config file, primarily `pyproject.toml`, `package.json`, `eslint.config.js`, `stylelint.config.js`, `.yamllint.yml`, and `.editorconfig`. Avoid adding overlapping scope rules in multiple places unless a workflow truly needs a narrow exception.
- `pyproject.toml` under `[tool.artifacts]` owns the canonical site URL, site path, and repository URL.
- Generated outputs such as `js/data.js`, `js/gallery-config.js`, README auto markers, `apps/*/thumbnail.webp`, and `_site/` stay outputs. Change their source inputs or generators instead of hand-editing them.
- `_site/` is the deploy artifact, and `gh-pages` is CI-managed deploy state. Neither should be maintained manually.
- `.github/workflows/update.yml` owns the main verify and publish flow. Reusable write logic belongs in `.github/actions/deploy-site/*`, `.github/actions/verified-commit/*`, and `scripts/ci/workflow_helpers.py` instead of being copied into workflow YAML.
- Trusted same-repo PRs may deploy previews and persist thumbnails. Fork PRs remain non-mutating, while same-repo Dependabot pip PRs may receive refreshed Python locks either as a verified branch commit or through a fallback maintenance PR branch.
- Publish steps deploy the verified `_site/` artifact. They do not rebuild from source during deploy.

## Recurring upkeep

- **Workflow changes:** keep action references pinned to full commit SHAs, preserve read-only verification before write-capable publish steps, and keep preview deploy and preview cleanup behavior symmetric.
- **Generator changes:** update matching tests, keep `make validate` aligned with the artifact folder contract, and update workspace docs when ownership or generated-output boundaries change.
- **Dependency changes:** keep declarations and lockfiles in sync. Same-repo Dependabot pip PRs rely on `.github/workflows/refresh-python-locks.yml` and `.github/workflows/commit-python-locks.yml` to refresh Python locks back onto the PR branch when possible or through a fallback maintenance PR branch when direct writeback is not possible. Scheduled lock refreshes use `.github/workflows/refresh-locks.yml` and always open or update a maintenance PR instead of committing directly to `main`.
- **Repository settings:** keep Pages, app IDs, app private keys, branch protection, and the `gh-pages` ruleset aligned with the contract documented in [`architecture.md`](architecture.md#external-github-settings) and audited by `.github/workflows/audit-repo-settings.yml`.
- **Scheduled monitoring:** keep `.github/workflows/live-site-smoke.yml` and `.github/workflows/audit-repo-settings.yml` issue titles stable so their alert issues can be updated and auto-closed instead of duplicating.
- **Pinned actions:** add new third-party actions with full SHAs immediately and let `.github/workflows/refresh-action-shas.yml` keep them current later through a maintenance PR branch instead of committing directly to `main`.

## When contracts change

- Update [`docs/adr/0001-root-publishing-platform.md`](adr/0001-root-publishing-platform.md) if the verified-artifact, fail-closed, or branch-mutation guardrails change.
- Update [`docs/adr/0002-shared-app-system-and-thumbnail-persistence.md`](adr/0002-shared-app-system-and-thumbnail-persistence.md) if thumbnail persistence or the shared app-system contract changes.
- Update [`docs/adr/0003-makefile-first-and-single-source-of-truth.md`](adr/0003-makefile-first-and-single-source-of-truth.md) if the Makefile-first or single-source-of-truth policy changes.
