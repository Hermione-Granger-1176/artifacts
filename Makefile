PYTHON ?= python3.12
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
VENV_PLAYWRIGHT := $(VENV)/bin/playwright
VENV_RUFF := $(VENV)/bin/ruff
NPM ?= npm

.PHONY: install lock node-install setup-base browser-install browser-install-ci setup setup-ci lint lint-js test test-js validate thumbnails index site generate new check clean

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PIP) install -r locks/requirements-dev.lock
	$(VENV_PIP) install --no-deps -e .

lock:
	$(PYTHON) -m venv /tmp/artifacts-runtime-lock-venv
	$(PYTHON) -m venv /tmp/artifacts-dev-lock-venv
	/tmp/artifacts-runtime-lock-venv/bin/pip install --upgrade pip
	/tmp/artifacts-dev-lock-venv/bin/pip install --upgrade pip
	/tmp/artifacts-runtime-lock-venv/bin/pip install -e .
	/tmp/artifacts-dev-lock-venv/bin/pip install -e ".[dev]"
	/tmp/artifacts-runtime-lock-venv/bin/pip freeze --exclude-editable > locks/requirements.lock
	/tmp/artifacts-dev-lock-venv/bin/pip freeze --exclude-editable > locks/requirements-dev.lock
	rm -rf /tmp/artifacts-runtime-lock-venv
	rm -rf /tmp/artifacts-dev-lock-venv

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

clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache build dist *.egg-info node_modules
