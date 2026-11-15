# ─── Typecheck @typecheck ─────────────────────────────────────────────────────

.PHONY: typecheck typecheck-py typecheck-web

# Python source tree that mypy strict-checks. Tests are intentionally excluded.
PY_TYPE_PATHS := scripts/

typecheck: typecheck-py typecheck-web ## Run all type checks

typecheck-py: ## Run mypy strict type checking over scripts/ [paths on stdin]
	@$(STDIN_PATHS) $(PY_TYPE_PATHS) -- $(VENV_PYTHON) -m mypy

typecheck-web: ## Run TypeScript checkJs over js/ and apps/*/js/
	$(NPM) run typecheck:web
