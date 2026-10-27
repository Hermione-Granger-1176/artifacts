# ─── Quality gates @quality ───────────────────────────────────────────────────

.PHONY: ci-python ci-web ci ci-fast security audit-python audit-node audit-vendored check-generated check-local check-fast check-web check fix

ci-python: format-py-check lint-py typecheck-py dead-code-py test-py ## Python CI gate

ci-web: editorconfig-check format-prettier-check lint-js lint-css lint-yaml typecheck-web lint-workflows lint-doc-commands lint-make-targets lint-js-test-coverage lint-artifact-csp lint-app-css-tokens lint-vendored-assets check-overrides dead-code-js test-js coverage-js coverage-js-floors ## Web and docs CI gate

ci: ci-python ci-web security validate check-generated ## Full local CI gate without browser tests

# check-generated runs after the parallel batch because it rewrites and
# restores generated files in place, which would race concurrent readers.
ci-fast: ## Run the non-browser CI checks in parallel
	$(VENV_PYTHON) scripts/ci/run_parallel_checks.py format-check lint typecheck test-py coverage-js dead-code security validate
	@$(MAKE) --no-print-directory check-generated

security: audit-python audit-node audit-vendored ## Run dependency audits

audit-python: ## Export locked Python deps and run pip-audit
	mkdir -p .artifacts
	$(UV) export --all-groups --frozen --no-emit-project --format requirements.txt --output-file .artifacts/requirements-audit.txt
	$(VENV_PYTHON) scripts/ci/run_security_audit.py \
		--requirements .artifacts/requirements-audit.txt \
		--pip-audit "$(VENV_PYTHON) -m pip_audit"

audit-node: ## Run policy-driven npm dependency audit with reviewed exceptions
	$(VENV_PYTHON) scripts/ci/run_npm_audit.py --npm "$(NPM)"

audit-vendored: ## Check vendored bundles against OSV advisories with reviewed exceptions
	$(VENV_PYTHON) scripts/ci/audit_vendored_assets.py

check-generated: ## Check canonical generated files are up to date
	$(VENV_PYTHON) scripts/lint/check_generated_drift.py

check-local: ci ## Alias for the full local CI gate

check-fast: ci-fast ## Alias for ci-fast

check-web: test-browser thumbnails ## Browser gate: test-browser + thumbnails

check: check-local check-web index site ## Full gate: check-local + check-web + index + site

fix: fmt check-local ## Auto-fix formatting, then run the full non-browser local gate
