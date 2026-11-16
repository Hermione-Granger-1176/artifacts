# ─── Test @test ───────────────────────────────────────────────────────────────

.PHONY: test test-py test-ci test-ci-workflows test-js test-browser test-browser-root test-browser-root-smoke test-browser-root-accessibility test-browser-root-flows test-browser-apps test-browser-apps-smoke test-browser-apps-accessibility test-browser-apps-flows test-browser-apps-shard test-browser-webkit-smoke test-visual visual-baselines visual-baselines-from-ci test-browser-live test-page-speed coverage-js coverage-js-floors

# Browser targets run through the retry-once helper in scripts/ci. BROWSER_ARGS
# passes an optional ARGS= tail (e.g. -k filters), honored only when given on the
# make command line.
RUN_BROWSER_TESTS = $(PLAYWRIGHT_LOCAL_RUN) $(VENV_PYTHON) -m scripts.ci.run_browser_tests
BROWSER_ARGS = $(if $(filter command line,$(origin ARGS)),$(ARGS))

test: test-py test-js ## Run non-browser Python tests + JS tests

# Honor ARGS only when given on the make command line.
test-py: ## Run Python tests except tests/browser, with coverage (pass ARGS="-k name --no-cov" for a subset)
	$(VENV_PYTHON) -m pytest --ignore=tests/browser $(if $(filter command line,$(origin ARGS)),$(ARGS))

test-ci: ## Run CI Python tests only
	$(VENV_PYTHON) -m pytest --no-cov tests/ci

test-ci-workflows: ## Run GitHub workflow contract tests only
	$(VENV_PYTHON) -m pytest --no-cov tests/ci/test_workflow_contracts.py

test-js: ## Run JS tests only (pass ARGS="--test-name-pattern name" for a subset)
	$(NPM) run test -- $(if $(filter command line,$(origin ARGS)),$(ARGS))

test-browser: test-browser-root test-browser-apps ## Run all browser tests (needs Chromium)

test-browser-root: test-browser-root-smoke test-browser-root-accessibility test-browser-root-flows ## Run all root gallery browser tests

test-browser-root-smoke: ## Run root gallery smoke browser tests (pass ARGS="-k name" for a subset)
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_smoke.py $(BROWSER_ARGS)

test-browser-root-accessibility: ## Run root gallery accessibility browser tests (pass ARGS="-k name" for a subset)
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_accessibility.py $(BROWSER_ARGS)

test-browser-root-flows: ## Run root gallery browser-flow tests (pass ARGS="-k name" for a subset)
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_browser_flows.py $(BROWSER_ARGS)

test-browser-apps: ## Run all mature app browser tests in one shared test process (pass ARGS="-k name")
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_apps_smoke.py tests/browser/test_frontend_apps_accessibility.py tests/browser/test_frontend_apps_browser_flows.py $(BROWSER_ARGS)

test-browser-apps-smoke: ## Run mature app smoke browser tests (pass ARGS="-k name" for a subset)
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_apps_smoke.py $(BROWSER_ARGS)

test-browser-apps-accessibility: ## Run mature app accessibility browser tests (pass ARGS="-k name" for a subset)
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_apps_accessibility.py $(BROWSER_ARGS)

test-browser-apps-flows: ## Run mature app browser-flow tests (pass ARGS="-k name" for a subset)
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_apps_browser_flows.py $(BROWSER_ARGS)

test-browser-apps-shard: ## Run one app-browser shard (make test-browser-apps-shard shard_manifest=PATH [ARGS="-k name"])
	$(call need,shard_manifest,make test-browser-apps-shard shard_manifest=.artifacts/shard-manifest.json)
	$(RUN_BROWSER_TESTS) --env ARTIFACTS_BROWSER_APP_MANIFEST="$(shard_manifest)" tests/browser/test_frontend_apps_smoke.py tests/browser/test_frontend_apps_accessibility.py tests/browser/test_frontend_apps_browser_flows.py $(BROWSER_ARGS)

test-browser-webkit-smoke: ## Run the WebKit cross-engine smoke pass (root + apps, needs WebKit) (pass ARGS="-k name")
	$(RUN_BROWSER_TESTS) --env ARTIFACTS_BROWSER_ENGINE=webkit tests/browser/test_frontend_webkit_smoke.py $(BROWSER_ARGS)

test-visual: ## Compare hero screenshots against committed baselines (needs Chromium) (pass ARGS="-k name")
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_visual.py $(BROWSER_ARGS)

visual-baselines: ## Regenerate hero screenshot baselines on this host, for a local comparison only (needs Chromium)
	ARTIFACTS_UPDATE_VISUAL_BASELINES=1 ARTIFACTS_REQUIRE_BROWSER_TESTS=1 $(PLAYWRIGHT_LOCAL_RUN) $(VENV_PYTHON) -m pytest --no-cov tests/browser/test_frontend_visual.py

# The committed baselines match what CI's pinned Playwright image renders. A CI
# run that fails the comparison uploads its captures in the root-browser failure
# artifact. This target adopts those captures as the new baselines.
visual-baselines-from-ci: ## Replace the visual baselines with the captures a CI run uploaded (make visual-baselines-from-ci [run=ID], defaults to this branch's latest)
	@run_id="$(RUN_ID)"; \
	test -n "$$run_id" || { printf 'Usage: make visual-baselines-from-ci run=123456 (or run on a branch with a resolvable latest run)\n' >&2; exit 1; }; \
	tmp=$$(mktemp -d "$${TMPDIR:-/tmp}/artifacts-visual.XXXXXX"); \
	trap 'rm -rf -- "$$tmp"' EXIT; \
	gh run download "$$run_id" --name "root-browser-artifacts-$$run_id" --dir "$$tmp"; \
	test -d "$$tmp/visual-baselines" || { printf 'Run %s uploaded no visual captures; the comparison passed or did not run.\n' "$$run_id" >&2; exit 1; }; \
	cp -- "$$tmp"/visual-baselines/*.png tests/browser/baselines/; \
	printf 'Adopted CI captures from run %s:\n' "$$run_id"; \
	ls -1 "$$tmp/visual-baselines"

test-browser-live: ## Run live-site browser verification (pass ARGS="-k name" for a subset)
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_live.py $(BROWSER_ARGS)

test-page-speed: ## Time the gallery and each app to ready in Chromium against a budget (make test-page-speed [budget_ms=N] [runs=N])
	$(RUN_BROWSER_TESTS) $(if $(budget_ms),--env ARTIFACTS_PAGE_SPEED_BUDGET_MS="$(budget_ms)") $(if $(runs),--env ARTIFACTS_PAGE_SPEED_RUNS="$(runs)") tests/browser/test_frontend_page_speed.py -rP $(BROWSER_ARGS)

coverage-js: ## Run JS tests with coverage enforcement (emits .artifacts/js-coverage.lcov) [COVERAGE_OUTPUT=path]
	@mkdir -p .artifacts
	@if [ -n "$(COVERAGE_OUTPUT)" ]; then \
		bash -o pipefail -c '$(NPM) run test:coverage | tee "$(COVERAGE_OUTPUT)"'; \
	else \
		$(NPM) run test:coverage; \
	fi

coverage-js-floors: ## Enforce per-file JS coverage floors (reads the coverage-js lcov, else reruns the suite)
	$(NPM) run coverage:files
