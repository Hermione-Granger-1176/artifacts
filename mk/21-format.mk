# ─── Format @format ───────────────────────────────────────────────────────────

.PHONY: fmt format fmt-py fmt-js fmt-css fmt-prettier format-check format-py-check format-py-diff format-prettier-check format-prettier-diff align-tables align-tables-check

fmt: fmt-py fmt-js fmt-css fmt-prettier ## Auto-fix all formatting and lint fixes

format: fmt ## Alias for fmt

fmt-py: ## Auto-fix Python (ruff check --fix + ruff format) [paths on stdin]
	@$(STDIN_PATHS) . -- $(VENV_PYTHON) -m ruff check --fix --then $(VENV_PYTHON) -m ruff format

fmt-js: ## Auto-fix JavaScript (eslint --fix)
	$(NPM) run lint:js -- --fix

fmt-css: ## Auto-fix CSS (stylelint --fix)
	$(NPM) run lint:css -- --fix

fmt-prettier: ## Auto-format metadata, workflows, and tooling scripts
	$(NPM) run format

format-check: format-py-check format-prettier-check align-tables-check ## Check Python, Prettier, and Markdown table formatting

format-py-check: ## Check Python formatting only [paths on stdin]
	@$(STDIN_PATHS) . -- $(VENV_PYTHON) -m ruff format --check

format-py-diff: ## Show Python formatting changes without modifying files [paths on stdin]
	@$(STDIN_PATHS) . -- $(VENV_PYTHON) -m ruff format --check --diff

format-prettier-check: ## Check Prettier-managed non-Markdown files only
	$(NPM) run format:check

format-prettier-diff: ## Show Prettier formatting changes without modifying files (paths on stdin, required)
	@$(STDIN_PATHS) --require --name "make format-prettier-diff" -- $(VENV_PYTHON) -m scripts.lint.format_prettier_diff --runner "$(NPM) exec --no --"

align-tables: ## Align markdown table pipes across all docs [paths on stdin]
	@$(STDIN_PATHS) -- $(VENV_PYTHON) scripts/lint/align_tables.py

align-tables-check: ## Check markdown table pipe alignment without modifying files [paths on stdin]
	@$(STDIN_PATHS) -- $(VENV_PYTHON) scripts/lint/align_tables.py --check
