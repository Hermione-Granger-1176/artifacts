PYTHON ?= python3.12
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
VENV_PLAYWRIGHT := $(VENV)/bin/playwright
VENV_RUFF := $(VENV)/bin/ruff

.PHONY: install browser-install browser-install-ci setup setup-ci lint test thumbnails index site generate check clean

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

thumbnails:
	$(VENV_PYTHON) scripts/generate_thumbnails.py

index:
	$(VENV_PYTHON) scripts/generate_index.py

site:
	$(VENV_PYTHON) scripts/prepare_site.py

generate:
	$(MAKE) thumbnails
	$(MAKE) index

check: lint test

clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache build dist *.egg-info
