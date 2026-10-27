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
	$(GH) issue-list "$$@"

issue-view: ## Show an issue with its comments (make issue-view issue=N)
	$(call need,issue,make issue-view issue=123)
	@$(GH) issue-view --issue "$(issue)"

issue-summary: ## One-screen issue overview: state, labels, assignees, recent comments (make issue-summary issue=N)
	$(call need,issue,make issue-summary issue=123)
	@$(GH) issue-summary --issue $(issue)

issue-create: ## Open an issue, body on stdin (TITLE='Fix X' make issue-create < issue.md [labels="a,b"] [assignee=@me])
	@test -n "$$TITLE" || \
		(printf "Usage: TITLE='Fix X' make issue-create < issue.md [labels=\"bug,ci\"] [assignee=@me]\n" >&2; exit 1)
	@$(GH) issue-create --title "$$TITLE" $(if $(labels),--labels "$(labels)") \
		$(if $(assignee),--assignee "$(assignee)") --body-file -

issue-comment: ## Comment on an issue, body on stdin (make issue-comment issue=N < notes.md)
	$(call need,issue,make issue-comment issue=123 < notes.md)
	@$(GH) issue-comment --issue "$(issue)" --body-file -

issue-edit: ## Edit an issue (TITLE='...' make issue-edit issue=N; new body on stdin: make issue-edit issue=N < body.md)
	$(call need,issue,make issue-edit issue=123 [TITLE='New title'] [< body.md])
	@set -e; \
	body=""; $(NO_TTY_READ) body=$$(cat); \
	test -n "$$TITLE$$body" || \
		{ printf "Nothing to change. Set TITLE='...' or pipe a new body in.\n" >&2; exit 1; }; \
	set -- --issue "$(issue)"; \
	if [ -n "$$TITLE" ]; then set -- "$$@" --title "$$TITLE"; fi; \
	if [ -n "$$body" ]; then \
		printf '%s' "$$body" | $(GH) issue-edit "$$@" --body-file -; \
	else \
		$(GH) issue-edit "$$@"; \
	fi

issue-label: ## Add labels to an issue (make issue-label issue=N labels="bug,ci")
	$(call need,issue,make issue-label issue=123 labels="bug")
	$(call need,labels,make issue-label issue=123 labels="bug")
	@$(GH) issue-label --issue "$(issue)" --labels "$(labels)"

issue-unlabel: ## Remove labels from an issue (make issue-unlabel issue=N labels="bug,ci")
	$(call need,issue,make issue-unlabel issue=123 labels="bug")
	$(call need,labels,make issue-unlabel issue=123 labels="bug")
	@$(GH) issue-unlabel --issue "$(issue)" --labels "$(labels)"

issue-assign: ## Assign users to an issue (make issue-assign issue=N users="a,b" OR mine=1)
	$(call need,issue,make issue-assign issue=123 users="octocat" OR mine=1)
	@test -n "$(users)$(if $(filter 1,$(mine)),me)" || { printf 'Provide users="a,b" or mine=1.\n' >&2; exit 1; }
	@$(GH) issue-assign --issue "$(issue)" $(if $(filter 1,$(mine)),--mine) $(if $(users),--users "$(users)")

issue-unassign: ## Remove assignees from an issue (make issue-unassign issue=N users="a,b" OR mine=1)
	$(call need,issue,make issue-unassign issue=123 users="octocat" OR mine=1)
	@test -n "$(users)$(if $(filter 1,$(mine)),me)" || { printf 'Provide users="a,b" or mine=1.\n' >&2; exit 1; }
	@$(GH) issue-unassign --issue "$(issue)" $(if $(filter 1,$(mine)),--mine) $(if $(users),--users "$(users)")

issue-close: ## Close an issue (make issue-close issue=N [reason=completed|"not planned"]; COMMENT='...' to say why)
	$(call need,issue,make issue-close issue=123)
	@set -e; \
	set -- --issue "$(issue)" $(if $(reason),--reason "$(reason)"); \
	if [ -n "$$COMMENT" ]; then set -- "$$@" --comment "$$COMMENT"; fi; \
	$(GH) issue-close "$$@"

issue-reopen: ## Reopen a closed issue (make issue-reopen issue=N; COMMENT='...' to say why)
	$(call need,issue,make issue-reopen issue=123)
	@set -e; \
	set -- --issue "$(issue)"; \
	if [ -n "$$COMMENT" ]; then set -- "$$@" --comment "$$COMMENT"; fi; \
	$(GH) issue-reopen "$$@"

issue-develop: ## Create and check out a branch linked to an issue (make issue-develop issue=N [base=branch] [name=branch])
	$(call need,issue,make issue-develop issue=123)
	@$(GH) issue-develop --issue "$(issue)" $(if $(base),--base "$(base)") $(if $(name),--name "$(name)")
