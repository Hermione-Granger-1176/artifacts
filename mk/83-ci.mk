# ─── CI runs @ci ──────────────────────────────────────────────────────────────

.PHONY: ci-runs ci-pages-runs ci-run ci-rerun ci-dispatch ci-caches ci-cache-delete ci-run-log ci-job-log ci-watch ci-failures

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
