# Troubleshooting and recovery

Find the symptom, then follow the steps. Day-to-day commands live in [operations](operations.md).

## Local setup and browsers

### Build output is too quiet

The default log level, `INFO`, omits the debug output that the build scripts write.

Set `LOG_LEVEL` on the make command, for example `LOG_LEVEL=DEBUG make index`. The accepted values are `DEBUG`, `INFO` (the default), `WARNING`, and `ERROR`. These scripts read it: `scripts/build/generate_index.py`, `scripts/build/generate_thumbnails.py`, `scripts/build/prepare_site.py`, and `scripts/ci/verify_deploy.py`.

### Browser targets fail before any test runs

The Playwright Python package or Chromium is not installed.

Run `make setup-all`. Without the package, the browser suites fail during collection, and `make thumbnails` exits at once. Without Chromium, `make check-web`, `make test-browser`, and `make test-browser-live` fail.

### Browsers install but will not launch

The host lacks the shared libraries that the browsers need.

Run `make setup-playwright-local`, then confirm it with `make playwright-local-gate`. Rerun the browser target with `local_libs=1`, for example `make test-browser local_libs=1`. To see which engines the cache covers, run `make playwright-local-status`. [Browser setup without sudo](operations.md#browser-setup-without-sudo) explains the runtime.

## CI runs, caches, and settings

### Every workflow reports startup_failure

When every workflow on a commit reports `startup_failure` at once, a GitHub incident is the likely cause. No job starts, so no logs exist.

Run `make lint-workflows` to confirm that the workflow files are valid. After the incident clears, replay each affected run with `make ci-rerun run=<id>`. Add `failed=1` to retry only the failed jobs of a partly green run.

### Cache restores look like a fresh install

A cache hit prints download lines that read like a full install.

A hit logs `Cache hit for: <key>` followed by `Cache restored from key: <key>`. The post step logs `Cache hit occurred on the primary key`, which confirms the hit. A miss logs `Cache not found for input keys`. A real install appears separately as `make install` or `npm ci` output. Run `make ci-caches` to see what is stored and how large it is.

### Retired cache keys still use the cache budget

Old cache entries stay after a key rolls and keep counting against the repository's cache budget.

List them with `make ci-caches key=<prefix>`, then delete each one with `make ci-cache-delete cache=<id|key>`. Pass the id when you can. A key can match one entry per ref, and a bare key resolves against the current branch only. To reach another branch, add `ref=refs/heads/<branch>`. Delete entries only after the change that retires the key is on `main`, because a run on the old code recreates the entry.

### Repository settings differ from the documented settings

A repository setting, variable, secret, or ruleset does not match [External GitHub settings](ci.md#external-github-settings).

Run `make ci-audit-repo-settings`. Add `repo=<owner/repo>` to audit another repository.

## Deploys and Pages

### Redeploy fails with "Multiple artifacts named github-pages"

A retry reuses its run's artifact namespace, so the deploy step finds two `github-pages` artifacts and stops.

Start a fresh run rather than retrying. For a main redeploy, run `make ci-dispatch workflow=update.yml ref=main`. For an older commit, add `inputs="redeploy-sha=<sha>"`.

### PR preview does not update after a dispatch

`workflow_dispatch` runs the main-site publish path, not the PR-preview path.

Push the follow-up commit to the PR branch. That creates a clean `pull_request` run. Do not dispatch `update.yml` on the PR branch.

### Deploy times out with `updating_pages`

`actions/deploy-pages` stops waiting while Pages still has a backlog, and the payload can publish after the action gives up.

Check `deploy-metadata.json` on the live site before you assume nothing shipped. If its `commit_sha` matches the commit whose run failed, that commit reached the live site.

### Post-deploy verifier flakes

The post-deploy verifier checks the live site right after publish.

Inspect the published `?v=<sha>` asset query strings and the live `deploy-metadata.json` before you rerun the job.

### Live browser verification fails in CI

The browser check on the published site failed in the `publish` job.

Download the `live-browser-artifacts-<run_id>` artifact for screenshots, traces, and runtime error logs.

### Daily live-site smoke check fails

The scheduled `live-site-smoke.yml` run found a failure on the published site.

Inspect the `live-site-smoke-artifacts-<run_id>` artifact and the GitHub issue that the workflow manages. Then rerun with `make ci-rerun run=<id>`.

## Security and audits

### Secret scan fails on a manual or scheduled run

Runs with no commit range, such as `workflow_dispatch` and `schedule`, make `secret-scan` walk every branch, including `gh-pages`.

Check the paths that the finding names. `.gitleaks.toml` excludes `pr-preview/` and nothing else. A finding outside that prefix is either a reviewed false positive or a real secret. Add a reviewed fingerprint to `.gitleaksignore`. Rotate a real secret. Never widen the path allowlist in `.gitleaks.toml`.

### npm audit fails

A new advisory affects the dependency graph, or a reviewed npm exception has expired or matches no active advisory.

Triage the advisory. To move a vulnerable package to a fixed version, run `make lock-node-update packages="package-a"`. Update or remove any expired or unused exception in `config/security_audit.json`.

### Python audit fails

`pip-audit` reports a vulnerability, or a Python exception in `config/security_audit.json` has expired, matches nothing in the lock files, or stops applying because a fix exists and the exception sets `ignore_only_without_fix: true`.

Upgrade the package with `make lock-update packages="package-a"` when a fix exists. Otherwise, record a reviewed exception or renew the expired one in `config/security_audit.json`. [Dependency audits](checks.md#dependency-audits) describes exception matching and defaults.

### Vendored audit reports an unreviewed vulnerability

OSV lists an advisory for a bundled version of a vendored library, and the message reads `Unreviewed vendored vulnerability`.

Upgrade the bundle to a fixed version, following [Vendored dependency update](#vendored-dependency-update), and update its entry in `config/vendored_assets.json`. Or add a reviewed exception under `vendored_vulnerability_exceptions`, with a `reason` and a `review_by` date.

### Vendored audit cannot query OSV or read its data

The audit could not reach `api.osv.dev` after three attempts, or the OSV response or the manifest is malformed.

For `could not query OSV`, rerun the job. For `could not use the OSV response` or `could not read config/vendored_assets.json`, fix the manifest or the record that the message names. No exception silences the last two messages.

## Dependencies and generated files

### Lock file does not match a dependency change

The lock file stays stale until you regenerate it: `uv.lock` for `pyproject.toml`, and `package-lock.json` for `package.json`.

Run `make lock` before you commit a Python dependency change, and `make lock-node` before you commit a Node dependency change. To move only some packages, run `make lock-update packages="package-a package-b"` or `make lock-node-update packages="package-a package-b"`. Both avoid refreshing the whole lock file.

### README markers are missing or duplicated

`scripts/build/generate_index.py` fails instead of writing a corrupted `README.md` when an `AUTO:` marker is missing or duplicated.

Restore each missing marker in `README.md`, remove duplicates, and run `make index`.

### `js/data.js` is empty

No artifact folders exist, so `make index` writes an empty `js/data.js`. This is valid output.

Add an artifact with `make new name=my-artifact`, then run `make index`.

## Rollback and recovery

### Bad main deploy

1. Identify the last known-good commit on `main`.
2. Run the `Update Artifacts & Deploy` workflow with `workflow_dispatch` and set the `redeploy-sha` input to that commit SHA. For example, run `make ci-dispatch workflow=update.yml ref=main inputs="redeploy-sha=<sha>"`. The workflow sets `BUILD_REF`, so every build, verify, and deploy job checks out that commit. The pipeline rebuilds `_site/` from it and republishes from a verified artifact. An empty `redeploy-sha` builds the current commit. The `plan` job rejects a SHA that is not a real commit before any other work starts.
3. Confirm that the published site serves a `deploy-metadata.json` with the redeployed commit's SHA and cache-busted asset query strings.
4. If the site is healthy but the Deployments page or the `github-pages` environment badge looks stale, check the `Create main deployment record` and `Mark main deployment successful` steps in the latest `publish` run. Those steps write the deployment record for main-site publishes. A failure there, not in the deploy itself, usually leaves the badge stale.

### Broken PR preview

1. Check that the PR is trusted (same repository, not Dependabot). Other PRs get no preview.
2. Check that `APP_ID`, `APP_PRIVATE_KEY`, `ESCALATION_APP_ID`, `ESCALATION_APP_PRIVATE_KEY`, `AUDIT_APP_ID`, and `AUDIT_APP_PRIVATE_KEY` exist and that the GitHub Apps are still installed on the repository.
3. Read the `publish` job summary. If live-browser verification failed after the deploy, download the `live-browser-artifacts-<run_id>` artifact.

### Token rotation or GitHub App outage

1. Rotate the key in the affected GitHub App. The procedure is the same for Hermione1176, Harry1176, and Percy1176.
2. Update the matching repository secret right after the rotation.
3. Run `make ci-audit-repo-settings repo=<owner/repo>` to confirm the repository still matches the documented settings.
4. Rerun a trusted preview deploy before the next `main` publish depends on the new key.

### Credential recovery (lost key or uninstalled app)

Use this when a private key is lost with no backup, or when a GitHub App was deleted or uninstalled from the repository. Token rotation covers an app that still exists. The minimal permissions for each app are in [Token model](ci.md#token-model).

What breaks, per app:

- **Hermione1176 (primary).** Same-PR thumbnail writeback stops. Primary and escalation credentials are all-or-nothing in trusted contexts, so `ci-setup` hard-fails every trusted `publish` and `persist-thumbnails` run while either app is missing. Preview and main deploys stop too until both apps are healthy.
- **Harry1176 (escalation).** All deploys stop: the main site, PR previews, and preview cleanup. The follow-up thumbnail PR from `main` stops too, along with the scheduled `refresh-locks`, `refresh-action-shas`, and `refresh-playwright` maintenance PRs. As with Hermione1176, `ci-setup` hard-fails trusted runs while either the primary or the escalation credential is absent.
- **Percy1176 (audit).** Only the weekly repository-settings audit stops. Deploys and previews are unaffected. A missing install surfaces as an HTTP 403 from `scripts/lib/gh_api.py` during the audit.

To re-mint an app, follow these steps.

1. Create a new GitHub App, or reuse the existing one when only the key was lost, and generate a fresh private key.
2. Grant exactly the permissions that [Token model](ci.md#token-model) lists for that app. Hermione needs `contents: write`. Harry needs `contents: write`, `pull_requests: write`, and `workflows: write`. Percy needs the read-only audit set plus `issues: write`.
3. Install the app on this repository.
4. Set the repository variable to the new app client ID: `APP_ID` for Hermione, `ESCALATION_APP_ID` for Harry, or `AUDIT_APP_ID` for Percy. The variable names do not change.
5. Update the matching repository secret with the new private key: `APP_PRIVATE_KEY`, `ESCALATION_APP_PRIVATE_KEY`, or `AUDIT_APP_PRIVATE_KEY`.

Verify the recovery with these checks.

- Hermione or Harry: run `make ci-audit-repo-settings repo=<owner/repo>` to confirm that the variables and secrets exist. Then run `make ci-dispatch workflow=update.yml ref=main`. A green run means the `publish` job minted both tokens, wrote the `gh-pages` deploy, and passed live browser verification. A trusted preview deploy on an open PR checks the preview path the same way.
- Percy: run `make ci-dispatch workflow=audit-repo-settings.yml`. A green run, with no new drift issue or with the existing one closed, means the audit token was minted and could read Pages, branch protection, variables, secrets, and the ruleset.

### `gh-pages` branch or Pages root drift

1. Confirm that the GitHub Pages source is GitHub Actions.
2. Confirm that the `gh-pages` ruleset targets `refs/heads/gh-pages` and blocks create, delete, update, and force-push, except for approved bypass actors.
3. If the branch contents are wrong, redeploy a known-good `main` commit. Do not repair `gh-pages` by hand, so the verified artifact stays the source of truth.
4. If a Pages deployment fails before verification starts, read the `Deploy GitHub Pages artifact` step in `update.yml`.

### First deploy or `gh-pages` branch recreation

Use this on a new fork that has never deployed, or after someone deleted `gh-pages`.

1. The deploy action creates `gh-pages` when it is missing. It seeds the branch with an initial commit that contains `.nojekyll`, then writes the site tree. Do not push an empty branch yourself. The seed commit is unsigned, so install the ruleset that requires signatures after the seed commit exists.
2. Recreate the `gh-pages` ruleset by hand. Automation cannot create it. Target `refs/heads/gh-pages` with the rules in [External GitHub settings](ci.md#external-github-settings): block create, delete, update, and force-push, and require linear history and signatures. Add the Harry1176 deploy app and the repository admins as bypass actors, so deploys can still write the branch. Install the ruleset after step 1 so it does not block the first branch creation.
3. Confirm that the Pages build type is GitHub Actions (`workflow`, not a legacy branch build) and that HTTPS is enforced. The official Pages actions then publish the deploy tree.
4. Run a `main` deploy with `make ci-dispatch workflow=update.yml ref=main`. Confirm that the live URL serves the expected `deploy-metadata.json` SHA and cache-busted asset query strings. Then run `make ci-dispatch workflow=live-site-smoke.yml ref=main`, or wait for the daily run, to confirm that the published site passes in a real browser.

### Generated-file drift in CI

CI fails when a generated file differs from what its source inputs produce.

1. Read the generated diff to decide whether the source change or the generator is wrong.
2. Fix the source or the generator, then rerun `make check-generated`.

### Vendored dependency update

1. Download the new UMD build from jsDelivr into the recorded `path` of each affected entry in `config/vendored_assets.json`. Several apps can vendor one package. `loan-amortization` and `bond-price-vs-rate` both vendor Chart.js. Update every entry that names the package you are bumping.
2. Update the `version`, `upstream`, and `sha256` fields of each affected entry so that `make lint-vendored-assets` passes. The `upstream` URL must contain `<package>@<version>`.
3. Run `make audit-vendored`. It fails when OSV lists an advisory for the new version.
4. When a PDF library changed, recheck the hand-written declarations in `config/types/pdf-vendor.d.ts`. Update the version numbers in each affected app's docs, for example `apps/loan-amortization/docs/decisions.md`.
5. Run `make test-browser` before you publish.

### Security gate failure

1. Treat a dependency audit or secret scan failure as a release blocker.
2. Decide whether it is a real leak or vulnerability, an expired exception, or a stale lock or dependency-review mismatch.
3. Resume deploys only after you fix the finding or record a reviewed exception.

See [`maintenance.md`](maintenance.md) for the long-term upkeep checklist.
