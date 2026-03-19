PYTHON ?= python3.12
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
VENV_PLAYWRIGHT := $(VENV)/bin/playwright
VENV_RUFF := $(VENV)/bin/ruff

.PHONY: install browser-install browser-install-ci setup setup-ci lint test validate thumbnails index site generate new check clean

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PIP) install -e ".[dev]"

browser-install: install
	$(VENV_PLAYWRIGHT) install chromium

browser-install-ci: install
	$(VENV_PLAYWRIGHT) install chromium --with-deps

setup: browser-install

setup-ci: browser-install-ci

lint:
	$(VENV_RUFF) check scripts tests

test:
	$(VENV_PYTHON) -m pytest

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
	rm -rf $(VENV) .pytest_cache .ruff_cache build dist *.egg-info
