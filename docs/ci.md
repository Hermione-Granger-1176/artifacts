# CI and deployment

GitHub Actions carries each commit from a pull request to the live site. The workflow files and helper scripts are the executable source of truth. This page describes how they fit together.

## Main pipeline (`update.yml`)

`.github/workflows/update.yml` runs on pushes to `main`, on `pull_request` events (opened, reopened, synchronize, closed) into `main`, on the weekly full sweep (`cron: 23 4 * * 0`, Sunday 04:23 UTC), and on manual dispatch. Dispatch defaults `full-sweep` to true.

`plan` starts `quick-gates`. Those cheap gates must pass before `heavy-checks`, `root-browser`, and the `app-shard` matrix start. `assemble-site` builds and uploads `_site/` once. `verify` aggregates every job above and gates `publish` and `save-app-ledger`. `persist-thumbnails` runs after `publish`. [ADR 0005](adr/0005-ci-scaling-architecture-and-roadmap.md) records the scaling rationale.

`runtime_change_plan` in `scripts/lib/app_discovery.py` maps changed files to apps. A change to an app's `index.html`, `js/`, `css/`, or `assets/` marks that app. A change to its `docs/`, `README.md`, or metadata files (`name.txt`, `description.txt`, `tags.txt`, `tools.txt`) marks nothing. A change to `css/style.css`, `js/app-theme.js`, or `js/modules/app-shell.js` marks every app. Other files under `js/modules/`, outside `js/modules/gallery/`, mark the apps that import them, or every app when none do. A change to a shared app browser test under `tests/browser/` widens the browser scope to every app.

Apps with a `js/app.js` go into shards of 20, with at most 128 shards (`scripts/ci/app_shards.py`). Apps whose input hash already passed on `main` drop out of the shards through the app ledger. A ledger read failure runs full verification.

## Pipeline walkthrough by scenario

Each scenario gives its trigger, the jobs it runs, and what it deploys or writes. `.github/workflows/update.yml` defines the steps, timeouts, permissions, and conditions.

### Same-repo PR push

A `pull_request` event with `opened`, `reopened`, or `synchronize` starts the run when the head repository is this repository and the author is not `dependabot[bot]`. `plan`, `secret-scan`, and `dependency-review` start first. The verification jobs, `assemble-site`, and `verify` follow. `publish` deploys the build to `pr-preview/pr-N/` on `gh-pages` and browser-tests that preview URL. The run also updates a sticky PR comment with the preview URL. If thumbnails changed, `persist-thumbnails` commits `apps/*/thumbnail.webp` to the PR branch with the Hermione1176 token. It skips the commit when the PR branch has moved. The commit starts a second run that skips verification (see [Verification skip for automated thumbnail commits](#verification-skip-for-automated-thumbnail-commits)).

### Push to main

A push to `main` starts the run. `workflow_dispatch` and the weekly schedule take the same path with a full sweep and `persist-mode` set to `none`. `dependency-review` does not run. `save-app-ledger` runs after `verify` and records the main-verified app hashes in the Actions cache.

`publish` replaces the `gh-pages` root with the new site. For a merged PR, it also removes that PR's `pr-preview/pr-N/` subtree, so one deployment covers both. It then verifies the live URL, browser-tests it, and creates a `github-pages` deployment record marked `success` or `failure`. If runtime changes or missing thumbnails call for it, `persist-thumbnails` opens or updates the follow-up PR `ci/save-generated-thumbnails-YYYYMMDD` with the Harry1176 token.

### Close an unmerged PR

`cleanup-preview` is the only job that runs when a PR closes without merging. It removes `pr-preview/pr-N/` from `gh-pages`, redeploys the Pages tree, and deletes the sticky preview comment. A merged PR skips this job, because the push to `main` removes its preview. Without tokens (fork or Dependabot PR), the job does nothing.

### Fork PR or Dependabot PR

The verification jobs and `assemble-site` run in full, so the code is built and tested. `publish` skips token minting and logs the skip to the step summary. It deploys nothing and runs no live browser tests. `persist-thumbnails` does not run, so nothing writes back to the branch.

### Branch write summary

| Branch                                    | Written by            | When                                                              | What is written                                                             |
| ----------------------------------------- | --------------------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------- |
| PR branch (for example `feature/new-app`) | `persist-thumbnails`  | Trusted same-repo PR with runtime changes or missing thumbnails   | `apps/*/thumbnail.webp` through a verified commit (Hermione1176)            |
| Dependabot PR branch                      | `commit-python-locks` | Same-repo Dependabot uv PR, when the direct verified commit works | `uv.lock` through a verified commit                                         |
| `ci/refresh-python-locks-*`               | `commit-python-locks` | Same-repo Dependabot uv PR, when the write falls back to a branch | Refreshed `uv.lock`                                                         |
| `ci/refresh-action-shas-*`                | `refresh-action-shas` | Monthly or manual run                                             | Workflow SHA pins                                                           |
| `ci/refresh-playwright-*`                 | `refresh-playwright`  | Monthly or manual run                                             | `pyproject.toml`, `uv.lock`, and workflow image pins                        |
| `ci/refresh-locks-*`                      | `refresh-locks`       | Weekly or manual run                                              | Refreshed dependency locks                                                  |
| `gh-pages`                                | `publish`             | Every successful deploy                                           | Verified commit replacing the site root or preview subdirectory (Harry1176) |
| `gh-pages`                                | `cleanup-preview`     | Unmerged PR closed                                                | Verified commit removing the preview subdirectory (Harry1176)               |
| `ci/save-generated-thumbnails-*`          | `persist-thumbnails`  | Push to `main` with runtime changes or missing thumbnails         | Follow-up PR branch with `thumbnail.webp` files (Harry1176)                 |

## Auxiliary workflows

- **Python lock refresh.** On a same-repo Dependabot uv PR, `refresh-python-locks.yml` runs `make lock` and uploads `uv.lock`. `commit-python-locks.yml` checks that the triggering run, artifact, PR, SHA, and branch match. It rejects symlinks and missing files, confirms the branch has not moved, and writes the lock to the PR branch or a `ci/refresh-python-locks-*` branch.
- **Action SHA pinning.** `refresh-action-shas.yml` pins `uses:` refs that are not full SHAs and opens or updates a maintenance PR. It does not move existing pins.
- **Playwright pin refresh.** `refresh-playwright.yml` runs `make refresh-ci-pins`, which updates the locked Playwright version and its official image digest. It opens one maintenance PR that changes `pyproject.toml`, `uv.lock`, `update.yml`, and `live-site-smoke.yml` together.
- **Dependency lock refresh.** `refresh-locks.yml` runs `make lock` and `make lock-node` and opens or updates a maintenance PR for lock changes.
- **Repo settings audit.** `audit-repo-settings.yml` runs `make ci-audit-repo-settings` and `make ci-audit-previews`. It reports drift from [External GitHub settings](#external-github-settings) and preview directories whose PR is no longer open. Drift goes to the step summary and to a dedicated issue, which closes once the audit passes.
- **Live site smoke.** `live-site-smoke.yml` runs `make test-browser-live` against the published site daily and on dispatch. On failure it uploads Playwright artifacts and opens or updates an alert issue, which closes after a passing run.
- **Deploy failure alert.** `deploy-failure-alert.yml` opens, updates, or closes one alert issue after each `update.yml` run on `main`. Pull request and fork runs are ignored.
- **Schedule watchdog.** GitHub disables cron triggers after about 60 days without repository activity, and a disabled schedule cannot alert on itself. `schedule-watchdog.yml` runs on pushes to `main` and checks that every workflow with a cron schedule is active. It opens or updates the watchdog issue when one is not, and closes it when all are. It does not read run history.
- **CodeQL.** `codeql.yml` analyzes JavaScript and TypeScript, Python, and the workflows. `.github/codeql/codeql-config.yml` limits the scan, and results go to code scanning. It needs no app tokens.
- **Dependency audit.** `dependency-audit.yml` runs `make audit-python`, `make audit-node`, `make audit-vendored`, and `make check-overrides`. `make ci-alert-issue` then opens, updates, or closes one alert issue, and the run fails if any audit failed. It uses the workflow token, not an app token.

## Workflow reference

| File                       | Triggers                                                                    | Jobs                                                                                                                                                                           |
| -------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `update.yml`               | push to main, PR (open/sync/close), weekly Sun 04:23 UTC full sweep, manual | plan, quick-gates, heavy-checks, root-browser, app-shard, assemble-site, verify, secret-scan, dependency-review, save-app-ledger, publish, persist-thumbnails, cleanup-preview |
| `audit-repo-settings.yml`  | weekly Mon 08:23 UTC, manual                                                | audit                                                                                                                                                                          |
| `live-site-smoke.yml`      | daily 06:17 UTC, manual                                                     | smoke, setup-failure-alert                                                                                                                                                     |
| `codeql.yml`               | push to main, PR to main, weekly Mon 06:30 UTC, manual                      | analyze-javascript, analyze-python, analyze-actions                                                                                                                            |
| `dependency-audit.yml`     | weekly Mon 06:00 UTC, manual                                                | audit                                                                                                                                                                          |
| `refresh-python-locks.yml` | same-repo Dependabot uv PR (`pyproject.toml`, `uv.lock`)                    | refresh-locks                                                                                                                                                                  |
| `commit-python-locks.yml`  | after refresh-python-locks completes                                        | commit-locks                                                                                                                                                                   |
| `refresh-action-shas.yml`  | monthly 1st 03:00 UTC, manual                                               | refresh                                                                                                                                                                        |
| `refresh-playwright.yml`   | monthly 1st 03:17 UTC, manual                                               | refresh                                                                                                                                                                        |
| `refresh-locks.yml`        | weekly Mon 12:00 UTC, manual                                                | refresh                                                                                                                                                                        |
| `deploy-failure-alert.yml` | after Update Artifacts & Deploy completes (main only)                       | alert                                                                                                                                                                          |
| `schedule-watchdog.yml`    | push to main, manual                                                        | watchdog                                                                                                                                                                       |

## Custom actions

| Action            | Purpose                                                                  | Key behavior                                                                                                                                                                         |
| ----------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `ci-setup`        | Set up Python and Node, install browsers on request, and mint app tokens | `app-token-policy` blocks minting for forks and Dependabot. Primary and escalation credentials must be passed together. `browser-engines` defaults to empty.                         |
| `deploy-site`     | Build `_site/` and commit the deploy tree to `gh-pages`                  | Uses `deploy-verified.mjs` for verified commits. The workflow then publishes the full tree with Pages Actions and polls with `scripts/ci/verify_deploy.py`.                          |
| `verified-commit` | Create a verified commit or fall back to a PR                            | Uses `verified-commit.mjs`. Modes are `direct`, `force-pr`, and `direct-or-pr` (the default). A conflict creates a dated fallback branch, which is force-reset if it already exists. |

Browser-only jobs run in the pinned Playwright Python container and set `browser-engines: ""`, so they neither restore nor install host browsers. The `publish` job runs on the hosted runner and sets `browser-engines: chromium`, so `ci-setup` installs Chromium for its live browser verification.

## Script dependency map

| Script                                                       | Called by                                                         | Purpose                                                                           |
| ------------------------------------------------------------ | ----------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `scripts/ci/workflow_helpers.py thumbnail-plan`              | plan job                                                          | Compute the browser, thumbnail, and persist scope and the shard matrix            |
| `scripts/ci/app_hashes.py apply-ledger`                      | plan job                                                          | Skip apps whose input hash already passed on `main`                               |
| `scripts/ci/app_hashes.py update-ledger`                     | save-app-ledger job                                               | Record main-verified app input hashes into the ledger cache                       |
| `scripts/ci/app_shards.py write-manifest`                    | app-shard job                                                     | Select one shard's slugs from the plan into a manifest                            |
| `scripts/ci/app_shards.py package-result`                    | app-shard job                                                     | Package a shard manifest and its generated thumbnails                             |
| `scripts/ci/app_shards.py merge-results`                     | assemble-site job                                                 | Merge every shard thumbnail result into the checkout                              |
| `scripts/ci/app_shards.py invalidate-thumbnails`             | app-shard job (`make thumbnails-shard`)                           | Delete stale thumbnails for a shard before regeneration                           |
| `scripts/ci/workflow_helpers.py app-token-policy`            | ci-setup action                                                   | Decide whether app tokens are minted                                              |
| `scripts/ci/workflow_helpers.py validate-thumbnail-artifact` | persist-thumbnails job                                            | Check that the thumbnail artifact matches the plan                                |
| `scripts/ci/workflow_helpers.py audit-repo-settings`         | audit-repo-settings workflow                                      | Compare repository settings with the expected values                              |
| `scripts/ci/workflow_helpers.py lock-refresh-workflow-run`   | commit-python-locks workflow                                      | Validate the triggering Dependabot run and emit its trusted values                |
| `scripts/ci/workflow_helpers.py validate-lock-artifact`      | commit-python-locks workflow                                      | Reject unsafe artifact trees and metadata that does not match the run             |
| `scripts/ci/refresh_ci_pins.py`                              | refresh-playwright workflow                                       | Update the locked Playwright package and matching official CI image digest        |
| `scripts/ci/run_parallel_checks.py`                          | quick-gates and heavy-checks jobs                                 | Run independent Make targets concurrently with CI-friendly output                 |
| `scripts/ci/verify_deploy.py`                                | publish job                                                       | Poll the published URL for the expected HTML marker and deploy metadata SHA       |
| `scripts/gh/cli.py`                                          | local `make pr-*`, `make issue-*`, and `make ci-failures` targets | Provide PR, issue, review-thread, and failed-CI helpers                           |
| `scripts/ci/workflow_helpers.py audit-previews`              | audit-repo-settings workflow                                      | List `pr-preview/pr-N/` directories on `gh-pages` whose PR is no longer open      |
| `scripts/ci/workflow_helpers.py sync-alert-issue`            | alert workflows                                                   | Open, update, or close one alert issue for a monitored failure                    |
| `.github/actions/deploy-site/deploy-verified.mjs`            | deploy-site action, publish and cleanup jobs                      | Deploy to `gh-pages` through a GraphQL verified commit, including preview removal |
| `.github/actions/verified-commit/verified-commit.mjs`        | verified-commit action                                            | Create a verified commit through GraphQL, falling back to a PR on conflict        |

## Artifact flow

`plan` uploads `ci-plan-{run_id}`, which holds `plan.json` with the slug lists. `app-shard` and `assemble-site` download it. Each shard uploads `app-shard-{run_id}-{shard}` with its manifest and thumbnails. `assemble-site` uploads `site-{run_id}` (the `_site/` directory) for `publish`, and `thumbnail-persist-{run_id}` for `persist-thumbnails` when thumbnails changed. `publish` uploads `live-browser-artifacts-{run_id}` only on failure. `refresh-python-locks.yml` uploads `python-lock-refresh-{pr_number}` for `commit-python-locks.yml`.

## Token model

Three GitHub Apps provide permissions beyond the default `GITHUB_TOKEN`. Each serves one role.

| App                    | Variable and secret                                               | Used for                                                                                                   |
| ---------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Hermione1176 (primary) | `vars.APP_ID` and `secrets.APP_PRIVATE_KEY`                       | Same-PR thumbnail writeback                                                                                |
| Harry1176 (escalation) | `vars.ESCALATION_APP_ID` and `secrets.ESCALATION_APP_PRIVATE_KEY` | All `gh-pages` deploys and preview removal, follow-up thumbnail PRs from `main`, scheduled maintenance PRs |
| Percy1176 (audit)      | `vars.AUDIT_APP_ID` and `secrets.AUDIT_APP_PRIVATE_KEY`           | Read-only settings audit and its drift issue                                                               |

Each installation carries only the permissions its role uses. All three also need `metadata: read`, which is implicit.

- Hermione1176: `contents: write`.
- Harry1176: `contents: write`, `pull_requests: write`, and `workflows: write`. The `refresh-action-shas` commit rewrites files under `.github/workflows/`, which GitHub rejects without `workflows: write`.
- Percy1176: `administration: read`, `pages: read`, `actions_variables: read`, `secrets: read` (names only), and `issues: write`.

Harry does not need `pages: write`. The Pages publish runs on the workflow `GITHUB_TOKEN`, which holds `pages: write` and `id-token: write` on the publish jobs. The deployment record uses its `deployments: write` grant. Check the app settings page before you remove any grant, because the audit does not enforce the write-app permission sets.

`ci-setup` takes the primary and escalation credentials together or not at all. The audit credentials are independent.

| Context         | Tokens | Deploy         | Thumbnail persist   |
| --------------- | ------ | -------------- | ------------------- |
| Same-repo PR    | Yes    | Preview deploy | PR branch writeback |
| Push to main    | Yes    | Main deploy    | Follow-up PR        |
| Fork PR         | No     | Skip           | Skip                |
| Dependabot PR   | No     | Skip           | Skip                |
| Manual dispatch | Yes    | Main deploy    | Skip                |

## Thumbnail persistence modes

The `plan` job computes `persist-mode` from the event context.

| Mode          | When                                                                                                 | What happens                          |
| ------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------- |
| `none`        | Fork PR, Dependabot PR, docs-only or metadata-only change, merged thumbnail PR, dispatch or schedule | No source mutation                    |
| `pr-branch`   | Trusted same-repo PR with runtime changes or missing thumbnails                                      | Thumbnails committed to the PR branch |
| `followup-pr` | Push to `main` with runtime changes or missing thumbnails                                            | Follow-up PR opened or updated        |

A merged follow-up thumbnail PR is detected through PR provenance, not the commit message, so squash merges do not break the check. The follow-up PR body carries the marker `<!-- artifacts:generated-thumbnails -->`.

## Verification skip for automated thumbnail commits

When `persist-thumbnails` commits thumbnails to a PR branch with the Hermione1176 token, the resulting `synchronize` event starts a second run. `plan` sets `skip-verification` to `true` only when both conditions hold:

- The workflow actor matches the app bot login, which `plan` resolves from `vars.APP_ID` at runtime.
- Every file in the triggering commit matches `apps/*/thumbnail.webp`.

When it is `true`, the verification jobs, `verify`, and `publish` are skipped. `plan`, `secret-scan`, and `dependency-review` still run on PR events. The same files check applies to main pushes from merged thumbnail follow-up PRs, alongside PR provenance detection. Any detection failure sets `false`, so the full pipeline runs.

## External GitHub settings

These settings live outside source control. Run `make ci-audit-repo-settings` to check them for drift.

- GitHub Pages uses GitHub Actions as its source, with HTTPS enforced.
- `gh-pages` is the CI-managed deploy branch for the live root and the PR preview subtrees.
- `vars.APP_ID`, `vars.ESCALATION_APP_ID`, and `vars.AUDIT_APP_ID` hold the GitHub App Client IDs. The names are kept for compatibility.
- `secrets.APP_PRIVATE_KEY`, `secrets.ESCALATION_APP_PRIVATE_KEY`, and `secrets.AUDIT_APP_PRIVATE_KEY` hold the private keys.
- `secrets.GITLEAKS_LICENSE` is for the Gitleaks action. The action requires a license only for organization accounts, so this has no effect while the repository is user-owned.
- Secret scanning and push protection are enabled. Push protection blocks a push that contains a secret. `secret-scan` covers the history behind it. `.gitleaks.toml` excludes only the built site copies under `pr-preview/` on `gh-pages`.
- The Actions allowlist permits GitHub-owned actions, `astral-sh/setup-uv@*`, `gitleaks/gitleaks-action@*`, and `marocchino/sticky-pull-request-comment@*`. Actions must be pinned to full commit SHAs, and verified-creator actions are not allowed.
- The `github-pages` environment accepts deployments from `gh-pages`, `main`, and `refs/pull/*/merge`.
- `main` branch protection requires the `verify`, `secret-scan`, and `dependency-review` checks, plus review, signing, and history requirements.
- The `gh-pages` ruleset blocks create, delete, update, and force-push, except for the deploy app and repository admins.
