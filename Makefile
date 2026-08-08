.DEFAULT_GOAL := help

# ─── Variables ────────────────────────────────────────────────────────────────

# Prefer python3.12 (the CI-pinned version), then fall back to 3.13/3.14 or python3.
# Override by passing PYTHON=... on the command line or in the environment.
PYTHON      ?= $(shell command -v python3.12 || command -v python3.13 || command -v python3.14 || command -v python3)
UV          ?= uv
UVX         ?= uvx
VENV        ?= .venv
VENV_PYTHON := $(VENV)/bin/python
NPM         ?= npm

# Shared branch names. Override on the command line or in the environment.
MAIN_BRANCH  ?= main
PAGES_BRANCH ?= gh-pages

# Port for the local static preview server (make serve). Override with PORT=NNNN.
PORT        ?= 8000

# Python source tree that mypy strict-checks. Tests are intentionally excluded.
PY_TYPE_PATHS := scripts/

# Prefix Python commands with the repository root without discarding a
# PYTHONPATH the developer set for their own tooling.
PY_PATH_PREFIX = PYTHONPATH=.$${PYTHONPATH:+:$${PYTHONPATH}}

# Browser targets opt into the private Linux runtime only with local_libs=1.
# Browsers install into Playwright's shared cache so every project reuses one
# copy; only the extracted shared libraries and per-run scratch live below the
# ignored .playwright cache. The wrapper refuses to download packages mid-run.
PLAYWRIGHT_BROWSERS := chromium webkit
PLAYWRIGHT_ENGINE_ARGS = $(subst -, ,$(strip $(engines)))
PLAYWRIGHT_INVALID_ENGINES = $(filter-out $(PLAYWRIGHT_BROWSERS),$(PLAYWRIGHT_ENGINE_ARGS))
PLAYWRIGHT_LOCAL_RUNTIME := $(VENV_PYTHON) scripts/setup/playwright_local_runtime.py
PLAYWRIGHT_LOCAL_RUN = $(if $(filter 1,$(local_libs)),$(PLAYWRIGHT_LOCAL_RUNTIME) run --,)

# Entry point for tested GitHub PR/CI helpers. Keep Make targets as thin
# wrappers so GitHub behavior is testable Python instead of inline shell.
GH = $(PY_PATH_PREFIX) $(VENV_PYTHON) -m scripts.gh.cli

# ─── Free text ────────────────────────────────────────────────────────────────
#
# Bodies arrive on standard input. That keeps multiline prose, quotes,
# backticks, and shell-looking text out of make's parser and out of recipe
# source. A title, search term, or close comment is short text, so it arrives
# through the environment instead:
#
#     TITLE='Fix the retry loop' make issue-create < issue.md
#     SEARCH='is:open label:bug' make issue-list
#     COMMENT='Resolved in the latest deploy' make issue-close issue=7
#
# Make expands command-line assignments while parsing the file. Refuse those
# spellings for free text so callers use the safe environment or stdin forms.
NO_TTY_READ := [ -t 0 ] ||
FREE_TEXT_VARS := TITLE COMMENT SEARCH
$(foreach v,$(FREE_TEXT_VARS),$(if $(filter command line,$(origin $(v))),$(error \
$(v) was passed as a make argument, which make expands; use $(v)='...' make <target>)))

RETIRED_TEXT_ARGS := body title comment notes search detail \
body_file message message_file notes_file detail_file
$(foreach v,$(RETIRED_TEXT_ARGS),$(if $(filter command line,$(origin $(v))),$(error \
$(v)= is no longer an argument: body and other prose arrive on stdin, while a title, search term, or close comment comes from the environment)))

# Repository slug (owner/name) for the @ci and @pr groups. Resolve from the
# origin remote first, then fall back to gh. Kept in the shared Variables block
# because @ci targets consume it alongside the @pr group.
REPO ?= $(strip $(shell repo="$$(git remote get-url origin 2>/dev/null | sed -nE 's|.*github\.com[:/]([^/]+/[^/.]+)(\.git)?$$|\1|p')"; \
	if [ -z "$$repo" ]; then repo="$$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)"; fi; \
	printf '%s' "$$repo"))

# Fail with a usage line when a required variable is empty.
# Usage: $(call need,varname,make new name=my-artifact [src=file.html])
define need
@test -n "$($(1))" || { printf 'Usage: %s\n' '$(2)' >&2; exit 1; }
endef

# ─── Setup @setup ─────────────────────────────────────────────────────────────

.PHONY: install node-install install-hooks setup-base setup setup-all setup-ci ci-prune-uv-cache playwright-version setup-playwright setup-playwright-engines setup-playwright-ci setup-playwright-webkit setup-playwright-webkit-ci setup-playwright-local setup-playwright-webkit-local playwright-local-status playwright-local-gate playwright-local-clean

install: ## Install locked Python deps into the virtual environment
	UV_PROJECT_ENVIRONMENT=$(VENV) $(UV) sync --all-groups --frozen --python $(PYTHON)

node-install: ## Install locked Node deps
	$(NPM) ci

install-hooks: ## Install local pre-commit Git hooks
	$(UVX) pre-commit install

setup-base: install node-install ## Install Python and Node deps

setup: setup-base ## Install Python and Node deps (fast, no Chromium)

setup-all: setup-base setup-playwright ## Full setup including Chromium for browser tests

setup-ci: setup-base setup-playwright-ci ## CI variant with Chromium system deps

ci-prune-uv-cache: ## Remove uv cache entries that are inefficient to persist in CI
	$(UV) cache prune --ci

playwright-version: ## Print the installed Playwright package version
	@$(VENV_PYTHON) -c "import importlib.metadata; print(importlib.metadata.version('playwright'))"

setup-playwright: ## Install Chromium for browser tests
	$(VENV)/bin/playwright install chromium

setup-playwright-ci: ## Install Chromium with system deps
	$(VENV)/bin/playwright install chromium --with-deps

# Used by the ci-setup action, which keys its browser cache on the engine set so
# a restored entry always holds exactly the engines the job asked for. Engines
# arrive hyphen-separated (chromium-webkit) because the value is part of a cache
# key; no supported engine name contains a hyphen, so splitting on it is
# unambiguous. Validation below rejects malformed or unsupported values.
setup-playwright-engines: ## Install named Playwright engines (make setup-playwright-engines engines=chromium-webkit [with_deps=1])
	$(call need,engines,make setup-playwright-engines engines=chromium-webkit [with_deps=1])
	$(if $(filter-out 1,$(words $(strip $(engines)))),$(error engines must be one hyphen-separated value),)
	$(if $(filter -% %-,$(strip $(engines))),$(error engines must not start or end with a hyphen),)
	$(if $(findstring --,$(strip $(engines))),$(error engines must not contain empty names),)
	$(if $(PLAYWRIGHT_INVALID_ENGINES),$(error unsupported Playwright engine(s): $(PLAYWRIGHT_INVALID_ENGINES)),)
	$(if $(filter-out $(words $(sort $(PLAYWRIGHT_ENGINE_ARGS))),$(words $(PLAYWRIGHT_ENGINE_ARGS))),$(error engines must not contain duplicates),)
	$(if $(filter-out 0 1,$(words $(strip $(with_deps)))),$(error with_deps must be one value),)
	$(if $(filter-out 1,$(strip $(with_deps))),$(error with_deps must be 1 when provided),)
	$(VENV)/bin/playwright install $(if $(filter 1,$(with_deps)),--with-deps) $(filter $(PLAYWRIGHT_BROWSERS),$(PLAYWRIGHT_ENGINE_ARGS))

setup-playwright-webkit: ## Install WebKit for the cross-engine smoke pass
	$(VENV)/bin/playwright install webkit

setup-playwright-webkit-ci: ## Install WebKit with system deps
	$(VENV)/bin/playwright install webkit --with-deps

# The two local targets share one manifest. Preparing an engine extends the
# recorded engine set instead of replacing it, so the extracted package closure
# stays the union Chromium and WebKit both need and installing one engine never
# strands the other. Preparing again after the browser install patches the shared
# WebKit launcher so it appends the inherited library path.
setup-playwright-local: ## Install Chromium and the private Ubuntu/Debian runtime without sudo
	$(PLAYWRIGHT_LOCAL_RUNTIME) prepare --engine chromium
	PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 $(VENV)/bin/playwright install chromium
	$(PLAYWRIGHT_LOCAL_RUNTIME) prepare --engine chromium

setup-playwright-webkit-local: ## Install WebKit and extend the private runtime to its libraries
	$(PLAYWRIGHT_LOCAL_RUNTIME) prepare --engine webkit
	PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 $(VENV)/bin/playwright install webkit
	$(PLAYWRIGHT_LOCAL_RUNTIME) prepare --engine webkit

playwright-local-status: ## Show repository-local Playwright runtime status
	$(PLAYWRIGHT_LOCAL_RUNTIME) status

playwright-local-gate: ## Launch every prepared engine in the private runtime
	$(PLAYWRIGHT_LOCAL_RUNTIME) probe

playwright-local-clean: ## Remove only the repository-local Playwright cache (keeps shared browsers)
	$(PLAYWRIGHT_LOCAL_RUNTIME) clean

# ─── Lint @lint ───────────────────────────────────────────────────────────────

.PHONY: lint lint-py lint-js lint-css lint-yaml lint-workflows workflow-lint lint-doc-commands lint-make-targets lint-js-test-coverage lint-artifact-csp lint-app-css-tokens lint-vendored-assets editorconfig-check check-overrides

lint: editorconfig-check lint-py lint-js lint-css lint-yaml lint-workflows lint-doc-commands lint-make-targets lint-js-test-coverage lint-artifact-csp lint-app-css-tokens lint-vendored-assets check-overrides ## Run all linters

editorconfig-check: ## Check EditorConfig rules
	$(VENV_PYTHON) scripts/lint/check_editorconfig.py

lint-py: ## Run ruff only [paths=...]
	$(VENV_PYTHON) -m ruff check $(if $(paths),$(paths),.)

lint-js: ## Run eslint only
	$(NPM) run lint:js

lint-css: ## Run stylelint only
	$(NPM) run lint:css

lint-yaml: ## Run yamllint only [paths=...]
	$(VENV)/bin/yamllint $(if $(paths),$(paths),.)

lint-workflows: ## Run workflow linter only
	$(NPM) run lint:workflows

workflow-lint: lint-workflows ## Alias for lint-workflows

lint-doc-commands: ## Check contributor docs use Make targets
	$(VENV_PYTHON) scripts/lint/check_doc_commands.py

lint-make-targets: ## Check documented Make targets
	$(VENV_PYTHON) scripts/lint/check_make_targets.py

lint-js-test-coverage: ## Check every JS source file has test imports
	$(VENV_PYTHON) scripts/lint/check_js_test_coverage.py

lint-artifact-csp: ## Check artifact pages ship a strict CSP and no external refs
	$(VENV_PYTHON) scripts/lint/check_artifact_csp.py

lint-app-css-tokens: ## Check app stylesheets stay on shared design tokens
	$(VENV_PYTHON) scripts/lint/check_app_css_tokens.py

lint-vendored-assets: ## Check vendored libraries against the integrity manifest
	$(VENV_PYTHON) scripts/lint/check_vendored_assets.py

check-overrides: ## Check npm overrides are still needed
	$(NPM) run check:overrides

# ─── Format @format ───────────────────────────────────────────────────────────

.PHONY: fmt fmt-py fmt-js fmt-css fmt-prettier format format-check format-py-check format-py-diff format-prettier-check format-prettier-diff

fmt: fmt-py fmt-js fmt-css fmt-prettier ## Auto-fix all formatting and lint fixes

format: fmt ## Alias for fmt

fmt-py: ## Auto-fix Python (ruff check --fix + ruff format) [paths=...]
	$(VENV_PYTHON) -m ruff check --fix $(if $(paths),$(paths),.)
	$(VENV_PYTHON) -m ruff format $(if $(paths),$(paths),.)

fmt-js: ## Auto-fix JavaScript (eslint --fix)
	$(NPM) run lint:js -- --fix

fmt-css: ## Auto-fix CSS (stylelint --fix)
	$(NPM) run lint:css -- --fix

fmt-prettier: ## Auto-format metadata, workflows, and tooling scripts
	$(NPM) run format

format-check: format-py-check format-prettier-check align-tables-check ## Check Python, Prettier, and Markdown table formatting

format-py-check: ## Check Python formatting only [paths=...]
	$(VENV_PYTHON) -m ruff format --check $(if $(paths),$(paths),.)

format-py-diff: ## Show Python formatting changes without modifying files [paths=...]
	$(VENV_PYTHON) -m ruff format --check --diff $(if $(paths),$(paths),.)

format-prettier-check: ## Check Prettier-managed non-Markdown files only
	$(NPM) run format:check

format-prettier-diff: ## Show Prettier formatting changes without modifying files (make format-prettier-diff path=config/eslint.config.js)
	@test -n "$(path)" || (printf 'Usage: make format-prettier-diff path=config/eslint.config.js\n' >&2; exit 1)
	$(if $(filter %.md %.markdown,$(path)),$(error Markdown formatting is owned by make align-tables-check),)
	@set -e; \
	formatted=$$(mktemp "$${TMPDIR:-/tmp}/artifacts-prettier.XXXXXX"); \
	trap 'rm -f -- "$$formatted"' EXIT; \
	$(NPM) exec --no -- prettier --config config/prettierrc.json --ignore-path config/prettierignore \
		-- "$(path)" > "$$formatted"; \
	diff -u -- "$(path)" "$$formatted" || test $$? -eq 1

# ─── Typecheck @typecheck ────────────────────────────────────────────────────

.PHONY: typecheck typecheck-py typecheck-web

typecheck: typecheck-py typecheck-web ## Run all type checks

typecheck-py: ## Run mypy strict type checking over scripts/ [paths=...]
	$(VENV_PYTHON) -m mypy $(if $(paths),$(paths),$(PY_TYPE_PATHS))

typecheck-web: ## Run TypeScript checkJs over hand-written js/ modules
	$(NPM) run typecheck:web

# ─── Dead code @deadcode ──────────────────────────────────────────────────────

.PHONY: dead-code dead-code-py dead-code-js

dead-code: dead-code-py dead-code-js ## Detect unused Python and JavaScript code

dead-code-py: ## Detect unused Python code with vulture [paths=...]
	$(VENV_PYTHON) -m vulture $(if $(paths),$(paths))

dead-code-js: ## Detect unused JavaScript files, exports, and dependencies
	$(NPM) run dead-code

# ─── Test @test ───────────────────────────────────────────────────────────────

.PHONY: test test-py test-ci test-ci-workflows test-js test-browser test-browser-root test-browser-root-smoke test-browser-root-accessibility test-browser-root-flows test-browser-apps test-browser-apps-smoke test-browser-apps-accessibility test-browser-apps-flows test-browser-apps-shard test-browser-webkit-smoke test-visual visual-baselines test-browser-live coverage-js coverage-js-floors

# Browser targets run through the tested retry-once helper so the flaky-report
# policy lives in scripts/ instead of inline shell. BROWSER_ARGS threads an
# optional ARGS= tail (e.g. -k filters), honored only when passed on the make
# command line so a stray ARGS environment variable cannot change the gate.
RUN_BROWSER_TESTS = $(PLAYWRIGHT_LOCAL_RUN) $(VENV_PYTHON) -m scripts.ci.run_browser_tests
BROWSER_ARGS = $(if $(filter command line,$(origin ARGS)),$(ARGS))

test: test-py test-js ## Run non-browser Python tests + JS tests

# Honor ARGS only when given on the make command line, so a stray ARGS
# environment variable cannot silently change what the test gate runs.
test-py: ## Run Python tests only (with coverage, pass ARGS="-k name --no-cov" for a subset)
	$(VENV_PYTHON) -m pytest --ignore=tests/browser $(if $(filter command line,$(origin ARGS)),$(ARGS))

test-ci: ## Run CI Python tests only
	$(VENV_PYTHON) -m pytest --no-cov tests/ci

test-ci-workflows: ## Run GitHub workflow contract tests only
	$(VENV_PYTHON) -m pytest --no-cov tests/ci/test_workflow_contracts.py

test-js: ## Run JS tests only (pass ARGS="--test-name-pattern name" for a subset)
	$(NPM) run test -- $(if $(filter command line,$(origin ARGS)),$(ARGS))

test-browser: test-browser-root test-browser-apps ## Run all browser tests (needs Chromium)

test-browser-root: test-browser-root-smoke test-browser-root-accessibility test-browser-root-flows ## Run all root gallery browser tests

test-browser-root-smoke: ## Run root gallery smoke browser tests (pass ARGS="-k name" for a subset)
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_smoke.py $(BROWSER_ARGS)

test-browser-root-accessibility: ## Run root gallery accessibility browser tests (pass ARGS="-k name" for a subset)
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_accessibility.py $(BROWSER_ARGS)

test-browser-root-flows: ## Run root gallery browser-flow tests (pass ARGS="-k name" for a subset)
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_browser_flows.py $(BROWSER_ARGS)

test-browser-apps: ## Run all mature app browser tests in one shared test process (pass ARGS="-k name")
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_apps_smoke.py tests/browser/test_frontend_apps_accessibility.py tests/browser/test_frontend_apps_browser_flows.py $(BROWSER_ARGS)

test-browser-apps-smoke: ## Run mature app smoke browser tests (pass ARGS="-k name" for a subset)
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_apps_smoke.py $(BROWSER_ARGS)

test-browser-apps-accessibility: ## Run mature app accessibility browser tests (pass ARGS="-k name" for a subset)
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_apps_accessibility.py $(BROWSER_ARGS)

test-browser-apps-flows: ## Run mature app browser-flow tests (pass ARGS="-k name" for a subset)
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_apps_browser_flows.py $(BROWSER_ARGS)

test-browser-apps-shard: ## Run one app-browser shard (make test-browser-apps-shard shard_manifest=PATH [ARGS="-k name"])
	$(call need,shard_manifest,make test-browser-apps-shard shard_manifest=.artifacts/shard-manifest.json)
	$(RUN_BROWSER_TESTS) --env ARTIFACTS_BROWSER_APP_MANIFEST="$(shard_manifest)" tests/browser/test_frontend_apps_smoke.py tests/browser/test_frontend_apps_accessibility.py tests/browser/test_frontend_apps_browser_flows.py $(BROWSER_ARGS)

test-browser-webkit-smoke: ## Run the WebKit cross-engine smoke pass (root + apps, needs WebKit) (pass ARGS="-k name")
	$(RUN_BROWSER_TESTS) --env ARTIFACTS_BROWSER_ENGINE=webkit tests/browser/test_frontend_webkit_smoke.py $(BROWSER_ARGS)

test-visual: ## Compare hero screenshots against committed baselines (needs Chromium) (pass ARGS="-k name")
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_visual.py $(BROWSER_ARGS)

visual-baselines: ## Regenerate committed hero screenshot baselines (needs Chromium)
	ARTIFACTS_UPDATE_VISUAL_BASELINES=1 ARTIFACTS_REQUIRE_BROWSER_TESTS=1 $(PLAYWRIGHT_LOCAL_RUN) $(VENV_PYTHON) -m pytest --no-cov tests/browser/test_frontend_visual.py

test-browser-live: ## Run live-site browser verification (pass ARGS="-k name" for a subset)
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_live.py $(BROWSER_ARGS)

coverage-js: ## Run JS tests with coverage enforcement (emits .artifacts/js-coverage.lcov) [COVERAGE_OUTPUT=path]
	@mkdir -p .artifacts
	@if [ -n "$(COVERAGE_OUTPUT)" ]; then \
		bash -o pipefail -c '$(NPM) run test:coverage | tee "$(COVERAGE_OUTPUT)"'; \
	else \
		$(NPM) run test:coverage; \
	fi

coverage-js-floors: ## Enforce per-file JS coverage floors (reads the coverage-js lcov, else reruns the suite)
	$(NPM) run coverage:files

# ─── Build @build ─────────────────────────────────────────────────────────────

.PHONY: validate thumbnails thumbnails-shard styles index site serve generate new optimize-social-image

validate: ## Check artifact directories are complete
	$(VENV_PYTHON) -c "from scripts.build.generate_index import validate; validate()"

thumbnails: ## Regenerate WebP thumbnails (needs Chromium) (make thumbnails [slug=a,b])
	ARTIFACTS_THUMBNAIL_SLUGS="$(slug)" $(PLAYWRIGHT_LOCAL_RUN) $(VENV_PYTHON) scripts/build/generate_thumbnails.py

thumbnails-shard: ## Generate thumbnails from one shard manifest (make thumbnails-shard shard_manifest=PATH)
	$(call need,shard_manifest,make thumbnails-shard shard_manifest=.artifacts/shard-manifest.json)
	$(VENV_PYTHON) scripts/ci/app_shards.py invalidate-thumbnails --manifest "$(shard_manifest)"
	ARTIFACTS_THUMBNAIL_SHARD_MANIFEST="$(shard_manifest)" $(PLAYWRIGHT_LOCAL_RUN) $(VENV_PYTHON) scripts/build/generate_thumbnails.py

styles: ## Rebuild css/style.css from ordered source partials
	$(VENV_PYTHON) scripts/build/generate_styles.py

index: ## Rebuild js/data.js, js/gallery-config.js, README
	$(VENV_PYTHON) scripts/build/generate_index.py

site: styles ## Assemble _site/ deploy payload
	$(VENV_PYTHON) scripts/build/prepare_site.py

serve: index site ## Build the packaged site and serve it locally (make serve [PORT=8000])
	@printf '\n  Serving _site/ at \033[1mhttp://localhost:%s/\033[0m  (Ctrl-C to stop)\n\n' "$(PORT)"
	$(PYTHON) -m http.server $(PORT) --directory _site --bind 127.0.0.1

generate: styles thumbnails index ## Rebuild all canonical generated assets

new: ## Scaffold a new artifact directory (make new name=X [src=file.html])
	$(call need,name,make new name=my-artifact [src=file.html])
	$(VENV_PYTHON) scripts/build/scaffold_artifact.py "$(name)" $(if $(src),--from-html "$(src)")

optimize-social-image: ## Recompress the Open Graph share image in place (make optimize-social-image [path=FILE])
	$(VENV_PYTHON) scripts/build/optimize_social_image.py $(if $(path),"$(path)")

# ─── Quality gates @quality ───────────────────────────────────────────────────

.PHONY: ci-python ci-web ci ci-fast security audit-python audit-node audit-fix-node check-generated check-local check-fast check-web check fix

ci-python: format-py-check lint-py typecheck-py dead-code-py test-py ## Python CI gate

ci-web: editorconfig-check format-prettier-check lint-js lint-css lint-yaml typecheck-web lint-workflows lint-doc-commands lint-make-targets lint-js-test-coverage lint-artifact-csp lint-app-css-tokens lint-vendored-assets check-overrides dead-code-js test-js coverage-js coverage-js-floors ## Web and docs CI gate

ci: ci-python ci-web security validate check-generated ## Full local CI gate without browser tests

# check-generated runs after the parallel batch because it rewrites and
# restores generated files in place, which would race concurrent readers.
ci-fast: ## Run the non-browser CI checks in parallel
	$(VENV_PYTHON) scripts/ci/run_parallel_checks.py format-check lint typecheck test-py coverage-js dead-code security validate
	@$(MAKE) --no-print-directory check-generated

security: audit-python audit-node ## Run dependency audits

audit-python: ## Export locked Python deps and run pip-audit
	mkdir -p .artifacts
	$(UV) export --all-groups --frozen --no-emit-project --format requirements.txt --output-file .artifacts/requirements-audit.txt
	$(VENV_PYTHON) scripts/ci/run_security_audit.py \
		--requirements .artifacts/requirements-audit.txt \
		--pip-audit "$(VENV_PYTHON) -m pip_audit"

audit-node: ## Run policy-driven npm dependency audit with reviewed exceptions
	$(VENV_PYTHON) scripts/ci/run_npm_audit.py --npm "$(NPM)"

audit-fix-node: ## Apply available npm audit fixes to package-lock.json
	$(NPM) audit fix --package-lock-only

check-generated: ## Check canonical generated files are up to date
	$(VENV_PYTHON) scripts/lint/check_generated_drift.py

check-local: ci ## Alias for the full local CI gate

check-fast: ci-fast ## Alias for ci-fast

check-web: test-browser thumbnails ## Browser gate: test-browser + thumbnails

check: check-local check-web index site ## Full gate: check-local + check-web + index + site

fix: fmt check-local ## Auto-fix formatting, then run the full non-browser local gate

# ─── Utilities @util ──────────────────────────────────────────────────────────

.PHONY: lock lock-node lock-node-update refresh-ci-pins fix-deps align-tables align-tables-check status clean help help-json

lock: ## Refresh uv.lock after Python dependency changes
	$(UV) lock

lock-node: ## Refresh package-lock.json after Node dependency changes
	$(NPM) install --package-lock-only

lock-node-update: ## Update selected Node packages in the lockfile (packages="package ...")
	$(call need,packages,make lock-node-update packages="package ...")
	$(NPM) update --package-lock-only $(foreach pkg,$(packages),"$(pkg)")

refresh-ci-pins: ## Refresh the Playwright package, uv lock, and pinned CI image
	$(PYTHON) scripts/ci/refresh_ci_pins.py upgrade-project
	$(MAKE) lock
	$(PYTHON) scripts/ci/refresh_ci_pins.py refresh-image

fix-deps: ## Refresh locks, reinstall, and npm audit fix
	$(MAKE) lock
	$(MAKE) lock-node
	$(MAKE) install
	$(MAKE) node-install
	$(MAKE) audit-fix-node

align-tables: ## Align markdown table pipes across all docs [paths="README.md docs/example.md"]
	$(VENV_PYTHON) scripts/lint/align_tables.py $(if $(paths),$(paths))

align-tables-check: ## Check markdown table pipe alignment without modifying files [paths="README.md docs/example.md"]
	$(VENV_PYTHON) scripts/lint/align_tables.py --check $(if $(paths),$(paths))

status: ## Show workspace health (git, venv, node, generated files, PR)
	@$(PY_PATH_PREFIX) $(PYTHON) -m scripts.lib.workspace_status --venv-python "$(VENV_PYTHON)" --uv "$(UV)" --npm "$(NPM)"

# Only repository-local state is removable here. Playwright's browsers live in
# the shared ~/.cache/ms-playwright cache that every project on the machine
# reuses, so this target must never grow a path that reaches outside the repo.
# Every other path below is a fixed repository-relative literal, so VENV is the
# one way this rm -rf can be aimed elsewhere. It is ?=, and make imports the
# environment, so an unrelated exported VENV would silently redirect it. Make
# functions split on whitespace, so a VENV holding spaces would expand into
# several paths that each pass a containment filter and each get deleted. Keep
# the value only when VENV is a single word that resolves under CURDIR, and let
# the recipe refuse the empty result rather than delete a shorter path. The
# expansion is quoted in the recipe too, while the fixed literals stay unquoted
# so *.egg-info still globs.
CLEAN_VENV = $(if $(filter 1,$(words $(VENV))),$(filter $(CURDIR)/%,$(abspath $(VENV))))

clean: ## Remove local environments, build outputs, and caches (keeps shared Playwright browsers)
	@test -n "$(CLEAN_VENV)" || { \
		printf 'Refusing to clean: VENV=%s is not a single path under %s\n' "$(VENV)" "$(CURDIR)" >&2; \
		exit 1; \
	}
	rm -rf "$(CLEAN_VENV)" node_modules _site .artifacts .playwright .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov coverage playwright-report test-results build dist *.egg-info

help: ## Show command groups (expand one with make help-<group>)
	@printf '\n  \033[1mmake <target>\033[0m   ·   expand a group: \033[1mmake help-<group>\033[0m   ·   machine-readable: \033[1mmake help-json\033[0m\n'
	@printf '\n  \033[1mGroups\033[0m\n'
	@awk ' \
		/^# ─── .*@/ { \
			line = $$0; sub(/^# ─── /, "", line); \
			ti = index(line, " @"); \
			if (ti == 0) next; \
			title = substr(line, 1, ti - 1); \
			rest = substr(line, ti + 2); sp = index(rest, " "); \
			slug = (sp ? substr(rest, 1, sp - 1) : rest); \
			printf "    %-12s %s\n", slug, title; \
		}' $(MAKEFILE_LIST)
	@printf '\n'

help-%: FORCE ## List the commands in one group (e.g. make help-pr)
	@awk -v want="$*" ' \
		/^# ─── / { \
			line = $$0; sub(/^# ─── /, "", line); ti = index(line, " @"); \
			if (ti > 0) { rest = substr(line, ti + 2); sp = index(rest, " "); \
				slug = (sp ? substr(rest, 1, sp - 1) : rest); title = substr(line, 1, ti - 1); } \
			else { slug = ""; title = line; sub(/ *─+$$/, "", title); } \
			inwant = (slug != "" && slug == want); \
			if (inwant) printf "\n  \033[1m%s\033[0m\n", title; \
			next; \
		} \
		inwant && /^[a-zA-Z0-9_-]+:.*## / { \
			target = $$1; sub(/:.*/, "", target); \
			desc = $$0; sub(/.*## /, "", desc); \
			printf "    %-22s %s\n", target, desc; \
		}' $(MAKEFILE_LIST)
	@printf '\n'

# .PHONY cannot cover pattern rules, so help-% depends on FORCE to stay
# runnable even if a file named help-<group> ever appears in the workspace.
FORCE:

help-json: ## Emit groups and commands as JSON
	@awk ' \
		BEGIN { printf "{\"groups\":["; ng = 0; nc = 0; cmds = ""; slug = "" } \
		/^# ─── / { \
			line = $$0; sub(/^# ─── /, "", line); ti = index(line, " @"); \
			if (ti == 0) { slug = ""; next; } \
			rest = substr(line, ti + 2); sp = index(rest, " "); \
			slug = (sp ? substr(rest, 1, sp - 1) : rest); title = substr(line, 1, ti - 1); \
			gsub(/"/, "\\\"", title); \
			printf "%s{\"slug\":\"%s\",\"title\":\"%s\"}", (ng++ ? "," : ""), slug, title; \
			next; \
		} \
		/^[a-zA-Z0-9_-]+:.*## / { \
			if (slug == "") next; \
			target = $$1; sub(/:.*/, "", target); \
			desc = $$0; sub(/.*## /, "", desc); gsub(/"/, "\\\"", desc); \
			cmds = cmds (nc++ ? "," : "") "{\"name\":\"" target "\",\"group\":\"" slug "\",\"desc\":\"" desc "\"}"; \
		} \
		END { printf "],\"commands\":[%s]}\n", cmds }' $(MAKEFILE_LIST)

# ─── Git @git ─────────────────────────────────────────────────────────────────

.PHONY: git branch branch-current branch-prune rebase-main rebase-continue sync-branch stage stage-all commit push push-force log log-file diff diff-staged

git: ## Git commands (make git)
	@$(MAKE) --no-print-directory help-git

branch: ## Create and switch to a new branch off main, or off base for a stacked branch (make branch name=X [base=branch])
	$(call need,name,make branch name=my-feature [base=other-branch])
	git checkout "$(if $(base),$(base),$(MAIN_BRANCH))" && \
	{ ! git rev-parse --symbolic-full-name --abbrev-ref '@{u}' >/dev/null 2>&1 || git pull; } && \
	git checkout -b "$(name)"

branch-current: ## Create and switch to a branch from the current commit without pulling (make branch-current name=X)
	$(call need,name,make branch-current name=my-feature)
	git checkout -b "$(name)"

branch-prune: export PRUNE_MAIN_BRANCH := $(MAIN_BRANCH)
branch-prune: export PRUNE_PAGES_BRANCH := $(PAGES_BRANCH)
branch-prune: export PRUNE_CONFIRM := $(confirm)
branch-prune: ## Prune local branches whose content is already in main (make branch-prune [confirm=1])
	@$(PY_PATH_PREFIX) $(PYTHON) -m scripts.lib.prune_branches

rebase-main: ## Rebase the current branch onto origin/main (make rebase-main [base=branch])
	git fetch origin "$(if $(base),$(base),$(MAIN_BRANCH))" && git rebase "origin/$(if $(base),$(base),$(MAIN_BRANCH))"

rebase-continue: ## Continue an in-progress rebase after resolving conflicts
	GIT_EDITOR=true git rebase --continue

sync-branch: ## Rebase the current branch onto its upstream branch
	git pull --rebase

stage: export STAGE_FILES := $(value files)
stage: export STAGE_FILE := $(value file)
stage: ## Stage selected files (make stage [files="path ..."] [file="path with spaces"])
	@$(PY_PATH_PREFIX) $(PYTHON) -m scripts.lib.stage_files

stage-all: ## Stage all workspace changes
	git add -A

commit: ## Commit staged changes, message on stdin (make commit < msg.txt, or a heredoc [amend=1])
	@set -e; \
	if [ -t 0 ]; then \
		printf 'Commit message must be provided on stdin. Usage: make commit < msg.txt, or a heredoc\n' >&2; \
		exit 1; \
	fi; \
	tmp=$$(mktemp "$${TMPDIR:-/tmp}/artifacts-commit-message.XXXXXX"); \
	chmod 600 "$$tmp"; \
	trap 'rm -f -- "$$tmp"' EXIT; \
	cat > "$$tmp"; \
	test -s "$$tmp" || { printf 'Empty commit message. Usage: make commit < msg.txt, or a heredoc\n' >&2; exit 1; }; \
	$(GH) check-commit-message --message-file "$$tmp"; \
	git commit $(if $(amend),--amend) -F "$$tmp"

push: ## Push the current branch to origin
	git push -u origin HEAD

push-force: ## Push the current branch to origin after a rebase (uses --force-with-lease)
	git push --force-with-lease -u origin HEAD

log: ## Show recent commit log (make log [limit=N])
	git log --oneline -$(if $(limit),$(limit),20)

log-file: ## Show recent commit log for one file (make log-file path=FILE [limit=N])
	$(call need,path,make log-file path=.github/workflows/update.yml [limit=N])
	git log --date=short --pretty=format:'%h %ad %s' -$(if $(limit),$(limit),20) -- "$(path)"

diff: ## Show unstaged changes (make diff [path=FILE])
	git diff $(if $(path),-- "$(path)")

diff-staged: ## Show staged changes (make diff-staged [path=FILE])
	git diff --cached $(if $(path),-- "$(path)")

# ─── Pull requests @pr ────────────────────────────────────────────────────────

PR_NUM = $(if $(pr_num),$(pr_num),$(strip $(shell gh pr view --json number -q .number 2>/dev/null)))

# Smart default for CI-run targets: the caller's run= else the latest run on the
# current branch, resolved through the tested gh helper (same source as
# ci-failures). Stays empty when nothing can be resolved so the guard can fire.
RUN_ID = $(if $(run),$(run),$(strip $(shell $(GH) latest-run-id 2>/dev/null)))

.PHONY: pr pr-create pr-edit pr-list pr-status pr-checks pr-diff pr-checkout pr-comments pr-comment pr-review-comments pr-reply pr-resolve pr-address pr-copilot-review pr-comments-list pr-comment-delete pr-summary pr-watch pr-merge pr-merge-admin pr-reviewers pr-label pr-close

pr: ## PR commands (make pr)
	@$(MAKE) --no-print-directory help-pr

pr-create: ## Open a pull request (make pr-create [base=branch]; TITLE='...' make pr-create < body.md for an explicit one)
	@if [ -z "$$TITLE" ]; then \
		gh pr create --fill $(if $(base),--base "$(base)"); \
	else \
		gh pr create $(if $(base),--base "$(base)") --title "$$TITLE" --body-file -; \
	fi

pr-edit: ## Edit the current PR (TITLE='...' make pr-edit; new body on stdin: make pr-edit < body.md) [pr_num=N]
	@set -e; \
	body=""; $(NO_TTY_READ) body=$$(cat); \
	test -n "$$TITLE$$body" || \
		{ printf "Usage: TITLE='New title' make pr-edit, or make pr-edit < body.md [pr_num=N]\n" >&2; exit 1; }; \
	set -- $(if $(PR_NUM),--pr "$(PR_NUM)"); \
	if [ -n "$$TITLE" ]; then set -- "$$@" --title "$$TITLE"; fi; \
	if [ -n "$$body" ]; then \
		printf '%s' "$$body" | $(GH) edit-pr "$$@" --body-file -; \
	else \
		$(GH) edit-pr "$$@"; \
	fi

pr-list: ## List open pull requests
	gh pr list

pr-status: ## Show a PR's status and CI checks (make pr-status [pr_num=N])
	gh pr checks $(pr_num)

pr-checks: ## Watch CI checks until done (make pr-checks [pr_num=N])
	gh pr checks $(pr_num) --watch --fail-fast || true

pr-diff: ## Show the diff for the current PR (make pr-diff [pr_num=N])
	gh pr diff $(pr_num)

pr-checkout: ## Check out a PR's branch locally (make pr-checkout pr_num=N)
	$(call need,pr_num,make pr-checkout pr_num=123)
	gh pr checkout $(pr_num)

pr-comments: ## Show all comments on a PR (make pr-comments [pr_num=N])
	gh pr view $(pr_num) --comments

pr-comment: ## Add a comment to a PR, body on stdin (make pr-comment < notes.md) [pr_num=N]
	@$(GH) comment $(if $(pr_num),--pr "$(pr_num)") --body-file -

pr-review-comments: ## List review threads with thread ids (make pr-review-comments [pr_num=N] [show=all])
	@$(GH) list $(if $(pr_num),--pr $(pr_num)) $(if $(filter all,$(show)),--all)

pr-reply: ## Reply to a review thread, body on stdin (make pr-reply thread=PRRT_... < notes.md)
	$(call need,thread,make pr-reply thread=PRRT_... < notes.md)
	@$(GH) reply --thread "$(thread)" --body-file -

pr-resolve: ## Resolve a review thread (make pr-resolve thread=PRRT_...)
	$(call need,thread,make pr-resolve thread=PRRT_...)
	@$(GH) resolve --thread "$(thread)"

pr-address: ## Reply to and resolve a review thread, body on stdin (make pr-address thread=PRRT_... < notes.md)
	$(call need,thread,make pr-address thread=PRRT_... < notes.md)
	@$(GH) address --thread "$(thread)" --body-file -

pr-copilot-review: ## Request a Copilot code review on the current PR (make pr-copilot-review [pr_num=N])
	@$(GH) copilot-review $(if $(pr_num),--pr $(pr_num))

pr-comments-list: ## List individual review comments with node ids (make pr-comments-list [pr_num=N])
	@$(GH) list-comments $(if $(pr_num),--pr $(pr_num))

pr-comment-delete: ## Delete a review comment by node id (make pr-comment-delete comment_id=PRRC_...)
	$(call need,comment_id,make pr-comment-delete comment_id=PRRC_...)
	@$(GH) delete-comment --comment "$(comment_id)"

pr-summary: ## One-screen PR overview: state, CI rollup, open threads (make pr-summary [pr_num=N])
	@$(GH) summary $(if $(pr_num),--pr $(pr_num))

pr-watch: ## Observe the Copilot review and checks (make pr-watch [pr_num=N] [request=1] [interval=S] [max_polls=K] [expected_checks=N] [checks_only=1])
	@$(GH) watch $(if $(pr_num),--pr "$(pr_num)") $(if $(filter 1,$(request)),--request-copilot) $(if $(interval),--interval "$(interval)") $(if $(max_polls),--max-polls "$(max_polls)") $(if $(expected_checks),--expected-checks "$(expected_checks)") $(if $(filter 1,$(checks_only)),--checks-only)

pr-merge: ## Merge a PR (squash, delete branch) (make pr-merge [pr_num=N])
	gh pr merge $(pr_num) --squash --delete-branch

pr-merge-admin: ## Force merge bypassing branch protection (admin) (make pr-merge-admin [pr_num=N])
	gh pr merge $(pr_num) --squash --delete-branch --admin

pr-reviewers: ## Add reviewers (make pr-reviewers users="user1,user2" [pr_num=N])
	$(call need,users,make pr-reviewers users="octocat")
	gh pr edit $(pr_num) --add-reviewer $(users)

pr-label: ## Add labels (make pr-label labels="bug" [pr_num=N])
	$(call need,labels,make pr-label labels="bug")
	gh pr edit $(pr_num) --add-label "$(labels)"

pr-close: ## Close a PR and delete branch (make pr-close [pr_num=N])
	gh pr close $(pr_num) --delete-branch

# ─── Issues @issue ────────────────────────────────────────────────────────────

.PHONY: issue issue-list issue-view issue-summary issue-create issue-comment issue-edit issue-label issue-unlabel issue-assign issue-unassign issue-close issue-reopen issue-develop

issue: ## Issue commands (make issue)
	@$(MAKE) --no-print-directory help-issue

issue-list: ## List issues (make issue-list [state=open|closed|all] [label=bug] [assignee=user OR mine=1] [author=user] [limit=N]; SEARCH='...' to filter)
	@test -z "$(and $(assignee),$(filter 1,$(mine)))" || { printf 'Use assignee=user or mine=1, not both.\n' >&2; exit 1; }
	@set -e; \
	set -- $(if $(state),--state "$(state)") $(if $(label),--label "$(label)") \
		$(if $(assignee),--assignee "$(assignee)") $(if $(filter 1,$(mine)),--assignee @me) \
		$(if $(author),--author "$(author)") $(if $(limit),--limit "$(limit)"); \
	if [ -n "$$SEARCH" ]; then set -- "$$@" --search "$$SEARCH"; fi; \
	gh issue list "$$@"

issue-view: ## Show an issue with its comments (make issue-view issue=N)
	$(call need,issue,make issue-view issue=123)
	gh issue view $(issue) --comments

issue-summary: ## One-screen issue overview: state, labels, assignees, recent comments (make issue-summary issue=N)
	$(call need,issue,make issue-summary issue=123)
	@$(GH) issue-summary --issue $(issue)

issue-create: ## Open an issue, body on stdin (TITLE='Fix X' make issue-create < issue.md [labels="a,b"] [assignee=@me])
	@test -n "$$TITLE" || \
		(printf "Usage: TITLE='Fix X' make issue-create < issue.md [labels=\"bug,ci\"] [assignee=@me]\n" >&2; exit 1)
	@gh issue create --title "$$TITLE" $(if $(labels),--label "$(labels)") \
		$(if $(assignee),--assignee "$(assignee)") --body-file -

issue-comment: ## Comment on an issue, body on stdin (make issue-comment issue=N < notes.md)
	$(call need,issue,make issue-comment issue=123 < notes.md)
	@gh issue comment "$(issue)" --body-file -

issue-edit: ## Edit an issue (TITLE='...' make issue-edit issue=N; new body on stdin: make issue-edit issue=N < body.md)
	$(call need,issue,make issue-edit issue=123 [TITLE='New title'] [< body.md])
	@set -e; \
	body=""; $(NO_TTY_READ) body=$$(cat); \
	test -n "$$TITLE$$body" || \
		{ printf "Nothing to change. Set TITLE='...' or pipe a new body in.\n" >&2; exit 1; }; \
	set -- "$(issue)"; \
	if [ -n "$$TITLE" ]; then set -- "$$@" --title "$$TITLE"; fi; \
	if [ -n "$$body" ]; then \
		printf '%s' "$$body" | gh issue edit "$$@" --body-file -; \
	else \
		gh issue edit "$$@"; \
	fi

issue-label: ## Add labels to an issue (make issue-label issue=N labels="bug,ci")
	$(call need,issue,make issue-label issue=123 labels="bug")
	$(call need,labels,make issue-label issue=123 labels="bug")
	gh issue edit $(issue) --add-label "$(labels)"

issue-unlabel: ## Remove labels from an issue (make issue-unlabel issue=N labels="bug,ci")
	$(call need,issue,make issue-unlabel issue=123 labels="bug")
	$(call need,labels,make issue-unlabel issue=123 labels="bug")
	gh issue edit $(issue) --remove-label "$(labels)"

issue-assign: ## Assign users to an issue (make issue-assign issue=N users="a,b" OR mine=1)
	$(call need,issue,make issue-assign issue=123 users="octocat" OR mine=1)
	@test -n "$(users)$(if $(filter 1,$(mine)),me)" || { printf 'Provide users="a,b" or mine=1.\n' >&2; exit 1; }
	gh issue edit $(issue) $(if $(filter 1,$(mine)),--add-assignee @me) $(if $(users),--add-assignee "$(users)")

issue-unassign: ## Remove assignees from an issue (make issue-unassign issue=N users="a,b" OR mine=1)
	$(call need,issue,make issue-unassign issue=123 users="octocat" OR mine=1)
	@test -n "$(users)$(if $(filter 1,$(mine)),me)" || { printf 'Provide users="a,b" or mine=1.\n' >&2; exit 1; }
	gh issue edit $(issue) $(if $(filter 1,$(mine)),--remove-assignee @me) $(if $(users),--remove-assignee "$(users)")

issue-close: ## Close an issue (make issue-close issue=N [reason=completed|"not planned"]; COMMENT='...' to say why)
	$(call need,issue,make issue-close issue=123)
	@set -e; \
	set -- "$(issue)" $(if $(reason),--reason "$(reason)"); \
	if [ -n "$$COMMENT" ]; then set -- "$$@" --comment "$$COMMENT"; fi; \
	gh issue close "$$@"

issue-reopen: ## Reopen a closed issue (make issue-reopen issue=N; COMMENT='...' to say why)
	$(call need,issue,make issue-reopen issue=123)
	@set -e; \
	set -- "$(issue)"; \
	if [ -n "$$COMMENT" ]; then set -- "$$@" --comment "$$COMMENT"; fi; \
	gh issue reopen "$$@"

issue-develop: ## Create and check out a branch linked to an issue (make issue-develop issue=N [base=branch] [name=branch])
	$(call need,issue,make issue-develop issue=123)
	gh issue develop $(issue) --checkout $(if $(base),--base "$(base)") $(if $(name),--name "$(name)")

# ─── CI @ci ───────────────────────────────────────────────────────────────────

.PHONY: ci-runs ci-pages-runs ci-run ci-rerun ci-dispatch ci-caches ci-cache-delete ci-run-log ci-job-log ci-watch ci-failures ci-platform-checks ci-quick-gates ci-heavy-checks ci-thumbnail-plan ci-plan-outputs ci-apply-app-ledger ci-update-app-ledger ci-write-shard-manifest ci-package-shard-result ci-merge-shard-results ci-coverage-summary ci-finalize-pages-dir ci-audit-repo-settings ci-audit-previews ci-schedule-watchdog ci-alert-issue refresh-action-shas

ci-runs: ## List recent CI workflow runs
	gh run list -L "$(if $(limit),$(limit),10)"

ci-pages-runs: ## List recent GitHub Pages deployment runs
	gh run list -L "$(if $(limit),$(limit),20)" --workflow pages-build-deployment --branch "$(if $(branch),$(branch),$(PAGES_BRANCH))"

ci-run: ## Show one CI workflow run (make ci-run [run=ID], defaults to this branch's latest)
	@run_id="$(RUN_ID)"; \
	test -n "$$run_id" || { printf 'Usage: make ci-run run=123456 (or run on a branch with a resolvable latest run)\n' >&2; exit 1; }; \
	gh run view "$$run_id"

ci-rerun: ## Re-run one CI workflow run (make ci-rerun [run=ID] [failed=1], defaults to this branch's latest)
	@run_id="$(RUN_ID)"; \
	test -n "$$run_id" || { printf 'Usage: make ci-rerun run=123456 (or run on a branch with a resolvable latest run)\n' >&2; exit 1; }; \
	gh run rerun "$$run_id" $(if $(filter 1,$(failed)),--failed)

# Prefer this over re-running a run whose jobs already uploaded an artifact:
# attempts share one artifact namespace, so replaying a failed publish leaves two
# artifacts of the same name and the deploy step refuses the ambiguity.
ci-dispatch: ## Start a fresh workflow run (make ci-dispatch workflow=update.yml [ref=branch] [inputs="key=value ..."])
	$(call need,workflow,make ci-dispatch workflow=update.yml [ref=branch] [inputs="key=value ..."])
	gh workflow run "$(workflow)" $(if $(ref),--ref "$(ref)") $(foreach kv,$(inputs),-f "$(kv)")

# Largest first, because the reason to look is almost always that something is
# being restored that no step reads.
ci-caches: ## List Actions caches, largest first (make ci-caches [limit=N] [key=prefix])
	gh cache list --limit "$(if $(limit),$(limit),30)" --sort size_in_bytes --order desc $(if $(key),--key "$(key)")

# gh takes an id or a key in the same positional slot, so one variable covers
# both. A key is not unique on its own: the same key exists once per ref, and gh
# resolves it against the current branch unless ref= names another one.
ci-cache-delete: ## Delete one Actions cache (make ci-cache-delete cache=ID_or_key [ref=refs/heads/BRANCH])
	$(call need,cache,make ci-cache-delete cache=1234 OR cache=my-cache-key [ref=refs/heads/main])
	gh cache delete "$(cache)" $(if $(ref),--ref "$(ref)")

ci-run-log: ## Show failed logs for one CI workflow run (make ci-run-log [run=ID], defaults to this branch's latest)
	@run_id="$(RUN_ID)"; \
	test -n "$$run_id" || { printf 'Usage: make ci-run-log run=123456 (or run on a branch with a resolvable latest run)\n' >&2; exit 1; }; \
	gh run view "$$run_id" --log-failed

ci-job-log: ## Show logs for one CI job (make ci-job-log run=ID job=ID)
	@test -n "$(run)" -a -n "$(job)" || (printf 'Usage: make ci-job-log run=123456 job=789\n' >&2; exit 1)
	gh run view "$(run)" --job "$(job)" --log

ci-watch: ## Watch one CI run until done (make ci-watch [run=ID], defaults to this branch's latest)
	@run_id="$(RUN_ID)"; \
	test -n "$$run_id" || { printf 'Usage: make ci-watch run=123456 (or run on a branch with a resolvable latest run)\n' >&2; exit 1; }; \
	gh run watch "$$run_id" --exit-status

ci-failures: ## Show failed-step logs for this branch's latest run (make ci-failures [run=ID])
	@$(GH) ci-failures $(if $(run),--run $(run))

# The workflow helpers below run on the system interpreter with the shared
# repository path prefix instead of $(VENV_PYTHON): the scheduled monitor workflows and the
# update.yml plan, publish, and cleanup jobs call them in contexts without a
# provisioned venv, and the coverage-summary and setup-failure alert paths must
# work even when dependency installation itself failed. The helpers and
# everything they import are stdlib-only. The monitor helpers read GH_TOKEN
# from the environment.
ci-platform-checks: ## Run fixed non-browser platform checks in parallel
	@$(MAKE) --no-print-directory ci-quick-gates
	@$(MAKE) --no-print-directory ci-heavy-checks

ci-quick-gates: ## Run fast formatting, lint, type, and artifact checks
	$(VENV_PYTHON) scripts/ci/run_parallel_checks.py --timeout 1200 \
		format-check lint typecheck validate

ci-heavy-checks: ## Run slow test, coverage, dead-code, and security checks
	$(VENV_PYTHON) scripts/ci/run_parallel_checks.py --timeout 1200 \
		test-py coverage-js dead-code security

ci-thumbnail-plan: ## Compute a git-diff app impact plan (event_name= base_sha= head_sha= [force_full=true])
	$(call need,event_name,make ci-thumbnail-plan event_name=push base_sha=SHA head_sha=SHA)
	@$(PY_PATH_PREFIX) $(PYTHON) scripts/ci/workflow_helpers.py thumbnail-plan \
		--event-name "$(event_name)" \
		--repo "$(repo)" \
		--pr-number "$(pr_number)" \
		--commit-sha "$(commit_sha)" \
		--base-sha "$(base_sha)" \
		--head-sha "$(head_sha)" \
		--head-repo-fork "$(if $(head_repo_fork),$(head_repo_fork),false)" \
		--pr-author "$(pr_author)" \
		--actor "$(actor)" \
		--app-bot-login "$(app_bot_login)" \
		--force-full "$(if $(force_full),$(force_full),false)"

ci-plan-outputs: ## Emit automation plan step outputs (reads PLAN_JSON from the environment)
	@$(PY_PATH_PREFIX) $(PYTHON) scripts/ci/workflow_helpers.py plan-outputs

ci-apply-app-ledger: ## Apply cached green app hashes to a persisted impact plan (plan=PATH ledger=PATH output=PATH)
	@test -n "$(plan)" -a -n "$(ledger)" -a -n "$(output)" || (printf 'Usage: make ci-apply-app-ledger plan=.artifacts/ci-plan/plan.json ledger=.artifacts/app-ledger/ledger.json output=.artifacts/ci-plan/memoized-plan.json\n' >&2; exit 1)
	@$(PY_PATH_PREFIX) $(PYTHON) scripts/ci/app_hashes.py apply-ledger --plan "$(plan)" --ledger "$(ledger)" --output "$(output)"

ci-update-app-ledger: ## Update a ledger from main-verified app hashes (plan=PATH ledger=PATH)
	@test -n "$(plan)" -a -n "$(ledger)" || (printf 'Usage: make ci-update-app-ledger plan=.artifacts/ci-plan/plan.json ledger=.artifacts/app-ledger/ledger.json\n' >&2; exit 1)
	@$(PY_PATH_PREFIX) $(PYTHON) scripts/ci/app_hashes.py update-ledger --plan "$(plan)" --ledger "$(ledger)"

ci-write-shard-manifest: ## Select one impact-plan shard (plan=PATH shard=N output=PATH)
	@test -n "$(plan)" -a -n "$(shard)" -a -n "$(output)" || (printf 'Usage: make ci-write-shard-manifest plan=.artifacts/ci-plan/plan.json shard=0 output=.artifacts/shard-manifest.json\n' >&2; exit 1)
	@$(PY_PATH_PREFIX) $(PYTHON) scripts/ci/app_shards.py write-manifest --plan "$(plan)" --shard "$(shard)" --output "$(output)"

ci-package-shard-result: ## Package one shard thumbnail result (manifest=PATH output=PATH)
	@test -n "$(manifest)" -a -n "$(output)" || (printf 'Usage: make ci-package-shard-result manifest=.artifacts/shard-manifest.json output=.artifacts/shard-result\n' >&2; exit 1)
	$(VENV_PYTHON) scripts/ci/app_shards.py package-result --manifest "$(manifest)" --output "$(output)"

ci-merge-shard-results: ## Merge downloaded shard thumbnails (root=PATH)
	$(call need,root,make ci-merge-shard-results root=.artifacts/shard-results)
	$(VENV_PYTHON) scripts/ci/app_shards.py merge-results --root "$(root)"

ci-coverage-summary: ## Summarize a JS coverage report (make ci-coverage-summary report=js-coverage.txt)
	$(call need,report,make ci-coverage-summary report=js-coverage.txt)
	@$(PY_PATH_PREFIX) $(PYTHON) scripts/ci/workflow_helpers.py coverage-summary --report "$(report)"

ci-finalize-pages-dir: ## Finalize a GitHub Pages payload directory (make ci-finalize-pages-dir root=DIR)
	$(call need,root,make ci-finalize-pages-dir root=.pages-publish)
	@$(PY_PATH_PREFIX) $(PYTHON) scripts/ci/workflow_helpers.py finalize-pages-dir --root "$(root)"

ci-audit-repo-settings: ## Audit GitHub repo settings drift (make ci-audit-repo-settings [repo=owner/name])
	@$(PY_PATH_PREFIX) $(PYTHON) scripts/ci/workflow_helpers.py audit-repo-settings \
		--repo "$(if $(repo),$(repo),$(REPO))" \
		--default-branch "$(if $(default_branch),$(default_branch),$(MAIN_BRANCH))" \
		--pages-branch "$(if $(pages_branch),$(pages_branch),$(PAGES_BRANCH))"

ci-audit-previews: ## Detect leaked gh-pages PR previews (make ci-audit-previews [repo=owner/name])
	@$(PY_PATH_PREFIX) $(PYTHON) scripts/ci/workflow_helpers.py audit-previews \
		--repo "$(if $(repo),$(repo),$(REPO))" \
		--pages-branch "$(if $(pages_branch),$(pages_branch),$(PAGES_BRANCH))"

ci-schedule-watchdog: ## Detect stale or auto-disabled scheduled workflows (make ci-schedule-watchdog [repo=owner/name])
	@$(PY_PATH_PREFIX) $(PYTHON) scripts/ci/schedule_watchdog.py \
		--repo "$(if $(repo),$(repo),$(REPO))"

ci-alert-issue: ## Sync a monitored alert issue, detail on stdin (TITLE='...' make ci-alert-issue run_url=URL state=open|close|setup-failure [labels="ops ci"] [repo=])
	@test -n "$$TITLE" -a -n "$(run_url)" -a -n "$(state)" || \
		(printf "Usage: TITLE='Alert title' make ci-alert-issue run_url=https://... state=open|close|setup-failure [labels=\"ops ci\"] [repo=owner/name] < detail.md\n" >&2; exit 1)
	@set -e; \
	set -- --repo "$(if $(repo),$(repo),$(REPO))" --title "$$TITLE" --run-url "$(run_url)" --state "$(state)" \
		$(foreach label,$(labels),--label "$(label)"); \
	$(NO_TTY_READ) set -- "$$@" --detail-file -; \
	$(PY_PATH_PREFIX) $(PYTHON) scripts/ci/workflow_helpers.py sync-alert-issue "$$@"

refresh-action-shas: ## Repin tag-based GitHub Actions refs to commit SHAs (needs GH_TOKEN)
	$(PY_PATH_PREFIX) $(PYTHON) -m scripts.ci.refresh_action_shas
