# ─── Workflow helpers @workflow ───────────────────────────────────────────────

.PHONY: ci-platform-checks ci-quick-gates ci-heavy-checks ci-thumbnail-plan ci-plan-outputs ci-apply-app-ledger ci-update-app-ledger ci-write-shard-manifest ci-package-shard-result ci-merge-shard-results ci-coverage-summary ci-finalize-pages-dir ci-audit-repo-settings ci-audit-previews ci-schedule-watchdog ci-alert-issue

# Repository slug (owner/name) for the audit and alert helpers. Resolve from
# the origin remote first, then fall back to gh.
REPO ?= $(strip $(shell repo="$$(git remote get-url origin 2>/dev/null | sed -nE 's|.*github\.com[:/]([^/]+/[^/.]+)(\.git)?$$|\1|p')"; \
	if [ -z "$$repo" ]; then repo="$$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)"; fi; \
	printf '%s' "$$repo"))

ci-platform-checks: ## Run ci-quick-gates, then ci-heavy-checks
	@$(MAKE) --no-print-directory ci-quick-gates
	@$(MAKE) --no-print-directory ci-heavy-checks

ci-quick-gates: ## Run fast formatting, lint, type, and artifact checks
	$(VENV_PYTHON) scripts/ci/run_parallel_checks.py --timeout 1200 \
		format-check lint typecheck validate

ci-heavy-checks: ## Run slow test, coverage, dead-code, and security checks
	$(VENV_PYTHON) scripts/ci/run_parallel_checks.py --timeout 1200 \
		test-py coverage-js dead-code security

# The workflow helpers from here down, except the two shard package and merge
# targets and ci-schedule-watchdog, run on the system interpreter ($(PYTHON))
# with the shared repository path prefix instead of $(VENV_PYTHON). The monitor
# workflows and the update.yml plan, publish, and cleanup jobs call them without
# a provisioned venv, and the coverage-summary and setup-failure alert paths
# must work even when dependency installation failed. The helpers and
# everything they import are stdlib-only. The monitor helpers read GH_TOKEN
# from the environment.
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

ci-schedule-watchdog: ## Detect disabled scheduled workflows (make ci-schedule-watchdog [repo=owner/name])
	@$(PY_PATH_PREFIX) $(VENV_PYTHON) scripts/ci/schedule_watchdog.py \
		--repo "$(if $(repo),$(repo),$(REPO))"

ci-alert-issue: ## Sync a monitored alert issue, detail on stdin (TITLE='...' make ci-alert-issue run_url=URL state=open|close|setup-failure [labels="ops ci"] [repo=])
	@test -n "$$TITLE" -a -n "$(run_url)" -a -n "$(state)" || \
		(printf "Usage: TITLE='Alert title' make ci-alert-issue run_url=https://... state=open|close|setup-failure [labels=\"ops ci\"] [repo=owner/name] < detail.md\n" >&2; exit 1)
	@set -e; \
	set -- --repo "$(if $(repo),$(repo),$(REPO))" --title "$$TITLE" --run-url "$(run_url)" --state "$(state)" \
		$(foreach label,$(labels),--label "$(label)"); \
	$(NO_TTY_READ) set -- "$$@" --detail-file -; \
	$(PY_PATH_PREFIX) $(PYTHON) scripts/ci/workflow_helpers.py sync-alert-issue "$$@"
