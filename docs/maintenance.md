# Maintain the workspace

Use this checklist when changes affect shared behavior, dependencies, automation, or repository settings. [Operations](operations.md) covers daily commands and recovery. [Workspace structure](workspace.md) lists file ownership, and [Architecture](architecture.md) explains the deployment design.

## Preserve shared contracts

For changes to tooling or deployment, check these rules:

- Use the Makefile for local workflows and shared CI gates.
- Keep tool scope in the owning configuration file. Avoid duplicate file selection in targets and workflows.
- Keep site URL, site path, and repository URL under `[tool.artifacts]` in `pyproject.toml`.
- Change inputs or generators for generated files. Do not maintain `_site/` or `gh-pages` by hand.
- Keep the main verification and publish flow in `.github/workflows/update.yml`. Reuse the shared deployment actions and workflow helpers for writes.
- Preserve trust restrictions on previews, thumbnail persistence, and Dependabot lock updates.
- Deploy the verified `_site/` artifact without rebuilding during publish.

## Review workflow changes

Pin action references to full commit SHAs. Keep verification read-only and require it before write-capable jobs. Preserve matching preview deploy and cleanup behavior.

For a new third-party action, add its full SHA immediately. `refresh-action-shas.yml` pins non-SHA references through a maintenance PR, but does not advance existing full-SHA pins.

Update `tests/ci/test_workflow_contracts.py` when job dependencies, step names, or cache keys change. [ADR 0005](adr/0005-ci-scaling-architecture-and-roadmap.md) records the CI design and rejected alternatives.

## Review generator changes

Update the matching tests and keep `make validate` consistent with the artifact contract. If ownership of generated files changes, update [Workspace structure](workspace.md).

## Refresh dependencies

Keep dependency declarations and lockfiles synchronized. For local edits, use the lock targets in [Operations](operations.md).

For Dependabot uv updates, preserve these checks in `refresh-python-locks.yml` and `commit-python-locks.yml`:

1. Validate the triggering workflow-run identity.
2. Require downloaded metadata to match the trusted PR, SHA, and branch.
3. Reject unsafe artifacts and stale branch heads before writeback.
4. Use a verified PR-branch commit or a fallback maintenance PR.

Scheduled `refresh-locks.yml` updates use maintenance PRs instead of direct commits to `main`. `refresh-playwright.yml` uses `make refresh-ci-pins` to update the locked Playwright package and matching official image digest together.

## Check stricter rules

After changing lint, type, dead-code, format, or coverage rules, run `make lint`, `make typecheck`, `make dead-code`, `make format-check`, `make test-py`, `make coverage-js`, and `make coverage-js-floors`. Add focused tests for new branches or exceptions.

## Review repository settings

Keep Pages, GitHub App credentials, branch protection, and the `gh-pages` ruleset consistent with [External GitHub settings](architecture.md#external-github-settings). Use `make ci-audit-repo-settings` to check drift.

## Preserve alert issue identities

Keep alert titles stable so failed and recovered runs update the same issue. The alert workflows are:

- `live-site-smoke.yml`, for published-site browser failures.
- `audit-repo-settings.yml`, for repository-settings drift.
- `deploy-failure-alert.yml`, for completed `Update Artifacts & Deploy` runs on `main`. It updates `Main deploy pipeline failed` after a failure and closes the issue after success.
- `schedule-watchdog.yml`, for inactive scheduled workflows. It updates `Scheduled workflow watchdog found stale or disabled schedules` and closes the issue when every scheduled workflow is active.

The deploy alert uses `workflow_run`, so scheduled-trigger inactivity does not disable it. The schedule watchdog runs on pushes and manual dispatch because a disabled schedule cannot report its own disabled state.

If a scheduled workflow stops appearing in Actions, inspect its enabled state and re-enable it if needed. The watchdog discovers workflows with cron schedules and checks their API `state`. It does not inspect run history or detect an active workflow that stops firing. Each scheduled check owns its result alerts.

## Update decision records

When a contract changes, update the corresponding record:

- [ADR 0001](adr/0001-root-publishing-platform.md), for verified artifacts, blocked publication after failed checks, or source-branch write restrictions.
- [ADR 0002](adr/0002-shared-app-system-and-thumbnail-persistence.md), for thumbnail persistence or the shared app system.
- [ADR 0003](adr/0003-makefile-first-and-single-source-of-truth.md), for Makefile use or configuration ownership.
- [ADR 0004](adr/0004-per-artifact-app-stylesheets.md), for app-local stylesheets or CSS ownership.
- [ADR 0005](adr/0005-ci-scaling-architecture-and-roadmap.md), for impact planning, shards, verification ledgers, or CI caches. Update its roadmap as work lands.
- [ADR 0006](adr/0006-shared-design-tokens-and-component-system.md), for shared tokens, components, frontend helpers, or app CSS token checks.
- [ADR 0007](adr/0007-line-matched-theme-files.md), for themed colors or the light and dark theme files.
