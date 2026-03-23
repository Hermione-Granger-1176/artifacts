PYTHON ?= python3.12
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
VENV_PLAYWRIGHT := $(VENV)/bin/playwright
VENV_RUFF := $(VENV)/bin/ruff
VENV_YAMLLINT := $(VENV)/bin/yamllint
NPM ?= npm

.PHONY: install lock node-install setup-base browser-install browser-install-ci setup setup-ci setup-local editorconfig-check lint lint-py lint-js lint-css lint-yaml lint-workflows test test-py test-browser test-browser-live test-js coverage-js security validate thumbnails index site generate new check check-local check-web local web align-tables clean

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PIP) install -r locks/requirements-dev.lock
	$(VENV_PIP) install --no-deps -e .

lock:
	@runtime_dir=$$(mktemp -d) && dev_dir=$$(mktemp -d) && \
	trap 'rm -rf "$$runtime_dir" "$$dev_dir"' EXIT && \
	$(PYTHON) -m venv "$$runtime_dir" && \
	$(PYTHON) -m venv "$$dev_dir" && \
	"$$runtime_dir/bin/pip" install --upgrade pip && \
	"$$dev_dir/bin/pip" install --upgrade pip && \
	"$$runtime_dir/bin/pip" install -e . && \
	"$$dev_dir/bin/pip" install -e ".[dev]" && \
	"$$runtime_dir/bin/pip" freeze --exclude-editable > locks/requirements.lock && \
	"$$dev_dir/bin/pip" freeze --exclude-editable > locks/requirements-dev.lock

node-install:
	$(NPM) ci

setup-base: install node-install

browser-install: setup-base
	$(VENV_PLAYWRIGHT) install chromium

browser-install-ci: setup-base
	$(VENV_PLAYWRIGHT) install chromium --with-deps

setup: browser-install

setup-ci: browser-install-ci

setup-local: setup-base

editorconfig-check:
	$(PYTHON) scripts/check_editorconfig.py

lint:
	$(MAKE) editorconfig-check
	$(MAKE) lint-py
	$(MAKE) lint-js
	$(MAKE) lint-css
	$(MAKE) lint-yaml
	$(MAKE) lint-workflows

lint-py:
	$(VENV_RUFF) check scripts tests

lint-js:
	$(NPM) run lint:js

lint-css:
	$(NPM) run lint:css

lint-yaml:
	$(VENV_YAMLLINT) -c .yamllint.yml .github .yamllint.yml

lint-workflows:
	$(NPM) run lint:workflows

test:
	$(MAKE) test-py
	$(MAKE) test-js

test-py:
	$(VENV_PYTHON) -m pytest --ignore=tests/test_frontend_smoke.py --ignore=tests/test_frontend_accessibility.py --ignore=tests/test_frontend_browser_flows.py --ignore=tests/test_frontend_live.py

test-browser:
	ARTIFACTS_REQUIRE_BROWSER_TESTS=1 $(VENV_PYTHON) -m pytest --no-cov tests/test_frontend_smoke.py tests/test_frontend_accessibility.py tests/test_frontend_browser_flows.py

test-browser-live:
	ARTIFACTS_REQUIRE_BROWSER_TESTS=1 $(VENV_PYTHON) -m pytest --no-cov tests/test_frontend_live.py

test-js:
	$(NPM) run test

coverage-js:
	@if [ -n "$(COVERAGE_OUTPUT)" ]; then \
		bash -o pipefail -c '$(NPM) run test:coverage | tee "$(COVERAGE_OUTPUT)"'; \
	else \
		$(NPM) run test:coverage; \
	fi

security:
	$(VENV_PYTHON) -m pip_audit --requirement locks/requirements-dev.lock
	$(NPM) audit

validate:
	$(PYTHON) -c "from scripts.generate_index import validate; validate()"

thumbnails:
	$(VENV_PYTHON) scripts/generate_thumbnails.py

index:
	$(PYTHON) scripts/generate_index.py

site:
	$(PYTHON) scripts/prepare_site.py

generate:
	$(MAKE) thumbnails
	$(MAKE) index

new:
	@test -n "$(name)" || (printf 'Usage: make new name=my-artifact\n' >&2; exit 1)
	$(PYTHON) scripts/scaffold_artifact.py "$(name)"

check-local:
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) coverage-js
	$(MAKE) security
	$(MAKE) validate

check-web:
	$(MAKE) test-browser
	$(MAKE) thumbnails

local: check-local

web: check-web

check: check-local web
	$(MAKE) index
	$(MAKE) site

align-tables:
	$(PYTHON) scripts/align_tables.py

clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache build dist *.egg-info node_modules
