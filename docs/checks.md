# Quality checks

This reference describes the workspace's check targets and their configuration. [Operations](operations.md) gives the steps for local verification.

## Formatting and lint

The formatting and lint targets check these rules:

- `make editorconfig-check` enforces supported `.editorconfig` rules such as LF endings, final-newline policy, trailing whitespace trimming, and indentation style for covered repository files, while skipping configured cache/build/dependency directories and binary assets.
- `ruff` scans the repo root. Built-in exclusions skip dependency and cache directories, including `.venv/` and `node_modules/`. Config: `pyproject.toml`.
- `eslint` scans the repo root; file patterns and ignores are in `config/eslint.config.js`.
- `stylelint` scans all `**/*.css`; ignores are in `config/stylelint.config.js`.
- `yamllint` scans the repo root; ignores are in `.yamllint.yml`.
- Workflow linting runs through `scripts/lint/lint-workflows.mjs`, which wraps `actionlint` across `.github/workflows/*.yml` and `.github/workflows/*.yaml`.
- `make lint-doc-commands` checks contributor-facing docs for direct commands that should use Make targets instead.
- `make lint-make-targets` verifies that `make <target>` references in Markdown, `.github` shell blocks, and non-test Python or JavaScript source still exist in `Makefile`, and rejects unallowlisted raw shell control flow in recipes.
- `make lint-js-test-coverage` verifies that every JS or MJS source file under the tracked source roots is imported by at least one test file.
- `make lint-artifact-csp` checks the root `index.html` and every `apps/<slug>/index.html`. Each page needs a Content-Security-Policy meta tag in the document head, before any markup that can load a resource. The policy must limit `default-src` and `script-src` to `'self'` or `'none'`. It must also set `object-src 'none'`, which is stricter than the `'self'` that `default-src` would give it, and restrict `base-uri` and `form-action` to `'self'` or `'none'`, because those two do not fall back to `default-src`. The check fails when a directive appears twice, because browsers ignore every copy after the first. The check fails on external scripts, external stylesheets, and external `url()` resources. The root page may also load images from `https://img.shields.io` for its badges. Artifact pages may not.
- Browsers ignore `frame-ancestors` in a meta tag, and GitHub Pages cannot send response headers. Any page can therefore be framed by another site, and no lint can change that.
- `make lint-app-css-tokens` checks app CSS colors, radii, font sizes, and letter spacing against shared tokens. It fails if no stylesheets are found. [Style guide](style.md#token-lint) lists allowed values and exceptions.
- `make lint-vendored-assets` reconciles vendored bundles under `apps/*/js/vendor/` with the integrity manifest in `config/vendored_assets.json`, failing on unlisted files, missing files, or SHA-256 mismatches.
- `make check-overrides` reports whether npm `overrides` entries are still needed when that package field exists.
- `make format-check` verifies ruff formatting, Markdown table alignment, and Prettier-managed metadata, config, workflows, and tooling scripts without writing files.
## Types, tests, and unused code

These targets check source types, test results, coverage, and unused code:

- `make typecheck` runs mypy strict over `scripts/` and the web typecheck target from `config/jsconfig.json`.
- `make dead-code` runs vulture for Python and Knip for JavaScript files, exports, and dependency usage.
- `make test-py` enforces 100% line and branch coverage for the `scripts` package and treats warnings as errors.
- `make test-ci` runs the CI-focused Python tests under `tests/ci/`.
- `make test-ci-workflows` runs narrow contract tests against `.github/workflows/*.yml` so local and CI checks can catch workflow-structure drift early.
- `make test-js` covers the grouped Node suites under `tests/js/home/`, `tests/js/common/`, `tests/js/apps/`, `tests/js/tooling/`, and `tests/js/workflows/`.
- `make coverage-js` uses Node's built-in experimental coverage output and enforces the current baseline gate of 95% lines, 85% branches, and 95% functions across all source files imported by the grouped `tests/js/` suites. Coverage excludes `node_modules/` and `tests/`; thresholds and exclusions are configured in `package.json`.
- `make coverage-js-floors` checks per-file JS coverage floors using the LCOV output from `make coverage-js`. If the report is missing, it reruns coverage.

## Dependency audits

The dependency audit targets use the shared policy:

- `make security` runs `make audit-python`, `make audit-node`, and then `make audit-vendored`.
- `make audit-python` exports the frozen uv graph and checks it with pip-audit. It matches reviewed exceptions in `config/security_audit.json` by both package name and vulnerability ID or alias. Expired and unused exceptions fail the check.
- `make audit-node` checks npm advisories through `scripts/ci/run_npm_audit.py`. It matches `npm_vulnerability_exceptions` by both package name and advisory ID or alias and rejects expired or unused exceptions.
- `make audit-vendored` runs `scripts/ci/audit_vendored_assets.py`, which asks [OSV](https://osv.dev) about every package and version in `config/vendored_assets.json`. `npm audit` and `pip-audit` read lock files and never see the bundles under `apps/*/js/vendor/`, so this is the only audit that covers them. It matches `vendored_vulnerability_exceptions` by both package name and advisory ID or alias and rejects expired or unused exceptions. It fails when OSV is unreachable, because a skipped query would look the same as a clean result.

For all three audits, a matching finding with a fix invalidates an exception only when `ignore_only_without_fix` is `true`. The flag defaults to `false`. The current npm exception explicitly uses `false`.

Gitleaks and GitHub dependency review run only in CI. The repository does not install those scanners for local checks.

## Generated files and browser checks

These targets check generated output and browser behavior:

- `make check-generated` reruns the stylesheet and index generators in a restore-safe mode and fails if `css/style.css`, generated README markers, `js/data.js`, or `js/gallery-config.js` would drift from tracked source inputs.
- Playwright browser suites check both the built root gallery and mature app pages through `make test-browser`, while CI scopes mature app suites per shard with `ARTIFACTS_BROWSER_APP_MANIFEST` (set by `make test-browser-apps-shard`). Locally, `ARTIFACTS_BROWSER_APP_SLUGS` narrows `make test-browser-apps` to specific slugs.
- `make test-browser-live` verifies an already-published site in a real browser when `ARTIFACTS_LIVE_SITE_URL` is set, and CI captures failure screenshots, traces, and logs through `ARTIFACTS_BROWSER_ARTIFACT_DIR`.

## Scheduled monitoring

The monitoring workflows report failures through issues:

- Scheduled CI monitoring uses GitHub-native issue alerts: `.github/workflows/audit-repo-settings.yml` opens or closes a single repository-settings drift issue, and `.github/workflows/live-site-smoke.yml` opens or closes a single live-site smoke issue.
- `.github/workflows/schedule-watchdog.yml` runs on pushes to `main` and manual dispatch. It discovers YAML workflows declaring cron schedules and checks their enabled state. It does not query run history or infer failures from run age. An active workflow that stops firing is outside this check. Smoke tests keep their own failure and recovery alerts. The existing watchdog alert title is retained so healthy runs can close previously opened issues.

## Aggregate and scoped gates

These targets combine checks or select a narrower scope:

- `make ci-fast` runs parallel non-browser checks and then generated-file checks. It omits `make coverage-js-floors`, which can run afterward using the generated LCOV report.
- `make ci` is the full non-browser local gate without browser Playwright suites or thumbnail generation, and it includes formatting, linting, tests, coverage, dead-code checks, dependency audits, validation, and canonical generated-file drift checks. `make check-local` is an alias.
- `make test-browser-root-smoke`, `make test-browser-root-accessibility`, and `make test-browser-root-flows` let you run the root gallery Playwright suites separately.
- `make test-browser-apps-smoke`, `make test-browser-apps-accessibility`, and `make test-browser-apps-flows` let you run the mature app Playwright suites separately while preserving `make test-browser-apps` as the aggregate app gate.
- `make check-web` is the browser-only gate for the aggregate root and app browser suites and thumbnails.
- `make validate` fails if a top-level artifact directory is missing `index.html` or `name.txt`, has an empty `name.txt`, or uses a non-kebab-case directory name.
- Python coverage policy is configured in `pyproject.toml`. Aggregate JavaScript coverage thresholds and exclusions are configured in `package.json`. Per-file JavaScript coverage floors are defined in `scripts/lint/check-js-coverage-floors.mjs`.
