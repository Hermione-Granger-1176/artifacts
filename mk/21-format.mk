# ─── Format @format ───────────────────────────────────────────────────────────

.PHONY: fmt format fmt-py fmt-js fmt-css fmt-prettier format-check format-py-check format-py-diff format-prettier-check format-prettier-diff align-tables align-tables-check

fmt: fmt-py fmt-js fmt-css fmt-prettier ## Auto-fix all formatting and lint fixes

format: fmt ## Alias for fmt

fmt-py: ## Auto-fix Python (ruff check --fix + ruff format) [paths=...]
	$(VENV_PYTHON) -m ruff check --fix $(if $(paths),$(paths),.)
	$(VENV_PYTHON) -m ruff format $(if $(paths),$(paths),.)

fmt-js: ## Auto-fix JavaScript (eslint --fix)
	$(NPM) run lint:js -- --fix

fmt-css: ## Auto-fix CSS (stylelint --fix)
	$(NPM) run lint:css -- --fix

fmt-prettier: ## Auto-format metadata, workflows, and tooling scripts
	$(NPM) run format

format-check: format-py-check format-prettier-check align-tables-check ## Check Python, Prettier, and Markdown table formatting

format-py-check: ## Check Python formatting only [paths=...]
	$(VENV_PYTHON) -m ruff format --check $(if $(paths),$(paths),.)

format-py-diff: ## Show Python formatting changes without modifying files [paths=...]
	$(VENV_PYTHON) -m ruff format --check --diff $(if $(paths),$(paths),.)

format-prettier-check: ## Check Prettier-managed non-Markdown files only
	$(NPM) run format:check

format-prettier-diff: ## Show Prettier formatting changes without modifying files (make format-prettier-diff path=config/eslint.config.js)
	@test -n "$(path)" || (printf 'Usage: make format-prettier-diff path=config/eslint.config.js\n' >&2; exit 1)
	$(if $(filter %.md %.markdown,$(path)),$(error Markdown formatting is owned by make align-tables-check),)
	@set -e; \
	formatted=$$(mktemp "$${TMPDIR:-/tmp}/artifacts-prettier.XXXXXX"); \
	trap 'rm -f -- "$$formatted"' EXIT; \
	$(NPM) exec --no -- prettier --config config/prettierrc.json --ignore-path config/prettierignore \
		-- "$(path)" > "$$formatted"; \
	diff -u -- "$(path)" "$$formatted" || test $$? -eq 1

align-tables: ## Align markdown table pipes across all docs [paths="README.md docs/example.md"]
	$(VENV_PYTHON) scripts/lint/align_tables.py $(if $(paths),$(paths))

align-tables-check: ## Check markdown table pipe alignment without modifying files [paths="README.md docs/example.md"]
	$(VENV_PYTHON) scripts/lint/align_tables.py --check $(if $(paths),$(paths))
