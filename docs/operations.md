# Operations

## Day-to-day local workflow

Use the Makefile instead of ad hoc shell commands.

```bash
make new name=... # scaffold a new artifact directory with placeholder files
make setup-local # create .venv, install pinned Python/Node deps without Chromium
make setup      # create .venv, install pinned Python/Node deps, install Chromium locally
make check-local # run the fast local gate without browser Playwright suites or thumbnails
make web        # run browser smoke/accessibility/browser-flow tests and thumbnail generation
make check      # run the full release gate, including local + web checks, index generation, and site assembly
make coverage-js # print Node test-runner coverage for js/app.js, js/modules/*.js, the verified-commit action module, and the deploy-site action module
make editorconfig-check # verify supported .editorconfig rules for covered repository files
make security   # run the local dependency audits used in CI
make validate   # fail fast on incomplete or invalid top-level artifact directories
make index      # rebuild js/data.js, js/gallery-config.js, and README auto markers
make thumbnails # regenerate WebP thumbnails when Playwright is available
make site       # assemble the clean deployable Pages payload in _site/
make generate   # run thumbnails and index together
make lock       # refresh locks/requirements.lock and locks/requirements-dev.lock after dependency changes
make align-tables # align markdown table pipe characters across all docs
make clean       # remove .venv, caches, build artifacts, and node_modules
```

Recommended workflow when changing workspace code:

1. `make new name=my-artifact` if you want a scaffold instead of creating files by hand.
2. `make setup-local` for fast local work, or `make setup` if you also need Chromium.
3. Edit files.
4. Run `make check-local`.
5. Run `make web` when you touch root-gallery browser behavior or need fresh thumbnails.
6. Run `make check` before opening a PR when you want the full CI-equivalent local gate.
7. Run `make validate` if you changed top-level artifact directories and want an explicit structure check.
8. Run `make index` if metadata or README markers may have changed.
9. Run `make site` if you want to inspect the exact Pages output locally.
10. Run `make lock` if you changed Python dependency declarations, and refresh `package-lock.json` if you changed Node dependencies.

## CI behavior

The production workflow uses the same command surface:

- `make setup-ci`
- `make check`

This keeps local and CI behavior aligned and reduces workflow-specific shell logic.

`update.yml` now handles production deploys and pull request previews.

- `verify` is a read-only job that runs `make check`, which bundles local lint/test/audit/validation work, browser smoke/accessibility/browser-flow tests, thumbnail generation, content generation, and `_site/` assembly.
- `verify` also records a JavaScript coverage report from Node's built-in test runner without adding extra coverage dependencies.
- `verify` uploads the exact `_site/` output as a workflow artifact so previews and production deploys can consume the verified build instead of rebuilding later.
- `secret-scan` runs Gitleaks against the checked-out repository.
- Pull requests also run dependency review for manifest and lockfile changes.
- Same-repo Dependabot Python PRs also trigger `.github/workflows/refresh-python-locks.yml`, which computes refreshed lock files on the PR branch; `.github/workflows/commit-python-locks.yml` performs the trusted follow-up artifact validation and commit after PR head revalidation.
- `publish` is the main write-capable job; it downloads the verified `_site/` artifact from `verify`, deploys previews or `gh-pages` from that exact build, verifies the published URL serves both the expected cache-busted asset reference and the expected deploy metadata commit SHA, and then runs `make test-browser-live` against the deployed URL.
- `cleanup-preview` is a write-capable cleanup job that removes preview deployments and comments when PRs close.
- Workflow trust-policy, lock-artifact validation, thumbnail invalidation, fallback PR detection, and repository-settings audit logic is intentionally kept thin; `scripts/workflow_helpers.py` owns those tested helper paths.
- Trusted pull requests publish preview deployments under `pr-preview/pr-<number>/`.
- Pull requests leave the source branch untouched while preview comments provide the live preview link.
- Generated files may differ in the verified workspace, but the release path never auto-commits those differences back to contributor branches.
- All deploys (main, preview, and cleanup) use the escalation app token (Harry1176) and create verified commits via the GraphQL API (`deploy-verified.mjs`).
- Preview comments use the workflow token, appear as `github-actions[bot]`, and are recreated on each push so the newest preview stays at the bottom of the PR timeline.
- Fork-based and Dependabot PRs still run checks and site assembly, but skip preview deployment because the app token is unavailable in those contexts.
- `.github/workflows/audit-repo-settings.yml` runs a read-only manual/weekly audit that checks Pages, branch protection, Actions variables/secrets, and the `gh-pages` ruleset for drift.

## Coverage and quality gates

- `scripts/check_editorconfig.py` enforces supported `.editorconfig` rules such as LF endings, final-newline policy, trailing whitespace trimming, and indentation style for covered repository files, while skipping configured cache/build/dependency directories and binary assets.
- `ruff` runs against `scripts/` and `tests/`.
- `eslint` runs against browser modules, Node tests, the custom workflow helper, and repo-level JavaScript config/scripts.
- `stylelint` runs against `css/**/*.css`.
- `yamllint` runs against `.github/` with a repo-local `.yamllint.yml` tuned for GitHub Actions and Dependabot files.
- Workflow linting runs through `scripts/lint-workflows.mjs`, which wraps `actionlint` across `.github/workflows/*.yml` and `.github/workflows/*.yaml`.
- `pytest` enforces 100% line coverage for the `scripts` package.
- `node --test` covers shared browser and workflow helper modules under `tests/js/`.
- `make coverage-js` uses Node's built-in experimental coverage output as the no-new-dependencies approximation for JavaScript coverage reporting and enforces the current baseline gate of 95% lines, 85% branches, and 95% functions across `js/app.js`, `js/modules/*.js`, `.github/actions/verified-commit/*.mjs`, and `.github/actions/deploy-site/*.mjs`.
- `make security` mirrors the practical local dependency audits in CI; the Python side runs a policy-driven audit over the configured lock files and reviewed vulnerability exceptions in `config/security_audit.json`, matches exceptions by lock file, package, and vulnerability id or alias, and fails expired, unused, or now-fixable exceptions, while Gitleaks and GitHub dependency review remain CI-only because this repo does not vendor those scanners locally.
- Playwright browser suites validate the built root gallery and `404.html` routing behavior through `make test-browser`, including smoke, accessibility, and browser-flow coverage.
- `make test-browser-live` verifies an already-published site in a real browser when `ARTIFACTS_LIVE_SITE_URL` is set, and CI captures failure screenshots/traces/logs through `ARTIFACTS_BROWSER_ARTIFACT_DIR`.
- `make check-local` is the fast local gate without browser Playwright suites or thumbnail generation.
- `make web` is the browser-only gate for smoke/accessibility/browser-flow tests and thumbnails.
- `make validate` fails if a top-level artifact directory is missing `index.html` or `name.txt`, has an empty `name.txt`, or uses a non-kebab-case directory name.
- Coverage policy is configured in `pyproject.toml`.

## Thumbnail policy

- `thumbnail.webp` is the preferred generated format.
- Local and CI thumbnail generation skips artifacts whose checked-in thumbnails are already up to date. CI also auto-invalidates thumbnails for apps whose `index.html` changed in the PR or push, using `workflow_helpers.py invalidate-thumbnails`.
- CI sets `ARTIFACTS_STRICT_THUMBNAILS=1`, so any attempted thumbnail failure fails the workflow instead of being logged as a warning.
- Local working copies do not need checked-in thumbnails to function during development.
- CI can regenerate thumbnails after push or during pull request preview builds.
- The generator still tolerates legacy `thumbnail.png` when present so older generated states do not break the gallery.

## Required GitHub settings

The workflow assumes these repository settings already exist:

- GitHub Pages publishes from the `gh-pages` branch root.
- Repository variables include `APP_ID` (Hermione1176) and `ESCALATION_APP_ID` (Harry1176).
- Repository secrets include `APP_PRIVATE_KEY` and `ESCALATION_APP_PRIVATE_KEY`.
- `main` branch protection requires `verify`, `secret-scan`, and `dependency-review`, plus 1 approval, signed commits, linear history, and conversation resolution.
- `gh-pages` is protected by a branch ruleset that restricts updates, deletions, and creations, blocks force pushes, and requires linear history, with bypass limited to the deploy GitHub App and the repo admin role.
- This repo intentionally operates as a single-admin repo, so admin-role bypass is the acceptable stand-in for owner-only bypass on `gh-pages`.
- `.github/workflows/audit-repo-settings.yml` is the source-controlled drift check for these assumptions.

## Rollback and recovery

- If a deployment is bad, restore the site by redeploying a known-good `main` commit through the strict push/manual workflow path.
- If generated files drift in CI, treat that as a signal to inspect the generated diff and decide whether the source change or the generated output contract needs updating; the release path intentionally does not auto-commit those files.
- If PR previews stop publishing, verify `APP_ID`, `APP_PRIVATE_KEY`, and GitHub App installation access first.
- If a deploy succeeds but the publish job fails afterward, check the post-deploy verification step for Pages propagation delay, stale HTML responses, or mismatched `deploy-metadata.json` content.
- If Pages serves the wrong root, confirm the repository is still configured for branch-based deployment from `gh-pages`.
- If dependency audit or secret scanning starts failing, treat that as a release blocker until triaged.

## Troubleshooting

- If the Playwright Python package is unavailable locally, browser Playwright suites fail during collection and `make thumbnails` exits immediately; rerun `make setup`.
- If Chromium is unavailable locally, `make web`, `make test-browser`, and `make test-browser-live` fail; run `make setup` to install it.
- `make check-local` intentionally avoids Playwright so it can stay fast on machines without Chromium.
- If you want to inspect the deployable output locally, run `make site` and serve `_site/` from a static file server.
- If `make security` fails on `npm audit`, the issue is in the current workspace dependency graph and needs triage before release.
- If `make security` fails on the Python audit, either a new vulnerability needs triage, an exception review date has expired, an exception no longer matches the current lock files, or a fix is now available and the temporary exception must be removed.
- If the post-deploy verifier flakes, inspect both the published `?v=<sha>` asset query strings and the deployed `deploy-metadata.json` payload before rerunning.
- If live browser verification fails in CI, download the `live-browser-artifacts-<run_id>` artifact for screenshots, traces, and runtime error logs.
- If README auto markers are removed or duplicated, `scripts/generate_index.py` fails fast instead of silently corrupting the file.
- If no artifacts exist, the index generator still writes a valid empty `js/data.js`.
- If Python dependency declarations change, rerun `make lock` before committing.
- If Node dependency declarations change, refresh `package-lock.json` before committing.
- If generated thumbnails are intentionally removed from the working tree, `js/data.js` will emit `thumbnail: null` until CI regenerates them.

See [`maintenance.md`](maintenance.md) for the long-term upkeep checklist.
