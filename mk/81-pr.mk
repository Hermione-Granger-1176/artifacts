# ─── Pull requests @pr ────────────────────────────────────────────────────────

.PHONY: pr pr-create pr-edit pr-list pr-status pr-checks pr-diff pr-checkout pr-comments pr-comment pr-review-comments pr-reply pr-resolve pr-address pr-copilot-review pr-comments-list pr-comment-delete pr-summary pr-watch pr-merge pr-merge-admin pr-reviewers pr-label pr-close

# Current branch's PR, resolved through the tested helper: `gh pr view` first, then
# the REST API when the environment blocks GraphQL.
PR_NUM = $(if $(pr_num),$(pr_num),$(strip $(shell $(GH) current-pr 2>/dev/null)))

# Smart default for CI-run targets: the caller's run= else the latest run on the
# current branch, resolved through the tested gh helper (same source as
# ci-failures). Stays empty when nothing can be resolved so the guard can fire.
RUN_ID = $(if $(run),$(run),$(strip $(shell $(GH) latest-run-id 2>/dev/null)))

pr: ## PR commands (make pr)
	@$(MAKE) --no-print-directory help-pr

pr-create: ## Open a pull request (make pr-create [base=branch]; TITLE='...' make pr-create < body.md for an explicit one)
	@if [ -z "$$TITLE" ]; then \
		$(GH) pr-create $(if $(base),--base "$(base)"); \
	else \
		$(GH) pr-create $(if $(base),--base "$(base)") --title "$$TITLE" --body-file -; \
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
	@$(GH) pr-list

pr-status: ## Show a PR's status and CI checks (make pr-status [pr_num=N])
	@$(GH) pr-status $(if $(pr_num),--pr "$(pr_num)")

pr-checks: ## Watch CI checks until done (make pr-checks [pr_num=N])
	@$(GH) pr-checks $(if $(pr_num),--pr "$(pr_num)") || true

pr-diff: ## Show the diff for the current PR (make pr-diff [pr_num=N])
	@$(GH) pr-diff $(if $(pr_num),--pr "$(pr_num)")

pr-checkout: ## Check out a PR's branch locally (make pr-checkout pr_num=N)
	$(call need,pr_num,make pr-checkout pr_num=123)
	@$(GH) pr-checkout --pr "$(pr_num)"

pr-comments: ## Show all comments on a PR (make pr-comments [pr_num=N])
	@$(GH) pr-comments $(if $(pr_num),--pr "$(pr_num)")

pr-comment: ## Add a comment to a PR, body on stdin (make pr-comment < notes.md) [pr_num=N]
	@$(GH) comment $(if $(pr_num),--pr "$(pr_num)") --body-file -

pr-review-comments: ## List review threads with thread ids (make pr-review-comments [pr_num=N] [show=all])
	@$(GH) list $(if $(pr_num),--pr $(pr_num)) $(if $(filter all,$(show)),--all)

pr-reply: ## Reply to a review thread, body on stdin (make pr-reply thread=PRRT_... < notes.md) [pr_num=N]
	$(call need,thread,make pr-reply thread=PRRT_... < notes.md)
	@$(GH) reply --thread "$(thread)" $(if $(pr_num),--pr "$(pr_num)") --body-file -

pr-resolve: ## Resolve a review thread (make pr-resolve thread=PRRT_...) [pr_num=N]
	$(call need,thread,make pr-resolve thread=PRRT_...)
	@$(GH) resolve --thread "$(thread)" $(if $(pr_num),--pr "$(pr_num)")

pr-address: ## Reply to and resolve a review thread, body on stdin (make pr-address thread=PRRT_... < notes.md) [pr_num=N]
	$(call need,thread,make pr-address thread=PRRT_... < notes.md)
	@$(GH) address --thread "$(thread)" $(if $(pr_num),--pr "$(pr_num)") --body-file -

pr-copilot-review: ## Request a Copilot code review on the current PR (make pr-copilot-review [pr_num=N])
	@$(GH) copilot-review $(if $(pr_num),--pr $(pr_num))

pr-comments-list: ## List individual review comments with node ids (make pr-comments-list [pr_num=N])
	@$(GH) list-comments $(if $(pr_num),--pr $(pr_num))

pr-comment-delete: ## Delete a review comment by node id or numeric id (make pr-comment-delete comment_id=PRRC_...)
	$(call need,comment_id,make pr-comment-delete comment_id=PRRC_...)
	@$(GH) delete-comment --comment "$(comment_id)"

pr-summary: ## One-screen PR overview: state, CI rollup, open threads (make pr-summary [pr_num=N])
	@$(GH) summary $(if $(pr_num),--pr $(pr_num))

pr-watch: ## Observe the Copilot review and checks (make pr-watch [pr_num=N] [request=1] [interval=S] [max_polls=K] [expected_checks=N] [checks_only=1])
	@$(GH) watch $(if $(pr_num),--pr "$(pr_num)") $(if $(filter 1,$(request)),--request-copilot) $(if $(interval),--interval "$(interval)") $(if $(max_polls),--max-polls "$(max_polls)") $(if $(expected_checks),--expected-checks "$(expected_checks)") $(if $(filter 1,$(checks_only)),--checks-only)

pr-merge: ## Merge a PR (squash, delete branch) (make pr-merge [pr_num=N])
	@$(GH) pr-merge $(if $(pr_num),--pr "$(pr_num)")

pr-merge-admin: ## Force merge bypassing branch protection (admin) (make pr-merge-admin [pr_num=N])
	@$(GH) pr-merge $(if $(pr_num),--pr "$(pr_num)") --admin

pr-reviewers: ## Add reviewers (make pr-reviewers users="user1,user2" [pr_num=N])
	$(call need,users,make pr-reviewers users="octocat")
	@$(GH) pr-reviewers --users "$(users)" $(if $(pr_num),--pr "$(pr_num)")

pr-label: ## Add labels (make pr-label labels="bug" [pr_num=N])
	$(call need,labels,make pr-label labels="bug")
	@$(GH) pr-label --labels "$(labels)" $(if $(pr_num),--pr "$(pr_num)")

pr-close: ## Close a PR and delete branch (make pr-close [pr_num=N])
	@$(GH) pr-close $(if $(pr_num),--pr "$(pr_num)")
