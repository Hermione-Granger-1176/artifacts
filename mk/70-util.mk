# ─── Utilities @util ──────────────────────────────────────────────────────────

.PHONY: status clean help help-json

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
