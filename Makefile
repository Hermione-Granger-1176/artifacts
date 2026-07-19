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

# Port for the local static preview server (make serve). Override with PORT=NNNN.
PORT        ?= 8000

# Python source tree that mypy strict-checks. Tests are intentionally excluded.
PY_TYPE_PATHS := scripts/

# Entry point for tested GitHub PR/CI helpers. Keep Make targets as thin
# wrappers so GitHub behavior is testable Python instead of inline shell.
GH = PYTHONPATH=. $(VENV_PYTHON) -m scripts.gh.cli

# The pinned Playwright ships no browser build for very new distros (e.g. Ubuntu
# 26.04 on WSL), so `playwright install` and browser launches abort. When the host
# is an Ubuntu release Playwright has no build for, fall back to a supported
# platform key; Playwright then downloads/uses its fallback build, which runs fine.
# Exported so every Playwright target (setup-all/ci, test-browser-*, thumbnails)
# inherits it. On a supported image (CI) this stays empty and nothing changes.
# Override or disable by setting PLAYWRIGHT_HOST_PLATFORM_OVERRIDE in the env.
PLAYWRIGHT_SUPPORTED_UBUNTU := 18.04 20.04 22.04 24.04
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE ?= $(shell \
	. /etc/os-release 2>/dev/null; \
	if [ "$$ID" = ubuntu ] && ! printf '%s' "$(PLAYWRIGHT_SUPPORTED_UBUNTU)" | grep -qw "$$VERSION_ID"; then \
		echo ubuntu22.04-x64; \
	fi)
ifneq ($(strip $(PLAYWRIGHT_HOST_PLATFORM_OVERRIDE)),)
export PLAYWRIGHT_HOST_PLATFORM_OVERRIDE
endif

# ─── Setup @setup ─────────────────────────────────────────────────────────────

.PHONY: install node-install install-hooks setup-base setup setup-all setup-ci setup-playwright setup-playwright-ci

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

setup-playwright: ## Install Chromium for browser tests
	$(VENV)/bin/playwright install chromium

setup-playwright-ci: ## Install Chromium with system deps
	$(VENV)/bin/playwright install chromium --with-deps

# ─── Lint @lint ───────────────────────────────────────────────────────────────

.PHONY: lint lint-py lint-js lint-css lint-yaml lint-workflows workflow-lint lint-doc-commands lint-make-targets lint-js-test-coverage lint-artifact-csp lint-app-css-tokens lint-vendored-assets editorconfig-check check-overrides

lint: editorconfig-check lint-py lint-js lint-css lint-yaml lint-workflows lint-doc-commands lint-make-targets lint-js-test-coverage lint-artifact-csp lint-app-css-tokens lint-vendored-assets check-overrides ## Run all linters

editorconfig-check: ## Check EditorConfig rules
	$(VENV_PYTHON) scripts/lint/check_editorconfig.py

lint-py: ## Run ruff only
	$(VENV_PYTHON) -m ruff check .

lint-js: ## Run eslint only
	$(NPM) run lint:js

lint-css: ## Run stylelint only
	$(NPM) run lint:css

lint-yaml: ## Run yamllint only
	$(VENV)/bin/yamllint .

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

.PHONY: fmt fmt-py fmt-js fmt-css fmt-prettier format format-check format-py-check format-py-diff format-prettier-check

fmt: fmt-py fmt-js fmt-css fmt-prettier ## Auto-fix all formatting and lint fixes

format: fmt ## Alias for fmt

fmt-py: ## Auto-fix Python (ruff check --fix + ruff format)
	$(VENV_PYTHON) -m ruff check --fix .
	$(VENV_PYTHON) -m ruff format .

fmt-js: ## Auto-fix JavaScript (eslint --fix)
	$(NPM) run lint:js -- --fix

fmt-css: ## Auto-fix CSS (stylelint --fix)
	$(NPM) run lint:css -- --fix

fmt-prettier: ## Auto-format docs, metadata, workflows, and tooling scripts
	$(NPM) run format

format-check: format-py-check format-prettier-check ## Check Python and Prettier formatting

format-py-check: ## Check Python formatting only
	$(VENV_PYTHON) -m ruff format --check .

format-py-diff: ## Show Python formatting changes without modifying files
	$(VENV_PYTHON) -m ruff format --check --diff .

format-prettier-check: ## Check Prettier-managed files only
	$(NPM) run format:check

# ─── Typecheck @typecheck ────────────────────────────────────────────────────

.PHONY: typecheck typecheck-py typecheck-web

typecheck: typecheck-py typecheck-web ## Run all type checks

typecheck-py: ## Run mypy strict type checking over scripts/
	$(VENV_PYTHON) -m mypy $(PY_TYPE_PATHS)

typecheck-web: ## Run TypeScript checkJs over hand-written js/ modules
	$(NPM) run typecheck:web

# ─── Dead code @deadcode ──────────────────────────────────────────────────────

.PHONY: dead-code dead-code-py dead-code-js

dead-code: dead-code-py dead-code-js ## Detect unused Python and JavaScript code

dead-code-py: ## Detect unused Python code with vulture
	$(VENV_PYTHON) -m vulture

dead-code-js: ## Detect unused JavaScript files, exports, and dependencies
	$(NPM) run dead-code

# ─── Test @test ───────────────────────────────────────────────────────────────

.PHONY: test test-py test-ci test-ci-workflows test-js test-browser test-browser-root test-browser-root-smoke test-browser-root-accessibility test-browser-root-flows test-browser-apps test-browser-apps-smoke test-browser-apps-accessibility test-browser-apps-flows test-browser-apps-shard test-browser-live coverage-js coverage-js-floors

define run_browser_pytest
	@set +e; \
	ARTIFACTS_REQUIRE_BROWSER_TESTS=1 $(1) $(VENV_PYTHON) -m pytest --no-cov $(2); \
	status=$$?; \
	if [ "$$status" -eq 0 ]; then exit 0; fi; \
	echo "::warning::Browser tests failed. Retrying only failed tests once."; \
	ARTIFACTS_REQUIRE_BROWSER_TESTS=1 $(1) $(VENV_PYTHON) -m pytest --no-cov --last-failed --last-failed-no-failures none $(2); \
	retry_status=$$?; \
	if [ "$$retry_status" -eq 0 ]; then \
		echo "::warning::FLAKY BROWSER TESTS: retry passed after an initial failure."; \
		if [ -n "$${GITHUB_STEP_SUMMARY:-}" ]; then \
			printf '## Flaky browser tests\n\nA retry passed after an initial failure.\n' >> "$$GITHUB_STEP_SUMMARY"; \
		fi; \
		exit 0; \
	fi; \
	exit "$$retry_status"
endef

test: test-py test-js ## Run non-browser Python tests + JS tests

# Honor ARGS only when given on the make command line, so a stray ARGS
# environment variable cannot silently change what the test gate runs.
test-py: ## Run Python tests only (with coverage, pass ARGS="-k name --no-cov" for a subset)
	$(VENV_PYTHON) -m pytest --ignore=tests/browser $(if $(filter command line,$(origin ARGS)),$(ARGS))

test-ci: ## Run CI Python tests only
	$(VENV_PYTHON) -m pytest --no-cov tests/ci

test-ci-workflows: ## Run GitHub workflow contract tests only
	$(VENV_PYTHON) -m pytest --no-cov tests/ci/test_workflow_contracts.py

test-js: ## Run JS tests only
	$(NPM) run test

test-browser: test-browser-root test-browser-apps ## Run all browser tests (needs Chromium)

test-browser-root: test-browser-root-smoke test-browser-root-accessibility test-browser-root-flows ## Run all root gallery browser tests

test-browser-root-smoke: ## Run root gallery smoke browser tests
	$(call run_browser_pytest,,tests/browser/test_frontend_smoke.py)

test-browser-root-accessibility: ## Run root gallery accessibility browser tests
	$(call run_browser_pytest,,tests/browser/test_frontend_accessibility.py)

test-browser-root-flows: ## Run root gallery browser-flow tests
	$(call run_browser_pytest,,tests/browser/test_frontend_browser_flows.py)

test-browser-apps: ## Run all mature app browser tests in one shared test process
	$(call run_browser_pytest,,tests/browser/test_frontend_apps_smoke.py tests/browser/test_frontend_apps_accessibility.py tests/browser/test_frontend_apps_browser_flows.py)

test-browser-apps-smoke: ## Run mature app smoke browser tests
	$(call run_browser_pytest,,tests/browser/test_frontend_apps_smoke.py)

test-browser-apps-accessibility: ## Run mature app accessibility browser tests
	$(call run_browser_pytest,,tests/browser/test_frontend_apps_accessibility.py)

test-browser-apps-flows: ## Run mature app browser-flow tests
	$(call run_browser_pytest,,tests/browser/test_frontend_apps_browser_flows.py)

test-browser-apps-shard: ## Run one app-browser shard (make test-browser-apps-shard shard_manifest=PATH)
	@test -n "$(shard_manifest)" || (printf 'Usage: make test-browser-apps-shard shard_manifest=.artifacts/shard-manifest.json\n' >&2; exit 1)
	$(call run_browser_pytest,ARTIFACTS_BROWSER_APP_MANIFEST="$(shard_manifest)",tests/browser/test_frontend_apps_smoke.py tests/browser/test_frontend_apps_accessibility.py tests/browser/test_frontend_apps_browser_flows.py)

test-browser-live: ## Run live-site browser verification
	$(call run_browser_pytest,,tests/browser/test_frontend_live.py)

coverage-js: ## Run JS tests with coverage enforcement (emits .artifacts/js-coverage.lcov)
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

thumbnails: ## Regenerate WebP thumbnails (needs Chromium)
	$(VENV_PYTHON) scripts/build/generate_thumbnails.py

thumbnails-shard: ## Generate thumbnails from one shard manifest (make thumbnails-shard shard_manifest=PATH)
	@test -n "$(shard_manifest)" || (printf 'Usage: make thumbnails-shard shard_manifest=.artifacts/shard-manifest.json\n' >&2; exit 1)
	$(VENV_PYTHON) scripts/ci/app_shards.py invalidate-thumbnails --manifest "$(shard_manifest)"
	ARTIFACTS_THUMBNAIL_SHARD_MANIFEST="$(shard_manifest)" $(VENV_PYTHON) scripts/build/generate_thumbnails.py

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
	@test -n "$(name)" || (printf 'Usage: make new name=my-artifact [src=file.html]\n' >&2; exit 1)
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
	$(VENV_PYTHON) scripts/ci/run_security_audit.py --requirements .artifacts/requirements-audit.txt

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

fix: fmt check-local ## Auto-fix formatting, then run the fast local gate

# ─── Utilities @util ──────────────────────────────────────────────────────────

.PHONY: lock lock-node fix-deps align-tables status clean help help-json

lock: ## Refresh uv.lock after Python dependency changes
	$(UV) lock

lock-node: ## Refresh package-lock.json after Node dependency changes
	$(NPM) install --package-lock-only

fix-deps: ## Refresh locks, reinstall, and npm audit fix
	$(MAKE) lock
	$(MAKE) lock-node
	$(MAKE) install
	$(MAKE) node-install
	$(MAKE) audit-fix-node

align-tables: ## Align markdown table pipes across all docs
	$(VENV_PYTHON) scripts/lint/align_tables.py

status: ## Show workspace health (git, venv, node, generated files, PR)
	@echo "=== Git ==="
	@git status -sb
	@echo
	@echo "=== Venv ==="
	@test -x $(VENV_PYTHON) && echo "OK: $(VENV_PYTHON) exists" || echo "MISSING: run make setup"
	@echo
	@echo "=== Node ==="
	@test -d node_modules && echo "OK: node_modules exists" || echo "MISSING: run make setup"
	@$(UV) lock --check >/dev/null 2>&1 && echo "OK: uv.lock is current" || echo "STALE: run make lock"
	@$(NPM) install --package-lock-only --ignore-scripts --dry-run >/dev/null 2>&1 && echo "OK: package-lock.json is current" || echo "STALE: run make lock-node"
	@echo
	@echo "=== Generated files ==="
	@test -f js/data.js && echo "OK: js/data.js" || echo "STALE: run make index"
	@test -f js/gallery-config.js && echo "OK: js/gallery-config.js" || echo "STALE: run make index"
	@test -d _site && echo "OK: _site/" || echo "NOT BUILT: run make site"
	@echo
	@echo "=== Pull request ==="
	@if [ -x "$(VENV_PYTHON)" ]; then $(GH) summary || true; else echo "SKIPPED: venv missing, run make setup"; fi

clean: ## Remove local environments, build outputs, and caches
	rm -rf $(VENV) node_modules _site .artifacts .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov coverage playwright-report test-results build dist *.egg-info

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

.PHONY: git branch branch-current rebase-main rebase-continue sync-branch stage stage-all commit push push-force log log-file diff diff-staged

git: ## Git commands (make git)
	@$(MAKE) --no-print-directory help-git

branch: ## Create and switch to a new branch off main, or off base for a stacked branch (make branch name=X [base=branch])
	@test -n "$(name)" || (printf 'Usage: make branch name=my-feature [base=other-branch]\n' >&2; exit 1)
	git checkout "$(if $(base),$(base),main)" && \
	if git rev-parse --symbolic-full-name --abbrev-ref '@{u}' >/dev/null 2>&1; then git pull; fi && \
	git checkout -b "$(name)"

branch-current: ## Create and switch to a branch from the current commit without pulling (make branch-current name=X)
	@test -n "$(name)" || (printf 'Usage: make branch-current name=my-feature\n' >&2; exit 1)
	git checkout -b "$(name)"

rebase-main: ## Rebase the current branch onto origin/main
	git fetch origin main && git rebase origin/main

rebase-continue: ## Continue an in-progress rebase after resolving conflicts
	GIT_EDITOR=true git rebase --continue

sync-branch: ## Rebase the current branch onto its upstream branch
	git pull --rebase

stage: ## Stage selected files (make stage files="path ...")
	@test -n "$(files)" || (printf 'Usage: make stage files="path ..."\n' >&2; exit 1)
	git add -- $(files)

stage-all: ## Stage all workspace changes
	git add -A

commit: ## Commit staged changes (make commit message="..." OR message_file=path, - reads stdin [amend=1])
	@test -n "$(message)$(message_file)" || (printf 'Usage: make commit message="Commit message" OR message_file=path (- reads the message from stdin, e.g. a heredoc)\n' >&2; exit 1)
	@if [ -n "$(message_file)" ]; then \
	  git commit $(if $(amend),--amend) -F "$(message_file)"; \
	else \
	  git commit $(if $(amend),--amend) -m "$(message)"; \
	fi

push: ## Push the current branch to origin
	git push -u origin HEAD

push-force: ## Push the current branch to origin after a rebase (uses --force-with-lease)
	git push --force-with-lease -u origin HEAD

log: ## Show recent commit log
	git log --oneline -20

log-file: ## Show recent commit log for one file (make log-file path=FILE)
	@test -n "$(path)" || (printf 'Usage: make log-file path=.github/workflows/update.yml\n' >&2; exit 1)
	git log --date=short --pretty=format:'%h %ad %s' -20 -- "$(path)"

diff: ## Show unstaged changes
	git diff

diff-staged: ## Show staged changes
	git diff --cached

# ─── Pull requests @pr ────────────────────────────────────────────────────────

REPO ?= $(strip $(shell repo="$$(git remote get-url origin 2>/dev/null | sed -nE 's|.*github\.com[:/]([^/]+/[^/.]+)(\.git)?$$|\1|p')"; \
	if [ -z "$$repo" ]; then repo="$$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)"; fi; \
	printf '%s' "$$repo"))
PR_NUM = $(if $(pr_num),$(pr_num),$(strip $(shell gh pr view --json number -q .number 2>/dev/null)))

.PHONY: pr pr-create pr-edit pr-list pr-status pr-checks pr-diff pr-comments pr-comment pr-review-comments pr-reply pr-resolve pr-address pr-copilot-review pr-comments-list pr-comment-delete pr-summary pr-watch pr-merge pr-merge-admin pr-reviewers pr-label pr-close

pr: ## PR commands (make pr)
	@$(MAKE) --no-print-directory help-pr

pr-create: ## Open a pull request for the current branch (make pr-create [base=branch])
	gh pr create --fill $(if $(base),--base "$(base)")

pr-edit: export PR_EDIT_TITLE := $(title)
pr-edit: export PR_EDIT_BODY := $(body)
pr-edit: ## Edit the current PR title or body (make pr-edit title="..." [body="..." OR body_file=path, - reads stdin] [pr_num=N])
	@test -n "$$PR_EDIT_TITLE$$PR_EDIT_BODY$(body_file)" || { printf 'Usage: make pr-edit title="New title" [body="..." OR body_file=- with the body piped on stdin] [pr_num=N]\n' >&2; exit 1; }
	@set -e; \
	tmp=""; \
	trap 'test -n "$$tmp" && rm -f "$$tmp"' EXIT; \
	set -- $(if $(PR_NUM),$(PR_NUM)); \
	if [ -n "$$PR_EDIT_TITLE" ]; then set -- "$$@" --title "$$PR_EDIT_TITLE"; fi; \
	if [ -n "$(body_file)" ]; then set -- "$$@" --body-file "$(body_file)"; \
	elif [ -n "$$PR_EDIT_BODY" ]; then tmp=$$(mktemp); printf '%s' "$$PR_EDIT_BODY" > "$$tmp"; set -- "$$@" --body-file "$$tmp"; fi; \
	gh pr edit "$$@"

pr-list: ## List open pull requests
	gh pr list

pr-status: ## Show current PR status and CI checks
	gh pr checks

pr-checks: ## Watch CI checks until done
	gh pr checks --watch --fail-fast || true

pr-diff: ## Show the diff for the current PR
	gh pr diff

pr-comments: ## Show all comments on the current PR
	gh pr view --comments

pr-comment: ## Add a comment to the current PR (body="msg" OR body_file=path for multiline content, - reads stdin)
	@test -n "$(body)$(body_file)" || (printf 'Usage: make pr-comment body="Looks good"  OR  make pr-comment body_file=- with the comment piped on stdin\n' >&2; exit 1)
	@if [ -n "$(body_file)" ]; then \
	  gh pr comment --body-file "$(body_file)"; \
	else \
	  gh pr comment --body "$(body)"; \
	fi

pr-review-comments: ## List review threads with thread ids (make pr-review-comments [pr_num=N] [show=all])
	@$(GH) list $(if $(pr_num),--pr $(pr_num)) $(if $(filter all,$(show)),--all)

pr-reply: export PR_REPLY_BODY := $(body)
pr-reply: ## Reply to a review thread (make pr-reply thread=PRRT_... body="msg" OR body_file=path, - reads stdin)
	@test -n "$(thread)" || (printf 'Usage: make pr-reply thread=PRRT_... body="Fixed"  OR  body_file=- with the reply piped on stdin\n' >&2; exit 1)
	@if [ -n "$(body_file)" ]; then \
	  $(GH) reply --thread "$(thread)" --body-file "$(body_file)"; \
	else \
	  test -n "$$PR_REPLY_BODY" || (printf 'Provide body="..." or body_file=path.\n' >&2; exit 1); \
	  $(GH) reply --thread "$(thread)" --body "$$PR_REPLY_BODY"; \
	fi

pr-resolve: ## Resolve a review thread (make pr-resolve thread=PRRT_...)
	@test -n "$(thread)" || (printf 'Usage: make pr-resolve thread=PRRT_...\n' >&2; exit 1)
	@$(GH) resolve --thread "$(thread)"

pr-address: export PR_ADDRESS_BODY := $(body)
pr-address: ## Reply to and resolve a review thread (make pr-address thread=PRRT_... body="msg" OR body_file=path, - reads stdin)
	@test -n "$(thread)" || (printf 'Usage: make pr-address thread=PRRT_... body="Fixed"  OR  body_file=- with the reply piped on stdin\n' >&2; exit 1)
	@if [ -n "$(body_file)" ]; then \
	  $(GH) address --thread "$(thread)" --body-file "$(body_file)"; \
	else \
	  test -n "$$PR_ADDRESS_BODY" || (printf 'Provide body="..." or body_file=path.\n' >&2; exit 1); \
	  $(GH) address --thread "$(thread)" --body "$$PR_ADDRESS_BODY"; \
	fi

pr-copilot-review: ## Request a Copilot code review on the current PR (make pr-copilot-review [pr_num=N])
	@$(GH) copilot-review $(if $(pr_num),--pr $(pr_num))

pr-comments-list: ## List individual review comments with node ids (make pr-comments-list [pr_num=N])
	@$(GH) list-comments $(if $(pr_num),--pr $(pr_num))

pr-comment-delete: ## Delete a review comment by node id (make pr-comment-delete comment=PRRC_...)
	@test -n "$(comment)" || (printf 'Usage: make pr-comment-delete comment=PRRC_...\n' >&2; exit 1)
	@$(GH) delete-comment --comment "$(comment)"

pr-summary: ## One-screen PR overview: state, CI rollup, open threads (make pr-summary [pr_num=N])
	@$(GH) summary $(if $(pr_num),--pr $(pr_num))

pr-watch: ## Wait until PR checks settle and a fresh Copilot review lands (make pr-watch [pr_num=N] [since=ISO] [interval=S] [max_polls=K] [checks_only=1])
	@$(GH) watch $(if $(pr_num),--pr $(pr_num)) $(if $(since),--since "$(since)") $(if $(interval),--interval $(interval)) $(if $(max_polls),--max-polls $(max_polls)) $(if $(filter 1,$(checks_only)),--checks-only)

pr-merge: ## Merge a PR (squash, delete branch) (make pr-merge [pr_num=N])
	gh pr merge $(pr_num) --squash --delete-branch

pr-merge-admin: ## Force merge bypassing branch protection (admin) (make pr-merge-admin [pr_num=N])
	gh pr merge $(pr_num) --squash --delete-branch --admin

pr-reviewers: ## Add reviewers (make pr-reviewers users="user1,user2")
	@test -n "$(users)" || (printf 'Usage: make pr-reviewers users="octocat"\n' >&2; exit 1)
	gh pr edit --add-reviewer $(users)

pr-label: ## Add labels (make pr-label labels="bug")
	@test -n "$(labels)" || (printf 'Usage: make pr-label labels="bug"\n' >&2; exit 1)
	gh pr edit --add-label "$(labels)"

pr-close: ## Close the current PR and delete branch
	gh pr close --delete-branch

# ─── CI @ci ───────────────────────────────────────────────────────────────────

.PHONY: ci-runs ci-pages-runs ci-run ci-run-log ci-job-log ci-watch ci-failures ci-platform-checks ci-quick-gates ci-heavy-checks ci-thumbnail-plan ci-plan-outputs ci-apply-app-ledger ci-update-app-ledger ci-write-shard-manifest ci-package-shard-result ci-merge-shard-results ci-coverage-summary ci-finalize-pages-dir ci-audit-repo-settings ci-audit-previews ci-alert-issue refresh-action-shas issues

ci-runs: ## List recent CI workflow runs
	gh run list -L "$(if $(limit),$(limit),10)"

ci-pages-runs: ## List recent GitHub Pages deployment runs
	gh run list -L "$(if $(limit),$(limit),20)" --workflow pages-build-deployment --branch "$(if $(branch),$(branch),gh-pages)"

ci-run: ## Show one CI workflow run (make ci-run run=ID)
	@test -n "$(run)" || (printf 'Usage: make ci-run run=123456\n' >&2; exit 1)
	gh run view "$(run)"

ci-run-log: ## Show failed logs for one CI workflow run (make ci-run-log run=ID)
	@test -n "$(run)" || (printf 'Usage: make ci-run-log run=123456\n' >&2; exit 1)
	gh run view "$(run)" --log-failed

ci-job-log: ## Show logs for one CI job (make ci-job-log run=ID job=ID)
	@test -n "$(run)" -a -n "$(job)" || (printf 'Usage: make ci-job-log run=123456 job=789\n' >&2; exit 1)
	gh run view "$(run)" --job "$(job)" --log

ci-watch: ## Watch the latest CI run until done
	gh run watch

ci-failures: ## Show failed-step logs for this branch's latest run (make ci-failures [run=ID])
	@$(GH) ci-failures $(if $(run),--run $(run))

# The workflow helpers below run on the system interpreter (PYTHONPATH=.
# $(PYTHON)) instead of $(VENV_PYTHON): the scheduled monitor workflows and the
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
	@PYTHONPATH=. $(PYTHON) scripts/ci/workflow_helpers.py thumbnail-plan \
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
	@PYTHONPATH=. $(PYTHON) scripts/ci/workflow_helpers.py plan-outputs

ci-apply-app-ledger: ## Apply cached green app hashes to a persisted impact plan (plan=PATH ledger=PATH output=PATH)
	@test -n "$(plan)" -a -n "$(ledger)" -a -n "$(output)" || (printf 'Usage: make ci-apply-app-ledger plan=.artifacts/ci-plan/plan.json ledger=.artifacts/app-ledger/ledger.json output=.artifacts/ci-plan/memoized-plan.json\n' >&2; exit 1)
	@PYTHONPATH=. $(PYTHON) scripts/ci/app_hashes.py apply-ledger --plan "$(plan)" --ledger "$(ledger)" --output "$(output)"

ci-update-app-ledger: ## Update a ledger from main-verified app hashes (plan=PATH ledger=PATH)
	@test -n "$(plan)" -a -n "$(ledger)" || (printf 'Usage: make ci-update-app-ledger plan=.artifacts/ci-plan/plan.json ledger=.artifacts/app-ledger/ledger.json\n' >&2; exit 1)
	@PYTHONPATH=. $(PYTHON) scripts/ci/app_hashes.py update-ledger --plan "$(plan)" --ledger "$(ledger)"

ci-write-shard-manifest: ## Select one impact-plan shard (plan=PATH shard=N output=PATH)
	@test -n "$(plan)" -a -n "$(shard)" -a -n "$(output)" || (printf 'Usage: make ci-write-shard-manifest plan=.artifacts/ci-plan/plan.json shard=0 output=.artifacts/shard-manifest.json\n' >&2; exit 1)
	@PYTHONPATH=. $(PYTHON) scripts/ci/app_shards.py write-manifest --plan "$(plan)" --shard "$(shard)" --output "$(output)"

ci-package-shard-result: ## Package one shard thumbnail result (manifest=PATH output=PATH)
	@test -n "$(manifest)" -a -n "$(output)" || (printf 'Usage: make ci-package-shard-result manifest=.artifacts/shard-manifest.json output=.artifacts/shard-result\n' >&2; exit 1)
	$(VENV_PYTHON) scripts/ci/app_shards.py package-result --manifest "$(manifest)" --output "$(output)"

ci-merge-shard-results: ## Merge downloaded shard thumbnails (root=PATH)
	@test -n "$(root)" || (printf 'Usage: make ci-merge-shard-results root=.artifacts/shard-results\n' >&2; exit 1)
	$(VENV_PYTHON) scripts/ci/app_shards.py merge-results --root "$(root)"

ci-coverage-summary: ## Summarize a JS coverage report (make ci-coverage-summary report=js-coverage.txt)
	@test -n "$(report)" || (printf 'Usage: make ci-coverage-summary report=js-coverage.txt\n' >&2; exit 1)
	@PYTHONPATH=. $(PYTHON) scripts/ci/workflow_helpers.py coverage-summary --report "$(report)"

ci-finalize-pages-dir: ## Finalize a GitHub Pages payload directory (make ci-finalize-pages-dir root=DIR)
	@test -n "$(root)" || (printf 'Usage: make ci-finalize-pages-dir root=.pages-publish\n' >&2; exit 1)
	@PYTHONPATH=. $(PYTHON) scripts/ci/workflow_helpers.py finalize-pages-dir --root "$(root)"

ci-audit-repo-settings: ## Audit GitHub repo settings drift (make ci-audit-repo-settings [repo=owner/name])
	@PYTHONPATH=. $(PYTHON) scripts/ci/workflow_helpers.py audit-repo-settings \
		--repo "$(if $(repo),$(repo),$(REPO))" \
		--default-branch "$(if $(default_branch),$(default_branch),main)" \
		--pages-branch "$(if $(pages_branch),$(pages_branch),gh-pages)"

ci-audit-previews: ## Detect leaked gh-pages PR previews (make ci-audit-previews [repo=owner/name])
	@PYTHONPATH=. $(PYTHON) scripts/ci/workflow_helpers.py audit-previews \
		--repo "$(if $(repo),$(repo),$(REPO))" \
		--pages-branch "$(if $(pages_branch),$(pages_branch),gh-pages)"

ci-alert-issue: ## Sync a monitored alert issue (title=, run_url=, state=open|close|setup-failure, [detail=] [detail_file=] [labels="ops ci"] [repo=])
	@test -n "$(title)" -a -n "$(run_url)" -a -n "$(state)" || \
		(printf 'Usage: make ci-alert-issue title="..." run_url=https://... state=open|close|setup-failure [detail="..."] [detail_file=path] [labels="ops ci"] [repo=owner/name]\n' >&2; exit 1)
	@PYTHONPATH=. $(PYTHON) scripts/ci/workflow_helpers.py sync-alert-issue \
		--repo "$(if $(repo),$(repo),$(REPO))" \
		--title "$(title)" \
		--run-url "$(run_url)" \
		--state "$(state)" \
		--detail "$(detail)" \
		--detail-file "$(detail_file)" \
		$(foreach label,$(labels),--label $(label))

refresh-action-shas: ## Repin tag-based GitHub Actions refs to commit SHAs (needs GH_TOKEN)
	PYTHONPATH=. $(PYTHON) -m scripts.ci.refresh_action_shas

issues: ## List open issues
	gh issue list
