# Operations

## Day-to-day local workflow

Use the Makefile instead of ad hoc shell commands.

```bash
make new name=... # scaffold a new artifact directory with placeholder files
make setup      # create .venv, install pinned Python/Node deps, install Chromium locally
make check      # run Python/JS lint, Python/JS tests, browser smoke tests, and artifact validation
make coverage-js # print Node test-runner coverage for tracked JS modules
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

1. `make new name=my-artifact` if you want a scaffold instead of creating files by hand
2. `make setup`
3. edit files
4. `make check`
5. `make coverage-js` if you want the same JavaScript coverage table CI records in the step summary
6. `make security` before opening a PR when you touched dependency declarations or workflow/runtime code
7. `make validate` if you changed top-level artifact directories and want an explicit structure check
8. `make index` if metadata or README markers may have changed
9. `make thumbnails` only if you need fresh local thumbnails and Playwright is available
10. `make site` if you want to inspect the exact Pages output locally
11. `make lock` if you changed Python dependency declarations, and refresh `package-lock.json` if you changed Node dependencies

## CI behavior

The production workflow uses the same command surface:

- `make setup-ci`
- `make lint`
- `make test`
- `make coverage-js`
- `make validate`
- `make security`
- `make thumbnails`
- `make index`
- `make site`

This keeps local and CI behavior aligned and reduces workflow-specific shell logic.

`update.yml` now handles production deploys and pull request previews.

- `verify` is a read-only job that runs setup, lint, tests, browser smoke tests, dependency audit, strict thumbnail generation, generation, and `_site/` assembly
- `verify` also records a JavaScript coverage report from Node's built-in test runner without adding extra coverage dependencies
- `secret-scan` runs Gitleaks against the checked-out repository
- pull requests also run dependency review for manifest and lockfile changes
- same-repo Dependabot Python PRs also trigger `.github/workflows/refresh-python-locks.yml`, which computes refreshed lock files on the PR branch and commits them back from a follow-up trusted workflow run after artifact validation and PR head revalidation
- `publish` is the main write-capable job; it regenerates outputs, commits generated files when needed, prepares `_site/`, deploys previews or `gh-pages`, and then verifies the published URL serves the new asset version
- `cleanup-preview` is a write-capable cleanup job that removes preview deployments and comments when PRs close
- trusted pull requests publish preview deployments under `pr-preview/pr-<number>/`
- pull requests leave the source branch untouched while preview comments provide the live preview link
- preview deploys use the GitHub App token
- preview comments use the workflow token, appear as `github-actions[bot]`, and are recreated on each push so the newest preview stays at the bottom of the PR timeline
- fork-based and Dependabot PRs still run checks and site assembly, but skip preview deployment because the app token is unavailable in those contexts

## Coverage and quality gates

- `ruff` runs against `scripts/` and `tests/`
- `eslint` runs against browser modules, Node tests, and workflow helper code
- `pytest` enforces 100% line coverage for the `scripts` package
- `node --test` covers shared browser and workflow helper modules under `tests/js/`
- `make coverage-js` uses Node's built-in experimental coverage output as the no-new-dependencies approximation for JavaScript coverage reporting and enforces the current baseline gate of 95% lines, 85% branches, and 95% functions across the tracked JavaScript/module set
- `make security` mirrors the practical local dependency audits in CI; Gitleaks and GitHub dependency review remain CI-only because this repo does not vendor those scanners locally
- Playwright smoke tests validate the built root gallery and `404.html` routing behavior when Chromium is installed
- `make validate` fails if a top-level artifact directory is missing `index.html` or `name.txt`, has an empty `name.txt`, or uses a non-kebab-case directory name
- coverage policy is configured in `pyproject.toml`

## Thumbnail policy

- `thumbnail.webp` is the preferred generated format
- local and CI thumbnail generation skips artifacts whose checked-in thumbnails are already up to date
- CI sets `ARTIFACTS_STRICT_THUMBNAILS=1`, so any attempted thumbnail failure fails the workflow instead of being logged as a warning
- local working copies do not need checked-in thumbnails to function during development
- CI can regenerate thumbnails after push or during pull request preview builds
- the generator still tolerates legacy `thumbnail.png` when present so older generated states do not break the gallery

## Required GitHub settings

The workflow assumes these repository settings already exist:

- GitHub Pages publishes from the `gh-pages` branch root
- repository variables include `APP_ID`
- repository secrets include `APP_PRIVATE_KEY`
- `main` branch protection requires `verify`, `secret-scan`, and `dependency-review`, plus 1 approval, signed commits, linear history, and conversation resolution
- `gh-pages` is protected by a branch ruleset that restricts updates/deletions/creations, blocks force pushes, and requires linear history, with bypass limited to the deploy GitHub App and the repo admin role
- this repo intentionally operates as a single-admin repo, so admin-role bypass is the acceptable stand-in for owner-only bypass on `gh-pages`

## Rollback and recovery

- if a deployment is bad, restore the site by redeploying a known-good `main` commit
- if generated-file commits fail on `main`, look for the fallback PR created by the verified-commit action and merge or close it intentionally
- if PR previews stop publishing, verify `APP_ID`, `APP_PRIVATE_KEY`, and GitHub App installation access first
- if a deploy succeeds but the publish job fails afterward, check the post-deploy verification step for Pages propagation delay or stale HTML responses
- if Pages serves the wrong root, confirm the repository is still configured for branch-based deployment from `gh-pages`
- if dependency audit or secret scanning starts failing, treat that as a release blocker until triaged

## Troubleshooting

- if the Playwright Python package is unavailable locally, browser smoke tests fail during collection and `make thumbnails` exits immediately; rerun `make setup`
- if Chromium is unavailable locally, browser smoke tests are skipped; run `make setup` to install it
- if Chromium is unavailable locally, `make thumbnails` can still fail even though `make check` succeeds with skipped smoke tests
- if you want to inspect the deployable output locally, run `make site` and serve `_site/` from a static file server
- if `make security` fails on `npm audit`, the issue is in the current workspace dependency graph and needs triage before release
- if the post-deploy verifier flakes, rerun the workflow and inspect whether the published page is still serving the previous `?v=<sha>` asset query strings
- if README auto markers are removed or duplicated, `scripts/generate_index.py` fails fast instead of silently corrupting the file
- if no artifacts exist, the index generator still writes a valid empty `js/data.js`
- if Python dependency declarations change, rerun `make lock` before committing
- if Node dependency declarations change, refresh `package-lock.json` before committing
- if generated thumbnails are intentionally removed from the working tree, `js/data.js` will emit `thumbnail: null` until CI regenerates them

See [`maintenance.md`](maintenance.md) for the long-term upkeep checklist.
