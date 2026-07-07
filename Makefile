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

.PHONY: lint lint-py lint-js lint-css lint-yaml lint-workflows workflow-lint lint-doc-commands lint-make-targets lint-js-test-coverage editorconfig-check check-overrides

lint: editorconfig-check lint-py lint-js lint-css lint-yaml lint-workflows lint-doc-commands lint-make-targets lint-js-test-coverage check-overrides ## Run all linters

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

check-overrides: ## Check npm overrides are still needed
	$(NPM) run check:overrides

# ─── Format @format ───────────────────────────────────────────────────────────

.PHONY: fmt fmt-py fmt-js fmt-css fmt-prettier format format-check format-py-check format-prettier-check

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

format-prettier-check: ## Check Prettier-managed files only
	$(NPM) run format:check

# ─── Typecheck @typecheck ────────────────────────────────────────────────────

.PHONY: typecheck typecheck-py typecheck-web

typecheck: typecheck-py typecheck-web ## Run all type checks

typecheck-py: ## Run mypy strict type checking over scripts/
	$(VENV_PYTHON) -m mypy $(PY_TYPE_PATHS)

typecheck-web: ## Run TypeScript checkJs on hand-written js/ modules
	$(NPM) run typecheck:web

# ─── Dead code @deadcode ──────────────────────────────────────────────────────

.PHONY: dead-code dead-code-py dead-code-js

dead-code: dead-code-py dead-code-js ## Detect unused Python and JavaScript code

dead-code-py: ## Detect unused Python code with vulture
	$(VENV_PYTHON) -m vulture

dead-code-js: ## Detect unused JavaScript files, exports, and dependencies
	$(NPM) run dead-code

# ─── Test @test ───────────────────────────────────────────────────────────────

.PHONY: test test-py test-ci test-ci-workflows test-js test-browser test-browser-root test-browser-root-smoke test-browser-root-accessibility test-browser-root-flows test-browser-apps test-browser-apps-smoke test-browser-apps-accessibility test-browser-apps-flows test-browser-live coverage-js

test: test-py test-js ## Run non-browser Python tests + JS tests

test-py: ## Run Python tests only (with coverage, pass ARGS="-k name --no-cov" for a subset)
	$(VENV_PYTHON) -m pytest --ignore=tests/browser $(ARGS)

test-ci: ## Run CI Python tests only
	$(VENV_PYTHON) -m pytest --no-cov tests/ci

test-ci-workflows: ## Run GitHub workflow contract tests only
	$(VENV_PYTHON) -m pytest --no-cov tests/ci/test_workflow_contracts.py

test-js: ## Run JS tests only
	$(NPM) run test

test-browser: test-browser-root test-browser-apps ## Run all browser tests (needs Chromium)

test-browser-root: test-browser-root-smoke test-browser-root-accessibility test-browser-root-flows ## Run all root gallery browser tests

test-browser-root-smoke: ## Run root gallery smoke browser tests
	ARTIFACTS_REQUIRE_BROWSER_TESTS=1 $(VENV_PYTHON) -m pytest --no-cov \
		tests/browser/test_frontend_smoke.py

test-browser-root-accessibility: ## Run root gallery accessibility browser tests
	ARTIFACTS_REQUIRE_BROWSER_TESTS=1 $(VENV_PYTHON) -m pytest --no-cov \
		tests/browser/test_frontend_accessibility.py

test-browser-root-flows: ## Run root gallery browser-flow tests
	ARTIFACTS_REQUIRE_BROWSER_TESTS=1 $(VENV_PYTHON) -m pytest --no-cov \
		tests/browser/test_frontend_browser_flows.py

test-browser-apps: test-browser-apps-smoke test-browser-apps-accessibility test-browser-apps-flows ## Run all mature app browser tests

test-browser-apps-smoke: ## Run mature app smoke browser tests
	ARTIFACTS_REQUIRE_BROWSER_TESTS=1 $(VENV_PYTHON) -m pytest --no-cov \
		tests/browser/test_frontend_apps_smoke.py

test-browser-apps-accessibility: ## Run mature app accessibility browser tests
	ARTIFACTS_REQUIRE_BROWSER_TESTS=1 $(VENV_PYTHON) -m pytest --no-cov \
		tests/browser/test_frontend_apps_accessibility.py

test-browser-apps-flows: ## Run mature app browser-flow tests
	ARTIFACTS_REQUIRE_BROWSER_TESTS=1 $(VENV_PYTHON) -m pytest --no-cov \
		tests/browser/test_frontend_apps_browser_flows.py

test-browser-live: ## Run live-site browser verification
	ARTIFACTS_REQUIRE_BROWSER_TESTS=1 $(VENV_PYTHON) -m pytest --no-cov \
		tests/browser/test_frontend_live.py

coverage-js: ## Run JS tests with coverage enforcement
	@if [ -n "$(COVERAGE_OUTPUT)" ]; then \
		bash -o pipefail -c '$(NPM) run test:coverage | tee "$(COVERAGE_OUTPUT)"'; \
	else \
		$(NPM) run test:coverage; \
	fi

# ─── Build @build ─────────────────────────────────────────────────────────────

.PHONY: validate thumbnails index site generate new

validate: ## Check artifact directories are complete
	$(VENV_PYTHON) -c "from scripts.build.generate_index import validate; validate()"

thumbnails: ## Regenerate WebP thumbnails (needs Chromium)
	$(VENV_PYTHON) scripts/build/generate_thumbnails.py

index: ## Rebuild js/data.js, js/gallery-config.js, README
	$(VENV_PYTHON) scripts/build/generate_index.py

site: ## Assemble _site/ deploy payload
	$(VENV_PYTHON) scripts/build/prepare_site.py

generate: thumbnails index ## Run thumbnails + index

new: ## Scaffold a new artifact directory (make new name=X)
	@test -n "$(name)" || (printf 'Usage: make new name=my-artifact\n' >&2; exit 1)
	$(VENV_PYTHON) scripts/build/scaffold_artifact.py "$(name)"

# ─── Quality gates @quality ───────────────────────────────────────────────────

.PHONY: ci-python ci-web ci ci-fast security audit-python audit-node audit-fix-node check-generated check-local check-fast check-web check fix

ci-python: format-py-check lint-py typecheck-py dead-code-py test-py ## Python CI gate

ci-web: format-prettier-check lint-js lint-css typecheck-web lint-workflows lint-doc-commands lint-make-targets lint-js-test-coverage check-overrides dead-code-js test-js coverage-js ## Web and docs CI gate

ci: ci-python ci-web security validate check-generated ## Full local CI gate without browser tests

ci-fast: ## Run the non-browser CI checks in parallel
	$(VENV_PYTHON) scripts/ci/run_parallel_checks.py format-check lint typecheck test-py coverage-js dead-code security validate check-generated

security: audit-python audit-node ## Run dependency audits

audit-python: ## Export locked Python deps and run pip-audit
	mkdir -p .artifacts
	$(UV) export --all-groups --frozen --no-emit-project --format requirements.txt --output-file .artifacts/requirements-audit.txt
	$(VENV_PYTHON) scripts/ci/run_security_audit.py --requirements .artifacts/requirements-audit.txt

audit-node: ## Run npm dependency audit
	$(NPM) audit

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
	@$(GH) summary || true

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

help-%: ## List the commands in one group (e.g. make help-pr)
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

.PHONY: git branch stage stage-all commit push log log-file diff diff-staged

git: ## Git commands (make git)
	@$(MAKE) --no-print-directory help-git

branch: ## Create and switch to a new branch off main, or off base for a stacked branch (make branch name=X [base=branch])
	@test -n "$(name)" || (printf 'Usage: make branch name=my-feature [base=other-branch]\n' >&2; exit 1)
	git checkout "$(if $(base),$(base),main)" && \
	if git rev-parse --symbolic-full-name --abbrev-ref '@{u}' >/dev/null 2>&1; then git pull; fi && \
	git checkout -b "$(name)"

stage: ## Stage selected files (make stage files="path ...")
	@test -n "$(files)" || (printf 'Usage: make stage files="path ..."\n' >&2; exit 1)
	git add -- $(files)

stage-all: ## Stage all workspace changes
	git add -A

commit: ## Commit staged changes (make commit message="..." OR message_file=path [amend=1])
	@test -n "$(message)$(message_file)" || (printf 'Usage: make commit message="Commit message" OR message_file=/tmp/message.txt\n' >&2; exit 1)
	@if [ -n "$(message_file)" ]; then \
	  git commit $(if $(amend),--amend) -F "$(message_file)"; \
	else \
	  git commit $(if $(amend),--amend) -m "$(message)"; \
	fi

push: ## Push the current branch to origin
	git push -u origin HEAD

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

.PHONY: pr pr-create pr-edit pr-list pr-status pr-checks pr-diff pr-comments pr-comment pr-review-comments pr-reply pr-resolve pr-address pr-comments-list pr-comment-delete pr-summary pr-merge pr-merge-admin pr-reviewers pr-label pr-close

pr: ## PR commands (make pr)
	@$(MAKE) --no-print-directory help-pr

pr-create: ## Open a pull request for the current branch (make pr-create [base=branch])
	gh pr create --fill $(if $(base),--base "$(base)")

pr-edit: export PR_EDIT_TITLE := $(title)
pr-edit: export PR_EDIT_BODY := $(body)
pr-edit: ## Edit the current PR title or body (make pr-edit title="..." [body="..."] [pr_num=N])
	@test -n "$$PR_EDIT_TITLE$$PR_EDIT_BODY" || { printf 'Usage: make pr-edit title="New title" [body="..."] [pr_num=N]\n' >&2; exit 1; }
	@set -e; \
	tmp=""; \
	trap 'test -n "$$tmp" && rm -f "$$tmp"' EXIT; \
	set -- $(if $(PR_NUM),$(PR_NUM)); \
	if [ -n "$$PR_EDIT_TITLE" ]; then set -- "$$@" --title "$$PR_EDIT_TITLE"; fi; \
	if [ -n "$$PR_EDIT_BODY" ]; then tmp=$$(mktemp); printf '%s' "$$PR_EDIT_BODY" > "$$tmp"; set -- "$$@" --body-file "$$tmp"; fi; \
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

pr-comment: ## Add a comment to the current PR (body="msg" OR body_file=path for multiline or shell-special content)
	@test -n "$(body)$(body_file)" || (printf 'Usage: make pr-comment body="Looks good"  OR  make pr-comment body_file=/tmp/msg.md\n' >&2; exit 1)
	@if [ -n "$(body_file)" ]; then \
	  gh pr comment --body-file "$(body_file)"; \
	else \
	  gh pr comment --body "$(body)"; \
	fi

pr-review-comments: ## List review threads with thread ids (make pr-review-comments [pr_num=N] [show=all])
	@$(GH) list $(if $(pr_num),--pr $(pr_num)) $(if $(filter all,$(show)),--all)

pr-reply: export PR_REPLY_BODY := $(body)
pr-reply: ## Reply to a review thread (make pr-reply thread=PRRT_... body="msg" OR body_file=path)
	@test -n "$(thread)" || (printf 'Usage: make pr-reply thread=PRRT_... body="Fixed"  OR  body_file=/tmp/reply.md\n' >&2; exit 1)
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
pr-address: ## Reply to and resolve a review thread (make pr-address thread=PRRT_... body="msg" OR body_file=path)
	@test -n "$(thread)" || (printf 'Usage: make pr-address thread=PRRT_... body="Fixed"  OR  body_file=/tmp/reply.md\n' >&2; exit 1)
	@if [ -n "$(body_file)" ]; then \
	  $(GH) address --thread "$(thread)" --body-file "$(body_file)"; \
	else \
	  test -n "$$PR_ADDRESS_BODY" || (printf 'Provide body="..." or body_file=path.\n' >&2; exit 1); \
	  $(GH) address --thread "$(thread)" --body "$$PR_ADDRESS_BODY"; \
	fi

pr-comments-list: ## List individual review comments with node ids (make pr-comments-list [pr_num=N])
	@$(GH) list-comments $(if $(pr_num),--pr $(pr_num))

pr-comment-delete: ## Delete a review comment by node id (make pr-comment-delete comment=PRRC_...)
	@test -n "$(comment)" || (printf 'Usage: make pr-comment-delete comment=PRRC_...\n' >&2; exit 1)
	@$(GH) delete-comment --comment "$(comment)"

pr-summary: ## One-screen PR overview: state, CI rollup, open threads (make pr-summary [pr_num=N])
	@$(GH) summary $(if $(pr_num),--pr $(pr_num))

pr-merge: ## Merge the current PR (squash, delete branch)
	gh pr merge --squash --delete-branch

pr-merge-admin: ## Force merge bypassing branch protection (admin)
	gh pr merge --squash --delete-branch --admin

pr-reviewers: ## Add reviewers (make pr-reviewers users="user1,user2")
	@test -n "$(users)" || (printf 'Usage: make pr-reviewers users="octocat"\n' >&2; exit 1)
	gh pr edit --add-reviewer $(users)

pr-label: ## Add labels (make pr-label labels="bug")
	@test -n "$(labels)" || (printf 'Usage: make pr-label labels="bug"\n' >&2; exit 1)
	gh pr edit --add-label "$(labels)"

pr-close: ## Close the current PR and delete branch
	gh pr close --delete-branch

# ─── CI @ci ───────────────────────────────────────────────────────────────────

.PHONY: ci-runs ci-pages-runs ci-run ci-run-log ci-job-log ci-watch ci-failures ci-audit-repo-settings issues

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

ci-audit-repo-settings: ## Audit GitHub repo settings drift (make ci-audit-repo-settings [repo=owner/name])
	$(VENV_PYTHON) scripts/ci/workflow_helpers.py audit-repo-settings \
		--repo "$(if $(repo),$(repo),$(REPO))" \
		--default-branch "$(if $(default_branch),$(default_branch),main)" \
		--pages-branch "$(if $(pages_branch),$(pages_branch),gh-pages)"

issues: ## List open issues
	gh issue list
