# Quality checks

This reference describes the check targets and their configuration. [Operations](operations.md) gives the steps for local verification.

## Formatting and lint

- `make editorconfig-check` enforces the supported `.editorconfig` rules (LF endings, final newline, trailing whitespace, and indentation style) on covered files. It skips cache, build, and dependency directories and binary assets.
- `make lint-py` runs ruff on the repo root. Config: `pyproject.toml`.
- `make lint-js` runs ESLint on the repo root. Patterns and ignores: `config/eslint.config.js`.
- `make lint-css` runs stylelint on `**/*.css`. Ignores: `config/stylelint.config.js`.
- `make lint-yaml` runs yamllint on the repo root. Ignores: `.yamllint.yml`.
- `make lint-workflows` runs `scripts/lint/lint-workflows.mjs`, which wraps `actionlint` over `.github/workflows/*.yml` and `.github/workflows/*.yaml`. It drops the `undefined variable "vars"` diagnostic and reports everything else.
- `make lint-doc-commands` checks `README.md`, `CLAUDE.md`, `.github/CONTRIBUTING.md`, `.github/pull_request_template.md`, and `docs/operations.md` for direct commands that should be Make targets.
- `make lint-make-targets` checks that every `make <target>` reference in Markdown, in `.github` YAML shell blocks, and in non-test Python or JavaScript source names a target in `Makefile` or `mk/*.mk`. It also rejects raw shell control flow (`if`, `for`, `while`, `case`) in recipes, unless the target is on the allowlist in `scripts/lint/make_targets.py`.
- `make lint-js-test-coverage` checks that at least one test file under `tests/js/` imports every JS or MJS source file under `js/` and `apps/`. It skips the generated `js/data.js` and `js/gallery-config.js`, vendored files, and `docs/` directories.
- `make lint-artifact-csp` checks the root `index.html` and every `apps/<slug>/index.html`. Each page needs a Content-Security-Policy meta tag in the head, before any markup that can load a resource. The policy must:
  - limit `default-src` and `script-src` to `'self'` or `'none'`, and limit any `img-src` to `'self'`, `'none'`, or `data:`;
  - set `object-src 'none'`;
  - restrict `base-uri` and `form-action` to `'self'` or `'none'`, because those two do not fall back to `default-src`.

  The check fails when a directive appears twice, because browsers ignore every copy after the first. It fails on external scripts, external stylesheets, and external `url()` resources. The root page may load images from `https://img.shields.io` for its badges. Artifact pages may not. The check does not cover `frame-ancestors`, because browsers ignore it in a meta tag and GitHub Pages does not let a repository set response headers.
- `make lint-app-css-tokens` checks app CSS colors, radii, font sizes, and letter spacing against shared tokens. It fails when no stylesheets are found. [Style guide](style.md#token-lint) lists allowed values and exceptions.
- `make lint-vendored-assets` reconciles the vendored bundles under `apps/*/js/vendor/` with the integrity manifest in `config/vendored_assets.json`. It fails on unlisted files, missing files, and SHA-256 mismatches. Each entry needs a lower-case npm package name, a semantic version, and an `upstream` URL that contains `<package>@<version>`. OSV matches names case-sensitively and returns nothing for an unknown name or version, so the audit needs exact values.
- `make check-overrides` runs `scripts/check-overrides.mjs`. When `package.json` has an `overrides` field, the script checks that `npm install` and `npm audit` still pass without those entries. It fails when the entries are stale. With no `overrides` field, it passes.
- `make format-check` verifies ruff formatting, Markdown table alignment, and Prettier formatting for metadata, config, workflows, and tooling scripts. It does not write files.

## Types, tests, and unused code

- `make typecheck` runs `make typecheck-py` (mypy strict over `scripts/`) and `make typecheck-web` (`tsc` with `checkJs` over `js/` and `apps/*/js/`, configured in `config/jsconfig.json`).
- `make dead-code` runs vulture for Python, and Knip for JavaScript files, exports, and dependencies.
- `make test-py` runs every Python test except `tests/browser/`. It enforces 100% line and branch coverage for the `scripts` package and treats warnings as errors. Pass `ARGS="-k name --no-cov"` to run a subset.
- `make test-ci` runs the CI-focused Python tests under `tests/ci/`.
- `make test-ci-workflows` runs narrow contract tests against `.github/workflows/*.yml`, so workflow-structure drift shows up locally.
- `make test-js` runs the Node suites under `tests/js/home/`, `tests/js/common/`, `tests/js/apps/`, `tests/js/tooling/`, and `tests/js/workflows/`.
- `make coverage-js` uses Node's built-in experimental coverage output. It enforces the baseline gate of 95% lines, 85% branches, and 95% functions across all source files that the `tests/js/` suites import. Thresholds and exclusions are in `package.json`.
- `make coverage-js-floors` checks per-file JS coverage floors (80% lines, 70% branches) with the LCOV output that `make coverage-js` writes to `.artifacts/js-coverage.lcov`. If the report is missing, it reruns the suite. The floor constants are in `scripts/lint/check-js-coverage-floors.mjs`.

## Dependency audits

The dependency audit targets use the shared policy:

- `make security` runs `make audit-python`, `make audit-node`, and `make audit-vendored`.
- `make audit-python` exports the frozen uv graph and checks it with pip-audit. It matches reviewed exceptions in `config/security_audit.json` by package name and by vulnerability ID or alias. Expired and unused exceptions fail the check.
- `make audit-node` checks npm advisories through `scripts/ci/run_npm_audit.py`. It matches `npm_vulnerability_exceptions` by package name and by advisory ID or alias. It rejects expired or unused exceptions.
- `make audit-vendored` runs `scripts/ci/audit_vendored_assets.py`, which asks [OSV](https://osv.dev) about every package and version in `config/vendored_assets.json`. `npm audit` and `pip-audit` read lock files and never see the bundles under `apps/*/js/vendor/`, so this is the only audit that covers them. It matches `vendored_vulnerability_exceptions` by package name and by advisory ID or alias, and it rejects expired or unused exceptions. It follows OSV page tokens and retries a transient network error three times. It fails when OSV stays unreachable or returns data it cannot read, because a skipped query would look like a clean result. It prints how many package versions it checked.

For all three audits, a finding that has a fix invalidates a matching exception only when that exception sets `ignore_only_without_fix` to `true`. The flag defaults to `false`.

Gitleaks and GitHub dependency review run only in CI.

## Generated files and browser checks

- `make check-generated` reruns the stylesheet and index generators in restore-safe mode. It fails if `css/style.css`, the generated README markers, `js/data.js`, or `js/gallery-config.js` would drift from the tracked source inputs.
- `make test-browser` runs the Playwright suites against a site that the tests build with `scripts/build/prepare_site.py`. The suites cover the root gallery and the mature app pages. CI splits the app suites into shards with `ARTIFACTS_BROWSER_APP_MANIFEST`, which `make test-browser-apps-shard` sets. Locally, `ARTIFACTS_BROWSER_APP_SLUGS` narrows `make test-browser-apps` to specific slugs.
- Every `make test-browser*` target runs through `scripts/ci/run_browser_tests.py`. It retries a failed run once with `--last-failed`. A run that passes on retry exits 0 locally. It fails when `ARTIFACTS_FAIL_ON_FLAKY_BROWSER_TESTS=1`, which CI sets. Pass `ARGS="-k name"` to select tests.
- `make test-browser-live` verifies an already-published site in a real browser when `ARTIFACTS_LIVE_SITE_URL` is set. CI sets `ARTIFACTS_BROWSER_ARTIFACT_DIR` to capture failure screenshots, traces, and logs.

## Scheduled monitoring

Each monitoring workflow opens, updates, or closes one GitHub issue with a fixed title. [Maintenance](maintenance.md#preserve-alert-issue-identities) lists the workflows and titles, and [CI](ci.md#auxiliary-workflows) describes how each one runs.

- `.github/workflows/audit-repo-settings.yml` reports repository-settings drift and leaked `gh-pages` PR previews.
- `.github/workflows/dependency-audit.yml` reports failures of `make audit-python`, `make audit-node`, `make audit-vendored`, and `make check-overrides`.
- `.github/workflows/live-site-smoke.yml` reports failures of `make test-browser-live` against the published site.
- `.github/workflows/deploy-failure-alert.yml` reports failed main-branch runs of `update.yml`.
- `.github/workflows/schedule-watchdog.yml` runs on pushes to `main` and on manual dispatch. It finds YAML workflows that declare cron schedules and checks whether each one is enabled. It does not read run history, so an enabled workflow that stops firing is outside this check.

## Aggregate and scoped gates

- `make ci-fast` runs `format-check`, `lint`, `typecheck`, `test-py`, `coverage-js`, `dead-code`, `security`, and `validate` in parallel, then `make check-generated`. It omits `make coverage-js-floors`, which you can run afterward on the LCOV report that `make coverage-js` wrote.
- `make ci` is the full non-browser local gate. It runs formatting, linting, type checks, tests, coverage, per-file coverage floors, dead-code checks, dependency audits, validation, and the generated-file drift check. It skips the Playwright suites and thumbnail generation. `make check-local` is an alias.
- `make ci-quick-gates` and `make ci-heavy-checks` are the two parallel batches that CI runs as the `quick-gates` and `heavy-checks` jobs. `make ci-quick-gates` runs `format-check`, `lint`, `typecheck`, and `validate`. `make ci-heavy-checks` runs `test-py`, `coverage-js`, `dead-code`, and `security`.
- `make test-browser-root-smoke`, `make test-browser-root-accessibility`, and `make test-browser-root-flows` run the root gallery Playwright suites separately. `make test-browser-root` runs all three.
- `make test-browser-apps-smoke`, `make test-browser-apps-accessibility`, and `make test-browser-apps-flows` run the mature app Playwright suites separately. `make test-browser-apps` remains the aggregate app gate.
- `make test-browser-webkit-smoke` runs the WebKit cross-engine smoke pass over the root gallery and the mature apps.
- `make test-page-speed` opens the gallery and each mature app in Chromium as a first visit with an empty cache, from the assembled site. It times navigation to the runtime's ready mark. The median of five visits per page must stay under 500 ms. CI runs it in the `root-browser` job. [Operations](operations.md#page-speed-budget) explains the budget.
- `make check-web` is the browser-only gate. It runs `make test-browser` and `make thumbnails`.
- `make check` runs `make check-local`, `make check-web`, `make index`, and `make site`.
- `make validate` fails when a directory under `apps/` lacks `index.html` or `name.txt`, has an empty `name.txt`, or has a name that is not kebab-case.

Python coverage policy is configured in `pyproject.toml`. Aggregate JavaScript coverage thresholds and exclusions are configured in `package.json`. The per-file JavaScript coverage floors are constants in `scripts/lint/check-js-coverage-floors.mjs`.
