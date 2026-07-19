# ADR 0005: CI scaling architecture and roadmap

- Status: Accepted
- Date: 2026-07-19

## Context

The gallery should scale to thousands of artifacts. Before this work, any shared-file change verified every artifact serially in one runner, the app browser tests rebuilt the full site once per app (quadratic filesystem work), and changed-file detection used a REST endpoint capped at 3000 files. Measured on the pre-change pipeline, a shared change at even a few hundred artifacts would have pushed CI past an hour; at thousands it becomes unusable.

Owner constraint that shapes everything here: every artifact must be fully verified before merge. Optimizations may reduce redundant work, but never verification coverage.

## Decision

The pipeline (PRs #120 and #121) is structured as: plan, then parallel verification (quick gates, heavy checks, root browser, dynamic app shards), then single-pass site assembly, then an aggregation-only `verify` job that branch protection requires, then publish.

1. **Independent impact axes.** The plan classifies changed files (exact `git diff base...head`, three-dot semantics) into separate browser, thumbnail, static-checks, and deploy scopes. Any planning failure falls back to the full fail-closed plan.
2. **Bounded dynamic shards.** Affected apps pack deterministically into shards of at most 20 apps, at most 128 shards (GitHub matrix cap is 256), `max-parallel` 12. Each shard builds the test site once and runs browser tests plus thumbnail capture together to amortize setup.
3. **Reverse dependency graph.** Static parsing of app script tags and ESM imports maps each shared `js/modules/*` file to its consumer apps, so a module change verifies only consumers. Global files (`css/style.css`, `js/app-theme.js`, `js/modules/app-shell.js`) and any module with zero parsed consumers fan out to all apps (fail open).
4. **Verification memoization, not skipping.** Each app gets an input hash over its own tracked files, shared runtime, shared browser-test harness, and lockfiles (git blob hashes). A ledger of main-verified green hashes is restored via the Actions cache; apps whose hash matches are dropped from browser shards because byte-identical inputs already passed on main. The ledger is written only by the main-branch job that runs after `verify` succeeds; every read path is fail-open to full verification.
5. **Fail-fast ordering.** Cheap gates (format, lint, typecheck, validate) gate the browser jobs; heavy checks (Python tests, JS coverage, dead code, security) run alongside them. No check runs twice.
6. **Deploy build scaling.** `_site` receives only runtime files per app (`index.html`, `css/`, `js/`, `assets/`, thumbnail), minification runs in a bounded worker pool, and cache busting uses per-file content hashes so unrelated commits stop rewriting every page and identical trees produce byte-identical sites.
7. **Environment caching.** Jobs cache pip/uv/npm downloads, the Playwright browser directory, and (this ADR's batch) `.venv` and `node_modules` directly, keyed exactly on lockfile hashes with no restore-keys, so a hit skips dependency installation entirely and a miss installs from scratch. The `.venv` key includes the resolved interpreter version and runner architecture (not the bare version input) so runner image updates roll the cache instead of restoring a venv built against a missing toolcache path. The uv binary is installed unconditionally because make targets such as `audit-python` invoke uv directly; only the dependency install is skippable. On a Playwright cache hit the setup skips the apt system-deps pass (`make setup-playwright` instead of `make setup-playwright-ci`); browser tests fail loudly if system libraries were ever missing.
8. **Flake control.** Failed browser tests rerun once (`--last-failed`), a pass on retry emits a labeled flaky warning and job-summary entry, and two consecutive failures stay red.
9. **Weekly full sweep.** A cron trigger and a `full-sweep` dispatch input force the fail-closed full plan through the same job graph as a backstop. The redeploy is a no-op when the tree is unchanged because the deploy script skips empty commits.
10. **Concurrency cancellation.** A `concurrency` group keyed on the workflow and the PR number (falling back to the ref) cancels superseded in-progress runs, with `cancel-in-progress` enabled only for `pull_request` events. A new push to a PR frees runners from the prior run immediately. Non-PR runs (pushes to `main`, scheduled sweeps, and dispatches) never cancel, so main-branch publishes always run to completion.

## Rejected alternatives

- **Post-merge or nightly-only verification tiers, and pre-merge canary sampling.** Rejected by the owner: everything is verified before merge. Do not reintroduce these.
- **Delta PR previews.** Deploy machinery risk outweighs the benefit while full-site preview copies remain cheap.
- **Merge queue.** Useful at high PR concurrency, but it is a repository settings change, not code; revisit when semantically conflicting PRs actually collide.

## Roadmap (ranked, all pre-merge safe)

1. **Consumer-scoped memoization hashes.** App hashes currently include all shared modules, so any module change invalidates every app's ledger entry even when only one app consumes it. Feed the reverse dependency graph into the hash inputs to raise hit rates once shared modules stabilize.
2. **Thumbnail memoization.** The ledger only skips browser tests today; thumbnails still regenerate for every scoped app. Extending the ledger to thumbnails (hash must add the generator script and browser version) would roughly halve shard cost on repeat inputs.
3. **Raise `max-parallel`.** Currently 12; the planner emits up to 128 shards of at most 20 apps each, so more concurrency and larger runners raise throughput further. Pure wall-time lever once the artifact count grows.
4. **Merge queue** (see rejected alternatives; becomes attractive with many concurrent PRs).

## Notes for future maintainers (research already done)

- `actions/cache` authenticates with the runner-provided `ACTIONS_RUNTIME_TOKEN`; the job `permissions:` block does not gate it, so `actions: read`/`write` are not needed for cache restore or save.
- Typed `workflow_dispatch` boolean inputs arrive as booleans in the `inputs` context, but the plan expression also tolerates the string form for REST-dispatched runs.
- Expressions like `inputs.x` render as an empty string on events without inputs; always compare against a literal so booleans render as booleans.
- The exact-key-only environment caches are deliberate: a partial restore would not justify skipping installation, so restore-keys would only add risk without saving time.
- A job whose `if` has no status-check function gets an implicit `success()`, and that evaluates false when any job in the transitive needs chain was skipped, not just direct needs (actions/runner issue 2205). Any job downstream of a conditionally skipped job (for example `dependency-review`, which only runs on pull requests) must start its condition with `!cancelled() &&` and check the needed results explicitly, or it silently never runs.
- Caches populated by an earlier job in the same run are visible to later jobs: `quick-gates` saves the `.venv` cache at job end, so `heavy-checks` restores it as a hit on the very first run of a branch. Skip logic must therefore never assume a cache hit implies a prior full setup ran in this job.
- `tests/ci/test_workflow_contracts.py` pins the job graph, step names, and key strings; every workflow change must update it in the same commit.
- Local gates before pushing CI changes: `make ci-fast`, `make format-check`, and both browser suites (`make test-browser-root` and `make test-browser-apps`); the root suite exercises the built site and catches deploy-build regressions the app suite misses.
