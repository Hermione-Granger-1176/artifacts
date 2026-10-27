# ─── Lint @lint ───────────────────────────────────────────────────────────────

.PHONY: lint editorconfig-check lint-py lint-js lint-css lint-yaml lint-workflows workflow-lint lint-doc-commands lint-make-targets lint-js-test-coverage lint-artifact-csp lint-app-css-tokens lint-vendored-assets check-overrides

lint: editorconfig-check lint-py lint-js lint-css lint-yaml lint-workflows lint-doc-commands lint-make-targets lint-js-test-coverage lint-artifact-csp lint-app-css-tokens lint-vendored-assets check-overrides ## Run all linters

editorconfig-check: ## Check EditorConfig rules
	$(VENV_PYTHON) scripts/lint/check_editorconfig.py

lint-py: ## Run ruff only [paths=...]
	$(VENV_PYTHON) -m ruff check $(if $(paths),$(paths),.)

lint-js: ## Run eslint only
	$(NPM) run lint:js

lint-css: ## Run stylelint only
	$(NPM) run lint:css

lint-yaml: ## Run yamllint only [paths=...]
	$(VENV)/bin/yamllint $(if $(paths),$(paths),.)

lint-workflows: ## Run workflow linter only
	$(NPM) run lint:workflows

workflow-lint: lint-workflows ## Alias for lint-workflows

lint-doc-commands: ## Check contributor docs use Make targets
	$(VENV_PYTHON) scripts/lint/check_doc_commands.py

lint-make-targets: ## Check make target references in docs, CI, and source against the Makefile
	$(VENV_PYTHON) scripts/lint/check_make_targets.py

lint-js-test-coverage: ## Check every JS source file has test imports
	$(VENV_PYTHON) scripts/lint/check_js_test_coverage.py

lint-artifact-csp: ## Check artifact pages ship a strict CSP and no external refs
	$(VENV_PYTHON) scripts/lint/check_artifact_csp.py

lint-app-css-tokens: ## Check app stylesheets stay on shared design tokens
	$(VENV_PYTHON) scripts/lint/check_app_css_tokens.py

lint-vendored-assets: ## Check vendored libraries against the integrity manifest
	$(VENV_PYTHON) scripts/lint/check_vendored_assets.py

check-overrides: ## Check npm overrides are still needed
	$(NPM) run check:overrides
