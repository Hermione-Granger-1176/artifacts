# ─── Git @git ─────────────────────────────────────────────────────────────────

.PHONY: git branches branch branch-current switch branch-prune worktree worktree-remove rebase-main merge-main branch-restart merge-branch apply-patch merge-abort resolve-ours resolve-theirs rebase-continue sync-branch squash squash-onto stage stage-all commit push push-force log log-file diff diff-staged diff-base

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
WORKTREE_PATH = $(if $(dir),$(dir),.worktrees/$(subst /,-,$(name)))

worktree: ## Create a branch off origin/main, or origin/base, in a new worktree (make worktree name=X [base=branch] [dir=DIR])
	$(call need,name,make worktree name=my-feature [base=other-branch] [dir=../dir])
	git fetch origin "$(if $(base),$(base),$(MAIN_BRANCH))" && \
	git worktree add --no-track -b "$(name)" "$(WORKTREE_PATH)" "origin/$(if $(base),$(base),$(MAIN_BRANCH))"

worktree-remove: ## Remove a clean worktree created by make worktree; the branch is kept (make worktree-remove name=X [dir=DIR])
	$(call need,name,make worktree-remove name=my-feature [dir=../dir])
	git worktree remove "$(WORKTREE_PATH)"

rebase-main: ## Rebase the current branch onto origin/main (make rebase-main [base=branch])
	git fetch origin "$(if $(base),$(base),$(MAIN_BRANCH))" && git rebase "origin/$(if $(base),$(base),$(MAIN_BRANCH))"

merge-main: ## Merge origin/main, or origin/base, into the current branch without rewriting history (make merge-main [base=branch])
	git fetch origin "$(if $(base),$(base),$(MAIN_BRANCH))" && git merge --no-edit "origin/$(if $(base),$(base),$(MAIN_BRANCH))"

branch-restart: ## Move the current branch onto origin/main, or origin/base, keeping uncommitted changes; for a branch whose PR already merged (make branch-restart [base=branch])
	git fetch origin "$(if $(base),$(base),$(MAIN_BRANCH))" && git reset --keep "origin/$(if $(base),$(base),$(MAIN_BRANCH))"

merge-branch: ## Merge a local or remote-tracking branch into the current branch (make merge-branch name=X)
	$(call need,name,make merge-branch name=my-feature)
	git merge --no-edit "$(name)"

apply-patch: ## Apply a patch from stdin to the working tree and index, merging three ways where it does not apply cleanly (make apply-patch < changes.patch)
	@test ! -t 0 || { printf 'Usage: make apply-patch < changes.patch\n' >&2; exit 1; }
	git apply --3way --index

merge-abort: ## Abandon an in-progress merge and restore the branch to its state before it
	git merge --abort

# Paths arrive on stdin, as in make stage. --literal-pathspecs stops git from
# expanding *.md or :(glob) magic, so git touches exactly the named file. The
# chosen side is checked out first, and nothing is staged if that fails.
resolve-ours: ## During a merge, keep the current branch's side of conflicted files and stage them (paths on stdin)
	@$(STDIN_PATHS) --require --name "make resolve-ours" -- git --literal-pathspecs checkout --ours -- --then git --literal-pathspecs add --

resolve-theirs: ## During a merge, take the incoming side of conflicted files and stage them (paths on stdin)
	@$(STDIN_PATHS) --require --name "make resolve-theirs" -- git --literal-pathspecs checkout --theirs -- --then git --literal-pathspecs add --

rebase-continue: ## Continue an in-progress rebase after resolving conflicts
	GIT_EDITOR=true git rebase --continue

sync-branch: ## Rebase the current branch onto its upstream branch
	git pull --rebase

squash-onto: ## Merge origin/main, or origin/base, then uncommit everything above it and keep the changes staged, ready for make commit as one commit on top of it (make squash-onto [base=branch])
	git fetch origin "$(if $(base),$(base),$(MAIN_BRANCH))" && git merge --no-edit "origin/$(if $(base),$(base),$(MAIN_BRANCH))" && git reset --soft "origin/$(if $(base),$(base),$(MAIN_BRANCH))"

squash: ## Uncommit the current branch's commits since its base and keep the changes staged, ready for make commit (make squash [base=branch])
	git fetch origin "$(if $(base),$(base),$(MAIN_BRANCH))" && git reset --soft "$$(git merge-base HEAD "origin/$(if $(base),$(base),$(MAIN_BRANCH))")"

stage: ## Stage selected files (paths on stdin, one per line)
	@$(STDIN_PATHS) --require --name "make stage" -- git --literal-pathspecs add --

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
	git commit $(if $(filter 1,$(amend)),--amend) -F "$$tmp"

push: ## Push the current branch to origin
	git push -u origin HEAD

push-force: ## Push the current branch to origin after a rebase (uses --force-with-lease)
	git push --force-with-lease -u origin HEAD

log: ## Show recent commit log (make log [limit=N])
	git log --oneline -$(if $(limit),$(limit),20)

log-file: ## Show recent commit log for files (paths on stdin) (make log-file [limit=N])
	@$(STDIN_PATHS) --require --name "make log-file" -- git log --date=short '--pretty=format:%h %ad %s' -$(if $(limit),$(limit),20) --

diff: ## Show unstaged changes [paths on stdin]
	@$(STDIN_PATHS) -- git diff --

diff-staged: ## Show staged changes [paths on stdin]
	@$(STDIN_PATHS) -- git diff --cached --

diff-base: ## Show what the current branch changes against origin/main, or origin/base (make diff-base [base=branch] [stat=1])
	git diff $(if $(filter 1,$(stat)),--stat) "origin/$(if $(base),$(base),$(MAIN_BRANCH))...HEAD"
