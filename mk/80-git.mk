# ─── Git @git ─────────────────────────────────────────────────────────────────

.PHONY: git branches branch branch-current switch branch-prune worktree worktree-remove rebase-main merge-main rebase-continue sync-branch squash stage stage-all commit push push-force log log-file diff diff-staged

git: ## Git commands (make git)
	@$(MAKE) --no-print-directory help-git

branches: ## List local and remote branches and worktrees
	git branch -a -vv
	@echo
	git worktree list

branch: ## Create and switch to a new branch off main, or off base for a stacked branch (make branch name=X [base=branch])
	$(call need,name,make branch name=my-feature [base=other-branch])
	git checkout "$(if $(base),$(base),$(MAIN_BRANCH))" && \
	{ ! git rev-parse --symbolic-full-name --abbrev-ref '@{u}' >/dev/null 2>&1 || git pull; } && \
	git checkout -b "$(name)"

branch-current: ## Create and switch to a branch from the current commit without pulling (make branch-current name=X)
	$(call need,name,make branch-current name=my-feature)
	git checkout -b "$(name)"

switch: ## Switch to an existing local branch (make switch name=X)
	$(call need,name,make switch name=my-feature)
	git switch "$(name)"

branch-prune: export PRUNE_MAIN_BRANCH := $(MAIN_BRANCH)
branch-prune: export PRUNE_PAGES_BRANCH := $(PAGES_BRANCH)
branch-prune: export PRUNE_CONFIRM := $(confirm)
branch-prune: ## Prune local branches whose content is already in main (make branch-prune [confirm=1])
	@$(PY_PATH_PREFIX) $(PYTHON) -m scripts.lib.prune_branches

# Worktrees default to .worktrees/<branch>, which git and every lint walker
# already ignore. Slashes are flattened so a branch like fix/x stays one directory.
WORKTREE_PATH = $(if $(path),$(path),.worktrees/$(subst /,-,$(name)))

worktree: ## Create a branch off origin/main, or origin/base, in a new worktree (make worktree name=X [base=branch] [path=DIR])
	$(call need,name,make worktree name=my-feature [base=other-branch] [path=../dir])
	git fetch origin "$(if $(base),$(base),$(MAIN_BRANCH))" && \
	git worktree add --no-track -b "$(name)" "$(WORKTREE_PATH)" "origin/$(if $(base),$(base),$(MAIN_BRANCH))"

worktree-remove: ## Remove a clean worktree created by make worktree; the branch is kept (make worktree-remove name=X [path=DIR])
	$(call need,name,make worktree-remove name=my-feature [path=../dir])
	git worktree remove "$(WORKTREE_PATH)"

rebase-main: ## Rebase the current branch onto origin/main (make rebase-main [base=branch])
	git fetch origin "$(if $(base),$(base),$(MAIN_BRANCH))" && git rebase "origin/$(if $(base),$(base),$(MAIN_BRANCH))"

merge-main: ## Merge origin/main, or origin/base, into the current branch without rewriting history (make merge-main [base=branch])
	git fetch origin "$(if $(base),$(base),$(MAIN_BRANCH))" && git merge --no-edit "origin/$(if $(base),$(base),$(MAIN_BRANCH))"

rebase-continue: ## Continue an in-progress rebase after resolving conflicts
	GIT_EDITOR=true git rebase --continue

sync-branch: ## Rebase the current branch onto its upstream branch
	git pull --rebase

squash: ## Uncommit the current branch's commits since its base and keep the changes staged, ready for make commit (make squash [base=branch])
	git fetch origin "$(if $(base),$(base),$(MAIN_BRANCH))" && git reset --soft "$$(git merge-base HEAD "origin/$(if $(base),$(base),$(MAIN_BRANCH))")"

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
