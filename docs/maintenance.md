# Maintain the workspace

Use the periodic checklist to keep the workspace healthy. Use the sections after it when a change touches a shared contract. [Operations](operations.md) lists the daily commands, [Workspace structure](workspace.md) lists file ownership, and [Architecture](architecture.md) describes the deploy design.

## Periodic checklist

Automation opens most upkeep work as pull requests and alert issues. [Auxiliary workflows](ci.md#auxiliary-workflows) lists each schedule.

Weekly:

- [ ] Review the maintenance PR from `refresh-locks.yml`.
- [ ] Review each open alert issue listed in [Preserve alert issue identities](#preserve-alert-issue-identities).
- [ ] If the settings audit reports drift, run `make ci-audit-repo-settings` and fix the drift in GitHub.

Monthly:

- [ ] Review the maintenance PRs from `refresh-action-shas.yml` and `refresh-playwright.yml`.
- [ ] Review open Dependabot PRs.

If the watchdog reports a stale schedule, check that the workflow is enabled in Actions and re-enable it. [Quality checks](checks.md#scheduled-monitoring) describes what the watchdog detects.

## Preserve shared contracts

- Use the Makefile for local workflows and shared CI gates.
- Keep each tool's scope in its configuration file. See [Tool configuration](workspace.md#tool-configuration).
- Keep the site URL, site path, and repository URL under `[tool.artifacts]` in `pyproject.toml`.
- Change the inputs or the generator for a generated file. Do not edit `_site/` or the `gh-pages` branch by hand.
- Keep the main verification and publish flow in `.github/workflows/update.yml`. Route writes through `.github/actions/` and `scripts/ci/`.
- Keep the trust limits on previews, thumbnail persistence, and Dependabot lock updates. See [CI and deployment](ci.md).
- Deploy the verified `_site/` artifact. Do not rebuild during publish.

## Review workflow changes

- Pin each third-party action to a full commit SHA when you add it.
- Keep verification jobs read-only. Each one passes before any job that writes runs.
- Keep preview deploy and preview cleanup in step. Each path that `publish` writes must also be removed by `cleanup-preview` and by the merged-PR cleanup in `publish`.
- Update `tests/ci/test_workflow_contracts.py` when job dependencies, step names, or cache keys change.
- Update [ADR 0005](adr/0005-ci-scaling-architecture-and-roadmap.md) when the CI design changes, including its roadmap.

## Review generator changes

- Update the matching tests and keep `make validate` consistent with the artifact contract.
- When a generated file gets a new owner, update [Generated and derived files](workspace.md#generated-and-derived-files).

## Refresh dependencies

- Keep dependency declarations and lockfiles in sync. Use `make lock` for Python and `make lock-node` for Node.
- Run `make refresh-ci-pins` to update the Playwright package and its matching official image digest together.
- For Dependabot uv updates, `refresh-python-locks.yml` and `commit-python-locks.yml` must keep these checks:

  1. Validate the identity of the triggering workflow run.
  2. Require downloaded metadata to match the trusted PR, SHA, and branch.
  3. Reject unsafe artifacts and stale branch heads before writeback.
  4. Write through a verified PR-branch commit, or fall back to a maintenance PR.

## Check stricter rules

After you change lint, type, dead-code, format, or coverage rules, run `make lint`, `make typecheck`, `make dead-code`, `make format-check`, `make test-py`, `make coverage-js`, and `make coverage-js-floors`. Add focused tests for new branches or exceptions.

## Review repository settings

Keep Pages, GitHub App credentials, branch protection, and the `gh-pages` ruleset consistent with [External GitHub settings](ci.md#external-github-settings). Run `make ci-audit-repo-settings` to check for drift, and `make ci-audit-previews` to list `gh-pages` previews whose PR is closed.

## Preserve alert issue identities

Keep alert titles stable so that failed and recovered runs update the same issue. Each workflow closes its issue after the check passes again.

| Workflow                   | Alert issue title                                             |
| -------------------------- | ------------------------------------------------------------- |
| `live-site-smoke.yml`      | Live site smoke check failed                                  |
| `audit-repo-settings.yml`  | Repository settings drift detected                            |
| `deploy-failure-alert.yml` | Main deploy pipeline failed                                   |
| `schedule-watchdog.yml`    | Scheduled workflow watchdog found stale or disabled schedules |
| `dependency-audit.yml`     | Dependency audit failed                                       |

## Update decision records

When a contract changes, update the matching record:

- [ADR 0001](adr/0001-root-publishing-platform.md) for verified artifacts, blocked publication after failed checks, or source-branch write restrictions.
- [ADR 0002](adr/0002-shared-app-system-and-thumbnail-persistence.md) for thumbnail persistence or the shared app system.
- [ADR 0003](adr/0003-makefile-first-and-single-source-of-truth.md) for Makefile use or configuration ownership.
- [ADR 0004](adr/0004-per-artifact-app-stylesheets.md) for app-local stylesheets or CSS ownership.
- [ADR 0005](adr/0005-ci-scaling-architecture-and-roadmap.md) for impact planning, shards, verification ledgers, or CI caches. Update its roadmap as work lands.
- [ADR 0006](adr/0006-shared-design-tokens-and-component-system.md) for shared tokens, components, frontend helpers, or app CSS token checks.
- [ADR 0007](adr/0007-line-matched-theme-files.md) for themed colors or the light and dark theme files.
- [ADR 0008](adr/0008-graphql-first-rest-fallback.md) for the `scripts/gh/` helpers or their REST fallback.
