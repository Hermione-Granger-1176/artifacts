.DEFAULT_GOAL := help

# ─── Variables ────────────────────────────────────────────────────────────────

PYTHON      ?= python3.12
UV          ?= uv
UVX         ?= uvx
VENV        ?= .venv
VENV_PYTHON := $(VENV)/bin/python
NPM         ?= npm

# ─── Setup ────────────────────────────────────────────────────────────────────

.PHONY: install node-install setup-base setup setup-all setup-ci

install:
	UV_PROJECT_ENVIRONMENT=$(VENV) $(UV) sync --all-groups --frozen --python $(PYTHON)

node-install:
	$(NPM) ci

setup-base: install node-install

setup: setup-base ## Install Python and Node deps (fast, no Chromium)

setup-all: setup-base ## Full setup including Chromium for browser tests
	$(VENV)/bin/playwright install chromium

setup-ci: setup-base ## CI variant with Chromium system deps
	$(VENV)/bin/playwright install chromium --with-deps

# ─── Lint ─────────────────────────────────────────────────────────────────────

.PHONY: lint lint-py lint-js lint-css lint-yaml lint-workflows lint-doc-commands lint-make-targets lint-js-test-coverage editorconfig-check

lint: editorconfig-check lint-py lint-js lint-css lint-yaml lint-workflows lint-doc-commands lint-make-targets lint-js-test-coverage ## Run all linters

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

lint-doc-commands: ## Check contributor docs use Make targets
	$(VENV_PYTHON) scripts/lint/check_doc_commands.py

lint-make-targets: ## Check documented Make targets
	$(VENV_PYTHON) scripts/lint/check_make_targets.py

lint-js-test-coverage: ## Check every JS source file has test imports
	$(VENV_PYTHON) scripts/lint/check_js_test_coverage.py

# ─── Format ───────────────────────────────────────────────────────────────────

.PHONY: fmt fmt-py fmt-js fmt-css

fmt: fmt-py fmt-js fmt-css ## Auto-fix all (ruff, eslint, stylelint)

fmt-py: ## Auto-fix Python (ruff check --fix + ruff format)
	$(VENV_PYTHON) -m ruff check --fix .
	$(VENV_PYTHON) -m ruff format .

fmt-js: ## Auto-fix JavaScript (eslint --fix)
	$(NPM) run lint:js -- --fix

fmt-css: ## Auto-fix CSS (stylelint --fix)
	$(NPM) run lint:css -- --fix

# ─── Test ─────────────────────────────────────────────────────────────────────

.PHONY: test test-py test-ci test-ci-workflows test-js test-browser test-browser-root test-browser-root-smoke test-browser-root-accessibility test-browser-root-flows test-browser-apps test-browser-apps-smoke test-browser-apps-accessibility test-browser-apps-flows test-browser-live coverage-js

test: test-py test-js ## Run non-browser Python tests + JS tests

test-py: ## Run Python tests only (with coverage)
	$(VENV_PYTHON) -m pytest --ignore=tests/browser

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

# ─── Build ────────────────────────────────────────────────────────────────────

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

# ─── Quality gates ────────────────────────────────────────────────────────────

.PHONY: security audit-fix-node check-generated check-local check-web check

security: ## Run dependency audits (pip-audit + npm audit)
	mkdir -p .artifacts
	$(UV) export --all-groups --frozen --no-emit-project --format requirements.txt --output-file .artifacts/requirements-audit.txt
	$(VENV_PYTHON) scripts/ci/run_security_audit.py --requirements .artifacts/requirements-audit.txt
	$(NPM) audit

audit-fix-node: ## Apply available npm audit fixes to package-lock.json
	$(NPM) audit fix --package-lock-only

check-generated: ## Check canonical generated files are up to date
	$(VENV_PYTHON) scripts/lint/check_generated_drift.py

check-local: lint test coverage-js security validate check-generated ## Fast gate: lint + test + coverage + security + validate + generated drift

check-web: test-browser thumbnails ## Browser gate: test-browser + thumbnails

check: check-local check-web index site ## Full gate: check-local + check-web + index + site

# ─── Utilities ────────────────────────────────────────────────────────────────

.PHONY: lock lock-node fix-deps align-tables status clean help

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

status: ## Show workspace health (git, venv, node, generated files)
	@echo "=== Git ==="
	@git status -sb
	@echo
	@echo "=== Venv ==="
	@test -x $(VENV_PYTHON) && echo "OK: $(VENV_PYTHON) exists" || echo "MISSING: run make setup"
	@echo
	@echo "=== Node ==="
	@test -d node_modules && echo "OK: node_modules exists" || echo "MISSING: run make setup"
	@echo
	@echo "=== Generated files ==="
	@test -f js/data.js && echo "OK: js/data.js" || echo "STALE: run make index"
	@test -f js/gallery-config.js && echo "OK: js/gallery-config.js" || echo "STALE: run make index"
	@test -d _site && echo "OK: _site/" || echo "NOT BUILT: run make site"

clean: ## Remove venv, caches, node_modules, _site
	rm -rf $(VENV) .pytest_cache .ruff_cache build dist *.egg-info node_modules _site .coverage

help: ## Show this help
	@awk ' \
		/^# ─── .+ ───/ { \
			gsub(/^# ─── | ─+$$/, ""); \
			section = $$0; \
			printed = 0; \
			drilldown = (section == "Git" || section == "Pull requests" || section == "CI"); \
		} \
		/^[a-zA-Z_-]+:.*## / { \
			if (section && !printed) { printf "\n  \033[1m%s\033[0m\n", section; printed = 1 } \
			sub(/:.*/,  "", $$1); \
			desc = $$0; sub(/.*## /, "", desc); \
			if (!drilldown || $$1 == "git" || $$1 == "pr" || $$1 == "ci") \
				printf "    %-20s %s\n", $$1, desc; \
		}' $(MAKEFILE_LIST)

# ─── Git ──────────────────────────────────────────────────────────────────────

.PHONY: git branch log log-file diff diff-staged

git: ## Git commands (make git)
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' ' \
		/^(branch|log|log-file|diff|diff-staged):/ { printf "    %-20s %s\n", $$1, $$2 }'

branch: ## Create and switch to a new branch from main (make branch name=X)
	@test -n "$(name)" || (printf 'Usage: make branch name=my-feature\n' >&2; exit 1)
	git checkout main && git pull && git checkout -b "$(name)"

log: ## Show recent commit log (short)
	git log --oneline -20

log-file: ## Show recent commit log for one file (make log-file path=FILE)
	@test -n "$(path)" || (printf 'Usage: make log-file path=.github/workflows/update.yml\n' >&2; exit 1)
	git log --date=short --pretty=format:'%h %ad %s' -20 -- "$(path)"

diff: ## Show unstaged changes
	git diff

diff-staged: ## Show staged changes
	git diff --cached

# ─── Pull requests ────────────────────────────────────────────────────────────

REPO ?= $(strip $(shell repo="$$(git remote get-url origin 2>/dev/null | sed -nE 's|.*github\.com[:/]([^/]+/[^/.]+)(\.git)?$$|\1|p')"; \
	if [ -z "$$repo" ]; then repo="$$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)"; fi; \
	printf '%s' "$$repo"))

.PHONY: pr pr-create pr-list pr-status pr-checks pr-diff pr-comments pr-comment pr-review-comments pr-reply pr-resolve pr-merge pr-merge-admin pr-reviewers pr-label pr-close

pr: ## PR commands (make pr)
	@grep -E '^pr-[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{ printf "    %-20s %s\n", $$1, $$2 }'

pr-create: ## Open a pull request for the current branch
	gh pr create --fill

pr-list: ## List open pull requests
	gh pr list

pr-status: ## Show current PR status and CI checks
	gh pr checks

pr-checks: ## Watch CI checks until done (5 min poll, 2 max)
	timeout 600 gh pr checks --watch --interval 300 --fail-fast || true

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

pr-review-comments: ## List review threads with resolution status (make pr-review-comments pr_num=N)
	@test -n "$(pr_num)" || (printf 'Usage: make pr-review-comments pr_num=19\n' >&2; exit 1)
	@printf '%s\n' "$(REPO)" | grep -Eq '^[^/]+/[^/]+$$' || (printf 'Error: REPO must be set to owner/name (e.g. REPO=octocat/Hello-World)\n' >&2; exit 1)
	@owner=$$(echo "$(REPO)" | cut -d/ -f1) && \
	 name=$$(echo "$(REPO)" | cut -d/ -f2) && \
	 gh api graphql -F pr_num='$(pr_num)' -F owner="$$owner" -F name="$$name" -f query='query($$pr_num: Int!, $$owner: String!, $$name: String!) { repository(owner: $$owner, name: $$name) { pullRequest(number: $$pr_num) { reviewThreads(first: 50) { nodes { id isResolved path line comments(first: 10) { nodes { databaseId body author { login } createdAt } } } } } } }'

pr-reply: ## Reply to a review comment (pr_num=N comment=ID body="msg" OR body_file=path for multiline or shell-special content)
	@test -n "$(pr_num)" -a -n "$(comment)" || (printf 'Usage: make pr-reply pr_num=19 comment=123456 body="Fixed"  OR  body_file=/tmp/reply.md\n' >&2; exit 1)
	@test -n "$(body)$(body_file)" || (printf 'Provide body="..." or body_file=path. Prefer body_file for text containing backticks, quotes, or newlines.\n' >&2; exit 1)
	@if [ -n "$(body_file)" ]; then \
	  test -r "$(body_file)" || (printf 'Error: body_file=%s is not readable\n' "$(body_file)" >&2; exit 1); \
	  python3 -c 'import json,sys; sys.stdout.write(json.dumps({"body": sys.stdin.read()}))' < "$(body_file)" \
	    | gh api repos/$(REPO)/pulls/$(pr_num)/comments/$(comment)/replies --method POST --input -; \
	else \
	  gh api repos/$(REPO)/pulls/$(pr_num)/comments/$(comment)/replies -f body="$(body)"; \
	fi

pr-resolve: ## Resolve a review thread (make pr-resolve thread=PRRT_...)
	@test -n "$(thread)" || (printf 'Usage: make pr-resolve thread=PRRT_kwDO...\n' >&2; exit 1)
	@gh api graphql -F thread="$(thread)" -f query='mutation($$thread: ID!) { resolveReviewThread(input: { threadId: $$thread }) { thread { id isResolved } } }'

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

# ─── CI ───────────────────────────────────────────────────────────────────────

.PHONY: ci ci-runs ci-pages-runs ci-run ci-run-log ci-job-log ci-watch ci-audit-repo-settings issues

ci: ## CI commands (make ci)
	@grep -E '^(ci-|issues)[a-zA-Z_-]*:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{ printf "    %-20s %s\n", $$1, $$2 }'

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

ci-audit-repo-settings: ## Audit GitHub repo settings drift (make ci-audit-repo-settings [repo=owner/name])
	$(VENV_PYTHON) scripts/ci/workflow_helpers.py audit-repo-settings \
		--repo "$(if $(repo),$(repo),$(REPO))" \
		--default-branch "$(if $(default_branch),$(default_branch),main)" \
		--pages-branch "$(if $(pages_branch),$(pages_branch),gh-pages)"

issues: ## List open issues
	gh issue list
