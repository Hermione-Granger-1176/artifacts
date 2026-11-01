# ─── Dead code @deadcode ──────────────────────────────────────────────────────

.PHONY: dead-code dead-code-py dead-code-js

dead-code: dead-code-py dead-code-js ## Detect unused Python and JavaScript code

dead-code-py: ## Detect unused Python code with vulture [paths=...]
	$(VENV_PYTHON) -m vulture $(if $(paths),$(paths))

dead-code-js: ## Detect unused JavaScript files, exports, and dependencies
	$(NPM) run dead-code
