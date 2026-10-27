# ─── Test @test ───────────────────────────────────────────────────────────────

.PHONY: test test-py test-ci test-ci-workflows test-js test-browser test-browser-root test-browser-root-smoke test-browser-root-accessibility test-browser-root-flows test-browser-apps test-browser-apps-smoke test-browser-apps-accessibility test-browser-apps-flows test-browser-apps-shard test-browser-webkit-smoke test-visual visual-baselines test-browser-live coverage-js coverage-js-floors

# Browser targets run through the tested retry-once helper so the flaky-report
# policy lives in scripts/ instead of inline shell. BROWSER_ARGS threads an
# optional ARGS= tail (e.g. -k filters), honored only when passed on the make
# command line so a stray ARGS environment variable cannot change the gate.
RUN_BROWSER_TESTS = $(PLAYWRIGHT_LOCAL_RUN) $(VENV_PYTHON) -m scripts.ci.run_browser_tests
BROWSER_ARGS = $(if $(filter command line,$(origin ARGS)),$(ARGS))

test: test-py test-js ## Run non-browser Python tests + JS tests

# Honor ARGS only when given on the make command line, so a stray ARGS
# environment variable cannot silently change what the test gate runs.
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

visual-baselines: ## Regenerate committed hero screenshot baselines (needs Chromium)
	ARTIFACTS_UPDATE_VISUAL_BASELINES=1 ARTIFACTS_REQUIRE_BROWSER_TESTS=1 $(PLAYWRIGHT_LOCAL_RUN) $(VENV_PYTHON) -m pytest --no-cov tests/browser/test_frontend_visual.py

test-browser-live: ## Run live-site browser verification (pass ARGS="-k name" for a subset)
	$(RUN_BROWSER_TESTS) tests/browser/test_frontend_live.py $(BROWSER_ARGS)

coverage-js: ## Run JS tests with coverage enforcement (emits .artifacts/js-coverage.lcov) [COVERAGE_OUTPUT=path]
	@mkdir -p .artifacts
	@if [ -n "$(COVERAGE_OUTPUT)" ]; then \
		bash -o pipefail -c '$(NPM) run test:coverage | tee "$(COVERAGE_OUTPUT)"'; \
	else \
		$(NPM) run test:coverage; \
	fi

coverage-js-floors: ## Enforce per-file JS coverage floors (reads the coverage-js lcov, else reruns the suite)
	$(NPM) run coverage:files
