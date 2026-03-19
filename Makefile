PYTHON ?= python3.12
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
VENV_PLAYWRIGHT := $(VENV)/bin/playwright
VENV_RUFF := $(VENV)/bin/ruff
NPM ?= npm

.PHONY: install lock node-install setup-base browser-install browser-install-ci setup setup-ci lint lint-js test test-js coverage-js security validate thumbnails index site generate new check align-tables clean

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

lint:
	$(VENV_RUFF) check scripts tests
	$(MAKE) lint-js

lint-js:
	$(NPM) run lint

test:
	$(VENV_PYTHON) -m pytest
	$(MAKE) test-js

test-js:
	$(NPM) run test

coverage-js:
	$(NPM) run test:coverage

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

check: lint test validate

align-tables:
	$(PYTHON) scripts/align_tables.py

clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache build dist *.egg-info node_modules
