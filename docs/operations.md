# Operations

## Day-to-day local workflow

Use Make targets for workspace commands. Start with these:

```bash
make help          # list command groups
make help-ci       # list the commands in one group, here CI and GitHub runs
make setup         # install Python and Node dependencies without Chromium
make setup-all     # also install Chromium for browser tests and thumbnails
make install-hooks # install local pre-commit hooks
make pr            # list the PR commands
make issue         # list the issue commands
make git           # list the Git commands
make ci            # run the full non-browser local gate
```

`make issue-list` accepts `state=`, `label=`, `assignee=`, `author=`, `limit=`, and `mine=1`. Set `SEARCH='...'` for a free-text search.

`make issue-summary issue=N` prints state, labels, assignees, milestone, and recent comments. `make issue-develop issue=N` creates a branch linked to the issue.

Supply issue bodies on stdin. `make issue-edit` takes a new title through `TITLE='...'`. Set `COMMENT='...'` for a short close or reopen comment.

The `make pr-*` and `make issue-*` targets try GraphQL first. If the environment refuses GraphQL, as Claude Code cloud sessions do, the targets use the REST API for the rest of the run. [ADR 0008](adr/0008-graphql-first-rest-fallback.md) explains the design. REST mode differs in these ways:

- Review threads have no node id. `make pr-review-comments` prints each thread as `thread=<id>`, where the id is the number of the thread's first comment. Pass that number to `make pr-reply`, `make pr-resolve`, or `make pr-address`. Add `pr_num=N` when the PR is not on the current branch.
- `make pr-comments-list` prints numeric comment ids. Pass one to `make pr-comment-delete comment_id=<id>`.
- A `PRRT_` or `PRRC_` node id needs GraphQL. The target fails and names the numeric id to use.
- List, view, and checks output is tab-separated and close to `gh` output, but not identical.
- `make pr-create` does not push. Run `make push` first, or the target stops when the branch on GitHub is missing or behind your local `HEAD`.
- `make pr-merge` and `make pr-close` delete the remote branch but leave your local checkout alone.
- `make pr-merge` refuses a PR that GitHub does not report as mergeable. The REST merge has no admin switch, so merging anyway would bypass branch protection for an administrator. Run `make pr-merge-admin` to merge past protection on purpose.
- `make issue-develop` creates and checks out the branch but cannot link it to the issue.
- The targets choose the repository from `GH_REPO` first, then from the default that `gh repo set-default` stored, then from `origin`. If gh stored a default these targets cannot read, they stop instead of using `origin`.
- When the selected repository differs from `origin`, such as upstream from a fork, the targets read and write the selected repository but push and fetch branches through `origin`. `make pr-create` opens the PR from the fork branch. `make pr-checkout` and `make issue-develop` refuse, because their fetches would come from the wrong repository. They also refuse when `origin` is not a GitHub repository.
- `make issue-list` with `SEARCH` needs the `search/issues` endpoint, which cloud sessions block. The other filters work.

`make pr-watch` observes the Copilot review that starts automatically when a pull request is created and waits for the checks to settle. It does not request a second review. After you push a correction that needs a fresh review, run `make pr-watch request=1`. To watch only CI, run `make pr-watch checks_only=1`. `make pr-copilot-review` requests a review on its own.

Python dependency setup uses uv. Put `uv` on PATH before you run the setup, install, lock, or security targets. Leave `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE` unset. The pinned Playwright detects current hosts natively, and a forced platform key can leave the browser revision cache holding a build from the wrong platform archive. On a Debian or Ubuntu host that lacks the shared libraries the browsers need, use the no-sudo runtime in [Browser setup without sudo](#browser-setup-without-sudo).

`scripts/gh/commit_message.py` checks the message before `make commit` records it. It rejects heredoc fragments, shell redirections, and pager pipes that were pasted into the message by mistake. Fix the flagged line and rerun the target.

To change workspace code:

1. To add an artifact, run `make new name=my-artifact`, or `make new name=my-artifact src=path/to/page.html` to install an existing HTML file. Both create the metadata, stylesheet, app shell, docs, and a `tests/js/apps/<slug>/app.test.js` stub. The placeholder passes the gates without edits. A `src=` import keeps off-origin references, so vendor or remove each reported reference before the CSP check can pass.
2. Run `make setup`, or `make setup-all` when you also need Chromium. Run `make install-hooks` once to enable the local pre-commit checks.
3. Edit files.
4. Run `make check-local`.
5. Run `make check-web` when you change shared browser behavior or need fresh thumbnails. To test one mature app, run `ARTIFACTS_BROWSER_APP_SLUGS="app-slug" make test-browser-apps`. For the cross-engine smoke pass, run `make setup-playwright-webkit` once, then `make test-browser-webkit-smoke`. On a host that lacks the browsers' shared libraries, follow [Browser setup without sudo](#browser-setup-without-sudo) and append `local_libs=1` to these targets.
6. Run `make check` before you open a PR to run the full local release gate.
7. Run `make validate` after you change the directories under `apps/` for an explicit structure check.
8. Run `make index` when metadata or README markers may have changed.
9. Run `make site` to inspect the Pages output locally, or `make serve` to build it and serve it on `http://localhost:8000/`.
10. Run `make lock` after you change Python dependency declarations and `make lock-node` after you change Node dependencies.

## Browser setup without sudo

`make setup-all` installs Chromium into Playwright's user-level browser cache. It installs no system packages and needs no sudo. Use it when the host already has the shared libraries the browsers need.

On a Debian or Ubuntu host that lacks those libraries, use the repository-local runtime instead:

```bash
make setup-playwright-local        # Chromium plus its extracted library closure
make setup-playwright-webkit-local # add WebKit for the cross-engine smoke pass
make playwright-local-status       # report what the cache currently covers
make playwright-local-gate         # launch every prepared engine for real
make playwright-local-clean        # remove only this repository's cache
```

Setup downloads package archives from the APT repositories the host already uses and extracts them into this repository's ignored `.playwright/local-libs/` cache. It resolves the package closure with an APT simulation, downloads with `apt download`, and extracts with `dpkg-deb -x`. It never installs packages, runs sudo or `dpkg -i`, or changes the system package database. Browsers install into Playwright's shared `~/.cache/ms-playwright` cache, so every project on the machine reuses one copy.

Separate targets install Chromium and WebKit, and both record into one manifest. Each target requests only its own engine, and the runtime records the union of that request and the engines already prepared. The extracted libraries therefore cover every prepared engine, and installing WebKit later does not strand Chromium's libraries. The runtime rebuilds the manifest when the operating system, architecture, Playwright version, engine set, or resolved package versions change.

Browser targets opt in with `local_libs=1`:

```bash
make test-browser local_libs=1
make test-browser-webkit-smoke local_libs=1
make thumbnails local_libs=1
make visual-baselines local_libs=1
make check-web local_libs=1
```

With `local_libs=1`, the wrapper requires a prepared cache and points `PLAYWRIGHT_BROWSERS_PATH` at the shared browser cache. It keeps the browser's home, cache, configuration, runtime, and temporary files under `.playwright/runtime/` and prepends only the extracted library and browser-data paths to the child environment. Preparing the runtime also patches the shared WebKit launcher so it appends an inherited library path after its own bundle directories. The wrapper never downloads packages during a test run. Runs without `local_libs=1` are unchanged.

`make playwright-local-clean` and `make clean` remove only this repository's `.playwright/` cache. Neither touches the shared browser cache, because other projects use it. Manage shared browsers with Playwright's own tooling.

Use the `--with-deps` setup targets (`make setup-ci`, `make setup-playwright-ci`, `make setup-playwright-webkit-ci`, and `make setup-playwright-engines with_deps=1`) only on CI and other disposable runners, because they can install operating-system packages. Browser-only CI jobs run in the pinned official Playwright Python container and set `browser-engines: ""`, so they neither restore nor install host browsers. The `publish` job stays on the hosted runner because it combines Pages deployment, GitHub CLI calls, and live browser verification. It sets `browser-engines: chromium`, so the `ci-setup` action provisions a host Chromium for it.

## Inspect CI failures

Run `make ci-runs` to find a run, then `make ci-failures run=ID` to read the output of its failed steps. To follow an active run, run `make ci-watch run=ID`.

CI calls the same Make targets as local development. [Architecture](architecture.md#main-pipeline-updateyml) describes job dependencies, shard selection, and build and publish behavior.

## Choose checks

Run `make check-local` for the non-browser gate. When browser behavior or thumbnails changed, also run `make check-web`. `make check` runs both gates plus `make index` and `make site`.

[Quality checks](checks.md) describes each target's behavior, scope, and configuration owner.

## Thumbnail policy

- `thumbnail.webp` in each artifact folder is the generated thumbnail.
- `make thumbnails` skips an artifact whose thumbnail is newer than every file under its `index.html`, `js/`, `css/`, and `assets/` and, for apps on the shared runtime, newer than `css/style.css`, `js/app-theme.js`, and the shared modules. Pass `slug=a,b` to limit the run.
- In CI, the `plan` job lists the apps to regenerate in its `thumbnail_slugs`. A change to an app's own `index.html`, `js/`, `css/`, or `assets/` selects that app. A change to `css/style.css`, `js/app-theme.js`, or `js/modules/app-shell.js` selects every app. A change to another shared module under `js/modules/` selects the apps that import it. Apps with no thumbnail are always selected. Each shard runs `make thumbnails-shard`, which deletes the selected thumbnails with `scripts/ci/app_shards.py invalidate-thumbnails` and then regenerates them.
- Edits that touch only an app's `docs/`, `README.md`, or metadata files do not trigger mature-app browser suites or thumbnail generation. The browser scope uses the same classification.
- CI sets `ARTIFACTS_STRICT_THUMBNAILS=1`, so a failed thumbnail attempt fails the workflow instead of logging a warning.
- Local working copies work without checked-in thumbnails.
- Thumbnail discovery rejects a symlinked artifact root or descendant before it starts the local server or Playwright, so an artifact cannot make the renderer follow files outside its own tree.
- Trusted CI runs can save the regenerated `thumbnail.webp` files back to the same PR branch, or open or update a follow-up PR for `main` pushes. [Architecture](architecture.md#thumbnail-persistence-modes) describes the modes.

## Visual regression baselines

- `make test-visual` compares a hero screenshot of the root gallery and of each mature app, taken at a 1200x800 viewport, with the committed baselines in `tests/browser/baselines/`. The comparison in `scripts/ci/visual_regression.py` (Pillow) is tolerant. A pixel counts as changed only when a channel differs by more than 32 of 255. An image fails when more than 5% of its pixels change, or 18% for the root gallery, whose animated 3D book scene stays a few percent noisy after animations are frozen.
- Screenshot rendering depends on the host's fonts, so this check is local and on demand. It is not part of the blocking CI browser gate. Regenerate the baselines in the environment where you run the check.
- After an intentional visual change, run `make visual-baselines` and review the PNG diff before you commit.
- Both targets need Chromium. Run `make setup-all` or `make setup-playwright`, or `make setup-playwright-local` and `local_libs=1` on a host that lacks the browsers' shared libraries.

## Required GitHub settings

[External GitHub settings](architecture.md#external-github-settings) lists every required repository setting (Pages, branch protection, app tokens, secrets, rulesets). Run `make ci-audit-repo-settings` to check for drift by hand.

## Vendored runtime dependencies

- No page loads a script, font, or stylesheet from an external CDN. Third-party scripts are vendored in the app.
- Three apps vendor libraries. `config/vendored_assets.json` is the inventory and the only place that records versions:
  - `apps/loan-amortization/js/vendor/`: Chart.js, `chartjs-plugin-annotation`, `chartjs-plugin-datalabels`
  - `apps/bond-price-vs-rate/js/vendor/`: Chart.js
  - `apps/vendor-docs-generator/js/vendor/`: jsPDF, `jspdf-autotable`, html2canvas, JSZip
- Versions are pinned and upgraded by hand. [Vendored dependency update](#vendored-dependency-update) lists the steps.
- `make lint-vendored-assets` checks each file against the manifest, and `make audit-vendored` checks each package version against published advisories. See [Formatting and lint](checks.md#formatting-and-lint) and [Dependency audits](checks.md#dependency-audits).
- ESLint skips vendored directories (`**/vendor/**` in `config/eslint.config.js`), and the lint walkers skip them (`vendor` in `SKIP_DIRECTORIES` in `scripts/lint/__init__.py`).
- `apps/loan-amortization/docs/decisions.md` records the rationale.

### Self-hosted fonts

- Gallery display fonts (Caveat, Fredoka One) are self-hosted as WOFF2 Latin subsets in `assets/fonts/`.
- `@font-face` declarations live in `css/src/01-tokens.css` and are bundled into `css/style.css`.
- Only the root gallery renders these display fonts. Artifact pages set `body.artifact-app`, which overrides `--font-body` and `--font-heading` with system fonts, so app pages never fetch the WOFF2 files. The two `<link rel="preload" as="font" ... crossorigin>` hints therefore live only in the root `index.html`. Do not add them to app pages.
- To add a font, download the WOFF2 subset into `assets/fonts/`, add the `@font-face` rule to `css/src/01-tokens.css`, run `make styles`, and check that the CSP `font-src 'self'` directive still covers it. Add a `preload` hint to `index.html` only when the root gallery renders the font.

### Adding external assets to a new artifact

Self-host every runtime asset. Do not load scripts, fonts, or stylesheets from an external CDN. For a third-party JS library, download the UMD build into the app's `js/vendor/` directory and add it to `config/vendored_assets.json`. `make lint-artifact-csp` rejects external references, and the browser tests record failed external requests.

## Rollback and recovery

### Bad main deploy

1. Identify the last known-good commit on `main`.
2. Run the `Update Artifacts & Deploy` workflow with `workflow_dispatch` and set the `redeploy-sha` input to that commit SHA. For example, run `make ci-dispatch workflow=update.yml ref=main inputs="redeploy-sha=<sha>"`. The `BUILD_REF` environment value makes every build, verify, and deploy job check out that commit instead of the branch tip, so the pipeline rebuilds the known-good `_site/` and republishes it from a verified artifact. An empty `redeploy-sha` builds the current commit. The `plan` job checks that the SHA is a real commit before any other work starts.
3. Confirm that the published site serves a `deploy-metadata.json` with the redeployed commit's SHA and cache-busted asset query strings.
4. If the site is healthy but the Deployments page or the `github-pages` environment badge looks stale, check the `Create main deployment record` and `Mark main deployment successful` steps in the latest `publish` run. They write the classic deployment record for main-site publishes, so a failure there, not in the deploy, usually freezes the badge.

### Broken PR preview

1. Check that the PR is trusted (same repository, not Dependabot). Other PRs get no preview.
2. Check that `APP_ID`, `APP_PRIVATE_KEY`, `ESCALATION_APP_ID`, `ESCALATION_APP_PRIVATE_KEY`, `AUDIT_APP_ID`, and `AUDIT_APP_PRIVATE_KEY` exist and that the GitHub Apps are still installed on the repository.
3. Read the `publish` job summary. If live-browser verification failed after the deploy, download the `live-browser-artifacts-<run_id>` artifact.

### Token rotation or GitHub App outage

1. Rotate the key in the affected GitHub App. The procedure is the same for Hermione1176, Harry1176, and Percy1176.
2. Update the matching repository secret right after the rotation.
3. Run `make ci-audit-repo-settings repo=<owner/repo>` to confirm the repository still matches the documented settings.
4. Re-run a trusted preview deploy before the next `main` publish depends on the new key.

### Credential recovery (lost key or uninstalled app)

Use this when a private key is lost with no backup, or when a GitHub App was deleted or uninstalled from the repository. Token rotation covers an app that still exists. The minimal permissions for each app are in [Token model](architecture.md#token-model).

What breaks per app:

- **Hermione1176 (primary):** same-PR thumbnail writeback stops. Because primary and escalation credentials are all-or-nothing in trusted contexts, `ci-setup` hard-fails every trusted `publish` and `persist-thumbnails` run while either app is missing, so preview and main deploys stop too until both apps are healthy.
- **Harry1176 (escalation):** all deploys stop (main site, PR previews, and preview cleanup), along with the follow-up thumbnail PR from `main` and the scheduled `refresh-locks`, `refresh-action-shas`, and `refresh-playwright` maintenance PRs. As with Hermione, `ci-setup` hard-fails trusted runs while either primary or escalation credential is absent.
- **Percy1176 (audit):** only the weekly repository-settings audit stops. Deploys and previews are unaffected. A missing install surfaces as an HTTP 403 from `scripts/lib/gh_api.py` during the audit.

Re-mint an app:

1. Create a new GitHub App, or reuse the existing one when only the key was lost, and generate a fresh private key.
2. Grant exactly the permissions that [Token model](architecture.md#token-model) lists for that app. Hermione needs `contents: write`. Harry needs `contents: write`, `pull_requests: write`, and `workflows: write`. Percy needs the read-only audit set plus `issues: write`.
3. Install the app on this repository.
4. Set the repository variable to the new app client ID: `APP_ID` for Hermione, `ESCALATION_APP_ID` for Harry, `AUDIT_APP_ID` for Percy. The variable names do not change.
5. Update the matching repository secret with the new private key: `APP_PRIVATE_KEY`, `ESCALATION_APP_PRIVATE_KEY`, or `AUDIT_APP_PRIVATE_KEY`.

Verify recovery:

- Hermione or Harry: run `make ci-audit-repo-settings repo=<owner/repo>` to confirm the variables and secrets exist, then dispatch `update.yml` on `main` from the Actions tab. A green run means the `publish` job minted both tokens, wrote the `gh-pages` deploy, and passed live browser verification. A trusted preview deploy on an open PR checks the preview path the same way.
- Percy: dispatch `audit-repo-settings.yml`. A green run, with no new drift issue or with the existing one closed, means the audit token was minted and could read Pages, branch protection, variables, secrets, and the ruleset.

### `gh-pages` branch or Pages root drift

1. Confirm the GitHub Pages source is GitHub Actions.
2. Confirm the `gh-pages` ruleset targets `refs/heads/gh-pages` and blocks create, delete, update, and force-push except for approved bypass actors.
3. If the branch contents are wrong, redeploy a known-good `main` commit. Do not repair `gh-pages` by hand, so the verified artifact stays the source of truth.
4. If a Pages deployment fails before verification starts, read the `Deploy GitHub Pages artifact` step in `update.yml`. The legacy `pages-build-deployment` workflow no longer runs.

### First deploy or `gh-pages` branch recreation

Use this on a new fork that has never deployed, or after someone deleted `gh-pages`.

1. The deploy action creates `gh-pages` when it is missing. On the first deploy it gets a 404 from the git ref lookup, seeds the branch with an initial commit that contains `.nojekyll`, and then writes the site tree. You do not push an empty branch. The REST git API creates the seed commit, so it is unsigned, unlike every later deploy commit (GraphQL `createCommitOnBranch` cannot create a missing branch). Install the ruleset that requires signatures after the seed commit exists.
2. Recreate the `gh-pages` ruleset. Automation cannot create it, and a new branch has none. Target `refs/heads/gh-pages` with the rules in [External GitHub settings](architecture.md#external-github-settings) (block create, delete, update, and force-push, and require linear history and signatures). Keep the Harry1176 deploy app and repo admins as bypass actors so deploys can still write the branch. Install the ruleset after step 1 so it does not block the first branch creation.
3. Confirm the Pages build type is GitHub Actions (`workflow`, not a legacy branch build) with HTTPS enforced, so the official Pages actions publish the deploy tree.
4. Run a `main` deploy (push to `main` or dispatch `update.yml`) and confirm the live URL serves the expected `deploy-metadata.json` SHA and cache-busted asset query strings. Then dispatch `live-site-smoke.yml`, or wait for the daily run, to confirm the published site passes in a real browser.

### Generated-file drift in CI

1. Treat drift as a mismatch between source inputs and generated outputs.
2. Read the generated diff to decide whether the source change or the generator is wrong.
3. Fix the source or the generator, then rerun `make check-generated`.

### Vendored dependency update

1. Download the new UMD build from the `upstream` URL recorded in `config/vendored_assets.json` (jsDelivr) into the recorded `path` of each affected entry. Several apps can vendor one package: `loan-amortization` and `bond-price-vs-rate` both vendor Chart.js. Update every entry that names the package you are bumping.
2. Update the `version`, `upstream`, and `sha256` fields of each affected entry so `make lint-vendored-assets` passes. The `upstream` URL must contain `<package>@<version>`.
3. Run `make audit-vendored`. It fails when OSV lists an advisory for the new version.
4. When a PDF library changed, recheck the hand-written declarations in `config/types/pdf-vendor.d.ts`. Update version numbers in each affected app's docs, for example `apps/loan-amortization/docs/decisions.md`.
5. Run the browser suites before you publish.

### Security gate failure

1. Treat a dependency audit or secret scan failure as a release blocker.
2. Decide whether it is a real leak or vulnerability, an expired exception, or a stale lock or dependency-review mismatch.
3. Resume deploys only after you fix the finding or record a reviewed exception.

## Troubleshooting

- Set `LOG_LEVEL=DEBUG` before a `make` command for verbose build output, for example `LOG_LEVEL=DEBUG make index`. The accepted values are `DEBUG`, `INFO` (the default), `WARNING`, and `ERROR`. `generate_index.py`, `generate_thumbnails.py`, `prepare_site.py`, and `verify_deploy.py` read it.
- If the Playwright Python package is missing, the browser suites fail during collection and `make thumbnails` exits at once. Run `make setup-all`.
- If Chromium is missing, `make check-web`, `make test-browser`, and `make test-browser-live` fail. Run `make setup-all`.
- If the browsers install but fail to launch because the host lacks their shared libraries, run `make setup-playwright-local`, confirm it with `make playwright-local-gate`, and rerun the browser target with `local_libs=1`. `make playwright-local-status` shows which engines the cache covers.
- `make check-local` does not use Playwright, so it stays fast on machines without Chromium.
- To audit repository settings outside the scheduled workflow, run `make ci-audit-repo-settings`. Add `repo=<owner/repo>` to audit another repository.
- If `secret-scan` fails on an event with no commit range (`workflow_dispatch`, `schedule`), check which paths the findings name before treating them as real. That job checks out with `fetch-depth: 0`, so those events walk every branch, including `gh-pages`, where each pull request leaves a built copy of the site under `pr-preview/`. `.gitleaks.toml` excludes that prefix and nothing else. A finding outside it is either one of the five reviewed fingerprints in `.gitleaksignore` (entropy hits on the tokenizer explorer's once-minified `render.js`) or a real secret, in which case you rotate the credential. Accept a reviewed finding by adding its fingerprint to `.gitleaksignore`. Never widen the path allowlist.
- If every workflow on a commit reports `startup_failure` at once, suspect a GitHub incident rather than the workflow files: `make lint-workflows` still passes, and no job ever starts, so there are no logs to read. Once the incident clears, replay each affected run with `make ci-rerun run=<id>` (add `failed=1` to retry only the failed jobs of a partially green run).
- If a replayed deploy fails with `Multiple artifacts named "github-pages" were unexpectedly found`, the retry is the cause, not the payload: attempts of one run share a single artifact namespace, so a second upload of the same name leaves the deploy step with an ambiguity it refuses to resolve. For a main or older-commit redeploy, start a fresh run with `make ci-dispatch workflow=update.yml ref=main` instead of re-running that one again, and pass `inputs="redeploy-sha=<sha>"` when the target is an older commit.
- For an open pull request, push the intended follow-up commit to the PR branch to create a clean `pull_request` run. Do not dispatch `update.yml` on the PR branch for this recovery, because `workflow_dispatch` follows the main-site publish path rather than the PR-preview path.
- If `actions/deploy-pages` times out with `Current status: updating_pages`, check `deploy-metadata.json` on the live site before assuming nothing shipped: a Pages backlog can publish the payload after the action stops waiting, so the deployed `commit_sha` may already match the commit whose run went red.
- To follow a CI run from a noninteractive shell, run `make ci-watch run=<id>` instead of the GitHub CLI watcher. The target resolves the run id, waits for the run to finish, and exits non-zero when the run fails.
- If CI looks like it is redownloading dependencies every run, check whether those lines are cache restores before treating it as a cache miss. A hit logs `Cache hit for: <key>` followed by `Received N of N (100.0%), … MBs/sec` and `Cache restored from key: <key>`, which reads much like a fresh install; the post step then confirms it with `Cache hit occurred on the primary key …, not saving cache`. A genuine miss says `Cache not found for input keys`. Real dependency installation appears separately as `make install` or `npm ci` output. Use `make ci-caches` to see what is stored and how large it is.
- If a cache key is rolled or retired, the old entries are not removed automatically and keep counting against the repository's cache budget. List them with `make ci-caches key=<prefix>` and drop each with `make ci-cache-delete cache=<id|key>`, which accepts a cache id or a cache key in the same slot. Prefer the id: a key is not unique, since one entry exists per ref that built it, and a bare key resolves against the current branch only (add `ref=refs/heads/<branch>` to reach another). Do this only after the change that retires the key is on `main`, since a run on the old code recreates the entry.
- To inspect the deployable output locally, run `make serve`. It builds `_site/` and serves it on `http://localhost:8000/`. Set `PORT=NNNN` to change the port.
- If `make security` fails on the npm audit, either a new advisory in the dependency graph needs triage, or a reviewed exception in `config/security_audit.json` has expired or matches no active advisory.
- If `make security` fails on the Python audit, a new vulnerability needs triage, an exception has passed its review date, an exception matches nothing in the lock files, or a fix exists for an exception that sets `ignore_only_without_fix: true`. [Dependency audits](checks.md#dependency-audits) describes exception matching and defaults.
- If `make security` fails on the vendored dependency audit, read the first message. `Unreviewed vendored vulnerability` means OSV lists an advisory for a bundled version. Upgrade the bundle to a fixed version and update its entry in `config/vendored_assets.json`, or add a reviewed exception under `vendored_vulnerability_exceptions` with a `reason` and a `review_by` date. `could not query OSV` means `api.osv.dev` stayed unreachable after three attempts, so rerun the job. `could not use the OSV response` and `could not read config/vendored_assets.json` mean the data is malformed. No exception can silence those, so fix the manifest or the record the message names.
- If the post-deploy verifier flakes, inspect both the published `?v=<sha>` asset query strings and the deployed `deploy-metadata.json` payload before rerunning.
- If live browser verification fails in CI, download the `live-browser-artifacts-<run_id>` artifact for screenshots, traces, and runtime error logs.
- If the daily live-site smoke workflow fails, inspect the `live-site-smoke-artifacts-<run_id>` artifact and the automatically managed GitHub issue before rerunning.
- If README auto markers are missing or duplicated, `scripts/build/generate_index.py` fails instead of corrupting the file.
- With no artifacts, the index generator still writes a valid empty `js/data.js`.
- After you change Python dependency declarations, run `make lock` before you commit. To move only some packages, run `make lock-update packages="package-a package-b"`.
- After you change Node dependency declarations, run `make lock-node` before you commit. To move only some packages, for example to clear an advisory, run `make lock-node-update packages="package-a package-b"` instead of refreshing the whole lockfile.
- If you delete generated thumbnails from the working tree, `js/data.js` keeps the canonical `apps/<slug>/thumbnail.webp` path while CI regenerates the files.

See [`maintenance.md`](maintenance.md) for the long-term upkeep checklist.
