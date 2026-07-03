# Operations

## Day-to-day local workflow

Use the Makefile instead of ad hoc shell commands.

```bash
make help       # see all available targets (auto-generated, two-level)
make setup      # fast: Python + Node deps, no Chromium
make setup-all  # full: also installs Chromium for browser tests and thumbnails
make pr         # show all PR sub-commands
make ci         # full non-browser local CI gate
make help-ci    # show CI and GitHub run sub-commands
make git        # show all git sub-commands
```

On a Linux distro newer than the pinned Playwright supports (for example Ubuntu 26.04 on WSL), `playwright install` and browser launches abort with `Playwright does not support chromium on <distro>`. The Makefile detects this and exports `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE` (a supported fallback platform key) for every Playwright target, so `make setup-all`, `make test-browser-*`, and `make thumbnails` work unchanged. CI runs on a supported image where the override stays empty. Override or disable it by setting `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE` in your environment.

Recommended workflow when changing workspace code:

1. `make new name=my-artifact` if you want a scaffold instead of creating files by hand. It also creates the matching `tests/js/apps/<slug>/` directory for app-specific Node tests.
2. `make setup` for fast local work, or `make setup-all` if you also need Chromium.
3. Edit files.
4. Run `make check-local`.
5. Run `make check-web` when you touch shared browser behavior or need fresh thumbnails. For targeted mature-app browser work, use `ARTIFACTS_BROWSER_APP_SLUGS="app-slug" make test-browser-apps`.
6. Run `make check` before opening a PR when you want the full CI-equivalent local gate.
7. Run `make validate` if you changed top-level artifact directories and want an explicit structure check.
8. Run `make index` if metadata or README markers may have changed.
9. Run `make site` if you want to inspect the exact Pages output locally.
10. Run `make lock` if you changed Python dependency declarations, and run `make lock-node` if you changed Node dependencies.

## CI behavior

CI uses the same `make` targets as local development. The `verify` job in `update.yml` runs:

- `make setup-ci`, then `scripts/ci/run_parallel_checks.py` runs `format-check`, `lint`, `test-py`, `coverage-js`, `dead-code`, `security`, `validate`, and `test-browser-root` concurrently, followed by conditional `make test-browser-apps`, then `make thumbnails`, `make check-generated`, `make index`, `make site`

This keeps local results predictive of CI results.

For the full pipeline reference (job flow diagrams, token model, artifact flow, script dependencies, and deploy behavior), see [architecture.md](architecture.md#cicd-layer).

## Coverage and quality gates

- `make editorconfig-check` enforces supported `.editorconfig` rules such as LF endings, final-newline policy, trailing whitespace trimming, and indentation style for covered repository files, while skipping configured cache/build/dependency directories and binary assets.
- `ruff` scans the repo root; built-in excludes skip `.venv/`, `node_modules/`, etc. Config: `pyproject.toml`.
- `eslint` scans the repo root; file patterns and ignores are in `eslint.config.js`.
- `stylelint` scans all `**/*.css`; ignores are in `stylelint.config.js`.
- `yamllint` scans the repo root; ignores are in `.yamllint.yml`.
- Workflow linting runs through `scripts/lint/lint-workflows.mjs`, which wraps `actionlint` across `.github/workflows/*.yml` and `.github/workflows/*.yaml`.
- `make lint-doc-commands` checks contributor-facing docs for direct commands that should use Make targets instead.
- `make lint-make-targets` verifies that documented `make <target>` references still exist in `Makefile`.
- `make lint-js-test-coverage` verifies that every JS or MJS source file under the tracked source roots is imported by at least one test file.
- `make format-check` verifies ruff formatting plus Prettier-managed docs, metadata, workflows, and tooling scripts without writing files.
- `make dead-code` runs vulture for Python and Knip for JavaScript files, exports, and dependency usage.
- `make check-overrides` reports whether npm `overrides` are still needed when that package field exists.
- `pytest` enforces 100% line coverage for the `scripts` package.
- `make test-ci` runs the CI-focused Python tests under `tests/ci/`.
- `make test-ci-workflows` runs narrow contract tests against `.github/workflows/*.yml` so local and CI checks can catch workflow-structure drift early.
- `node --test` covers the grouped Node suites under `tests/js/home/`, `tests/js/common/`, `tests/js/apps/`, and `tests/js/workflows/`.
- `make coverage-js` uses Node's built-in experimental coverage output and enforces the current baseline gate of 95% lines, 85% branches, and 95% functions across all source files imported by the grouped `tests/js/` suites. Coverage excludes `node_modules/` and `tests/`; thresholds and exclusions are configured in `package.json`.
- `make security` mirrors the practical local dependency audits in CI; the Python side runs a policy-driven audit over the configured lock files and reviewed vulnerability exceptions in `config/security_audit.json`, matches exceptions by lock file, package, and vulnerability id or alias, and fails expired, unused, or now-fixable exceptions, while Gitleaks and GitHub dependency review remain CI-only because this repo does not vendor those scanners locally.
- `make check-generated` reruns the index generator in a restore-safe mode and fails if `README.md`, `js/data.js`, or `js/gallery-config.js` would drift from tracked source inputs.
- Playwright browser suites validate both the built root gallery and mature app pages through `make test-browser`, while CI selectively scopes mature app suites with `ARTIFACTS_BROWSER_APP_SLUGS`.
- `make test-browser-live` verifies an already-published site in a real browser when `ARTIFACTS_LIVE_SITE_URL` is set, and CI captures failure screenshots/traces/logs through `ARTIFACTS_BROWSER_ARTIFACT_DIR`.
- Scheduled CI monitoring now uses GitHub-native issue alerts: `.github/workflows/audit-repo-settings.yml` opens/closes a single repository-settings drift issue, and `.github/workflows/live-site-smoke.yml` opens/closes a single live-site smoke issue.
- `make ci` is the full non-browser local gate without browser Playwright suites or thumbnail generation, and it includes formatting, linting, tests, coverage, dead-code checks, dependency audits, validation, and canonical generated-file drift checks. `make check-local` is an alias.
- `make test-browser-root-smoke`, `make test-browser-root-accessibility`, and `make test-browser-root-flows` let you run the root gallery Playwright suites separately.
- `make test-browser-apps-smoke`, `make test-browser-apps-accessibility`, and `make test-browser-apps-flows` let you run the mature app Playwright suites separately while preserving `make test-browser-apps` as the aggregate app gate.
- `make check-web` is the browser-only gate for the aggregate root/app browser suites and thumbnails.
- `make validate` fails if a top-level artifact directory is missing `index.html` or `name.txt`, has an empty `name.txt`, or uses a non-kebab-case directory name.
- Coverage policy is configured in `pyproject.toml`.

## Thumbnail policy

- `thumbnail.webp` is the preferred generated format.
- Local and CI thumbnail generation skips artifacts whose checked-in thumbnails are already up to date. CI auto-invalidates thumbnails for apps whose runtime changed (`index.html`, `js/**`, `assets/**`) or when shared site assets changed, using `scripts/ci/workflow_helpers.py invalidate-thumbnails`.
- CI does not trigger mature-app browser suites for app docs or metadata-only edits; the thumbnail plan uses the same runtime-change classification to scope mature-app browser runs.
- CI sets `ARTIFACTS_STRICT_THUMBNAILS=1`, so any attempted thumbnail failure fails the workflow instead of being logged as a warning.
- Local working copies do not need checked-in thumbnails to function during development.
- CI can regenerate thumbnails after push or during pull request preview builds, and trusted runs can save those generated `thumbnail.webp` files back to the same PR branch or open/update a follow-up PR for `main` pushes.

## Required GitHub settings

See [architecture.md: External GitHub settings](architecture.md#external-github-settings) for the full list of required repository settings (Pages, branch protection, app tokens, secrets, rulesets). Use `make help-ci` to discover the `make ci-audit-repo-settings` wrapper for the manual drift check.

## Vendored runtime dependencies

- There are no external CDN dependencies at runtime. All third-party scripts are vendored locally.
- `apps/loan-amortization/js/vendor/` contains:
  - Chart.js `4.4.1`
  - `chartjs-plugin-annotation` `3.0.1`
  - `chartjs-plugin-datalabels` `2.2.0`
- Versions are pinned and upgraded manually for stability. To upgrade, download the new UMD builds from cdnjs, replace the files in `js/vendor/`, and rerun the browser suites.
- Vendored directories are excluded from ESLint (`**/vendor/**` in `eslint.config.js`) and lint checks (`vendor` in `scripts/lint/__init__.py` `SKIP_DIRECTORIES`).
- See `apps/loan-amortization/docs/decisions.md` for rationale.

### Self-hosted fonts

- Gallery display fonts (Caveat, Fredoka One) are self-hosted as WOFF2 Latin subsets in `assets/fonts/`.
- `@font-face` declarations live in `css/style.css`.
- When adding a new font, download the WOFF2 subset into `assets/fonts/`, add the `@font-face` rule to `css/style.css`, and verify the CSP `font-src 'self'` directive still covers it.

### Adding external assets to a new artifact

All runtime assets should be self-hosted. Do not load scripts, fonts, or stylesheets from external CDNs. For third-party JS libraries, download UMD builds into a `js/vendor/` directory inside the app. Browser tests will flag any unexpected external requests as failures.

## Rollback and recovery

### Bad main deploy

1. Identify the last known-good commit on `main`.
2. Trigger the strict deploy workflow for that commit through the normal push/manual path so the repo rebuilds `_site/` and deploys from a verified artifact again.
3. Verify the published site serves the expected `deploy-metadata.json` SHA and cache-busted asset query strings before declaring recovery complete.

### Broken PR preview

1. Check whether the PR is trusted (same-repo, non-Dependabot) so preview deployment is actually allowed.
2. Verify `APP_ID`, `APP_PRIVATE_KEY`, `ESCALATION_APP_ID`, `ESCALATION_APP_PRIVATE_KEY`, `AUDIT_APP_ID`, and `AUDIT_APP_PRIVATE_KEY` still exist and the GitHub Apps still have repository installation access.
3. Inspect the `publish` job summary, then download browser artifacts if live-browser verification failed after deployment.

### Token rotation or GitHub App outage

1. Rotate the affected key in the GitHub App first. Hermione1176, Harry1176, and Percy1176 all follow the same procedure.
2. Update the matching repository secret immediately after rotation.
3. Re-run `make ci-audit-repo-settings repo=<owner/repo>` to confirm the repo still matches the documented contract.
4. Re-run a trusted preview deploy before relying on the next `main` publish.

### `gh-pages` branch or Pages root drift

1. Confirm GitHub Pages is still branch-based from `gh-pages` with path `/`.
2. Confirm the `gh-pages` ruleset still targets `refs/heads/gh-pages` and still blocks create/delete/update/force-push operations except for approved bypass actors.
3. If the branch contents are wrong, redeploy a known-good `main` commit instead of repairing `gh-pages` manually so the verified artifact path stays the source of truth.

### Generated-file drift in CI

1. Treat generated drift as a source-of-truth mismatch, not a deploy-time nuisance.
2. Inspect the generated diff and determine whether the source change or the generator contract is wrong.
3. Land the source or generator fix, then rerun the strict gate.

### Vendored dependency update

1. Download the new UMD builds from cdnjs into `apps/loan-amortization/js/vendor/`.
2. Update the version numbers in `apps/loan-amortization/docs/decisions.md`.
3. Run browser suites before publishing and update the app README if the version changed.

### Security gate failure

1. Treat dependency audit or secret scan failures as release blockers.
2. Triage whether the issue is a real leak/vulnerability, an expired exception, or a stale lock/dependency review mismatch.
3. Only resume deploys after the finding is resolved or consciously documented.

## Troubleshooting

- Set `LOG_LEVEL=DEBUG` before any `make` command to get verbose output from build scripts (e.g., `LOG_LEVEL=DEBUG make index`). Accepted values: `DEBUG`, `INFO` (default), `WARNING`, `ERROR`. Applies to `generate_index.py`, `generate_thumbnails.py`, `prepare_site.py`, and `verify_deploy.py`.
- If the Playwright Python package is unavailable locally, browser Playwright suites fail during collection and `make thumbnails` exits immediately; rerun `make setup-all`.
- If Chromium is unavailable locally, `make check-web`, `make test-browser`, and `make test-browser-live` fail; run `make setup-all` to install it.
- `make check-local` intentionally avoids Playwright so it can stay fast on machines without Chromium.
- If you need to manually audit repository settings drift outside the scheduled workflow, run `make help-ci` to discover `make ci-audit-repo-settings`, then pass `repo=<owner/repo>` when auditing a different repository.
- If you want to inspect the deployable output locally, run `make site` and serve `_site/` from a static file server.
- If `make security` fails on `npm audit`, the issue is in the current workspace dependency graph and needs triage before release.
- If `make security` fails on the Python audit, either a new vulnerability needs triage, an exception review date has expired, an exception no longer matches the current lock files, or a fix is now available and the temporary exception must be removed.
- If the post-deploy verifier flakes, inspect both the published `?v=<sha>` asset query strings and the deployed `deploy-metadata.json` payload before rerunning.
- If live browser verification fails in CI, download the `live-browser-artifacts-<run_id>` artifact for screenshots, traces, and runtime error logs.
- If the daily live-site smoke workflow fails, inspect the `live-site-smoke-artifacts-<run_id>` artifact and the automatically managed GitHub issue before rerunning.
- If README auto markers are removed or duplicated, `scripts/build/generate_index.py` fails fast instead of silently corrupting the file.
- If no artifacts exist, the index generator still writes a valid empty `js/data.js`.
- If Python dependency declarations change, rerun `make lock` before committing.
- If Node dependency declarations change, run `make lock-node` before committing.
- If generated thumbnails are intentionally removed from the working tree, `js/data.js` will emit `thumbnail: null` until CI regenerates them.

See [`maintenance.md`](maintenance.md) for the long-term upkeep checklist.
