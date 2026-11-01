# ─── Setup @setup ─────────────────────────────────────────────────────────────

.PHONY: install node-install install-hooks setup-base setup setup-all setup-ci ci-prune-uv-cache playwright-version setup-playwright setup-playwright-ci setup-playwright-engines setup-playwright-webkit setup-playwright-webkit-ci setup-playwright-local setup-playwright-webkit-local playwright-local-status playwright-local-gate playwright-local-clean

PLAYWRIGHT_BROWSERS := chromium webkit
PLAYWRIGHT_ENGINE_ARGS = $(subst -, ,$(strip $(engines)))
PLAYWRIGHT_INVALID_ENGINES = $(filter-out $(PLAYWRIGHT_BROWSERS),$(PLAYWRIGHT_ENGINE_ARGS))

install: ## Install locked Python deps into the virtual environment
	UV_PROJECT_ENVIRONMENT=$(VENV) $(UV) sync --all-groups --frozen --python $(PYTHON)

node-install: ## Install locked Node deps
	$(NPM) ci

install-hooks: ## Install local pre-commit Git hooks
	$(UVX) pre-commit install

setup-base: install node-install ## Install Python and Node deps

setup: setup-base ## Install Python and Node deps (fast, no Chromium)

setup-all: setup-base setup-playwright ## Full setup including Chromium for browser tests

setup-ci: setup-base setup-playwright-ci ## CI variant with Chromium system deps

ci-prune-uv-cache: ## Remove uv cache entries that are inefficient to persist in CI
	$(UV) cache prune --ci

playwright-version: ## Print the installed Playwright package version
	@$(VENV_PYTHON) -c "import importlib.metadata; print(importlib.metadata.version('playwright'))"

setup-playwright: ## Install Chromium for browser tests
	$(VENV)/bin/playwright install chromium

setup-playwright-ci: ## Install Chromium with system deps
	$(VENV)/bin/playwright install chromium --with-deps

# Used by the ci-setup action, which keys its browser cache on the engine set so
# a restored entry always holds exactly the engines the job asked for. Engines
# arrive hyphen-separated (chromium-webkit) because the value is part of a cache
# key; no supported engine name contains a hyphen, so splitting on it is
# unambiguous. Validation below rejects malformed or unsupported values.
setup-playwright-engines: ## Install named Playwright engines (make setup-playwright-engines engines=chromium-webkit [with_deps=1])
	$(call need,engines,make setup-playwright-engines engines=chromium-webkit [with_deps=1])
	$(if $(filter-out 1,$(words $(strip $(engines)))),$(error engines must be one hyphen-separated value),)
	$(if $(filter -% %-,$(strip $(engines))),$(error engines must not start or end with a hyphen),)
	$(if $(findstring --,$(strip $(engines))),$(error engines must not contain empty names),)
	$(if $(PLAYWRIGHT_INVALID_ENGINES),$(error unsupported Playwright engine(s): $(PLAYWRIGHT_INVALID_ENGINES)),)
	$(if $(filter-out $(words $(sort $(PLAYWRIGHT_ENGINE_ARGS))),$(words $(PLAYWRIGHT_ENGINE_ARGS))),$(error engines must not contain duplicates),)
	$(if $(filter-out 0 1,$(words $(strip $(with_deps)))),$(error with_deps must be one value),)
	$(if $(filter-out 1,$(strip $(with_deps))),$(error with_deps must be 1 when provided),)
	$(VENV)/bin/playwright install $(if $(filter 1,$(with_deps)),--with-deps) $(filter $(PLAYWRIGHT_BROWSERS),$(PLAYWRIGHT_ENGINE_ARGS))

setup-playwright-webkit: ## Install WebKit for the cross-engine smoke pass
	$(VENV)/bin/playwright install webkit

setup-playwright-webkit-ci: ## Install WebKit with system deps
	$(VENV)/bin/playwright install webkit --with-deps

# The two local targets share one manifest. Preparing an engine extends the
# recorded engine set instead of replacing it, so the extracted package closure
# stays the union Chromium and WebKit both need and installing one engine never
# strands the other. Preparing again after the browser install patches the shared
# WebKit launcher so it appends the inherited library path.
setup-playwright-local: ## Install Chromium and the private Ubuntu/Debian runtime without sudo
	$(PLAYWRIGHT_LOCAL_RUNTIME) prepare --engine chromium
	PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 $(VENV)/bin/playwright install chromium
	$(PLAYWRIGHT_LOCAL_RUNTIME) prepare --engine chromium

setup-playwright-webkit-local: ## Install WebKit and extend the private runtime to its libraries
	$(PLAYWRIGHT_LOCAL_RUNTIME) prepare --engine webkit
	PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 $(VENV)/bin/playwright install webkit
	$(PLAYWRIGHT_LOCAL_RUNTIME) prepare --engine webkit

playwright-local-status: ## Show repository-local Playwright runtime status
	$(PLAYWRIGHT_LOCAL_RUNTIME) status

playwright-local-gate: ## Launch every prepared engine in the private runtime
	$(PLAYWRIGHT_LOCAL_RUNTIME) probe

playwright-local-clean: ## Remove only the repository-local Playwright cache (keeps shared browsers)
	$(PLAYWRIGHT_LOCAL_RUNTIME) clean
