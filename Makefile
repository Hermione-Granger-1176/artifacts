.DEFAULT_GOAL := help

# ─── Variables ────────────────────────────────────────────────────────────────

# Prefer python3.12, then 3.13 or 3.14, then python3.
# Override by passing PYTHON=... on the command line or in the environment.
PYTHON      ?= $(shell command -v python3.12 || command -v python3.13 || command -v python3.14 || command -v python3)
UV          ?= uv
UVX         ?= uvx
VENV        ?= .venv
VENV_PYTHON := $(VENV)/bin/python
NPM         ?= npm

# Shared branch names. Override on the command line or in the environment.
MAIN_BRANCH  ?= main
PAGES_BRANCH ?= gh-pages

# Prefix Python commands with the repository root, keeping any PYTHONPATH already set.
PY_PATH_PREFIX = PYTHONPATH=.$${PYTHONPATH:+:$${PYTHONPATH}}

# Browser targets opt into the private Linux runtime only with local_libs=1.
# Browsers install into Playwright's shared cache. The extracted shared libraries
# and per-run scratch live below the ignored .playwright cache. The wrapper
# refuses to download packages mid-run.
PLAYWRIGHT_LOCAL_RUNTIME := $(VENV_PYTHON) scripts/setup/playwright_local_runtime.py
PLAYWRIGHT_LOCAL_RUN = $(if $(filter 1,$(local_libs)),$(PLAYWRIGHT_LOCAL_RUNTIME) run --,)

# Entry point for the GitHub PR and CI helpers. Make targets are thin wrappers
# around it.
GH = $(PY_PATH_PREFIX) $(VENV_PYTHON) -m scripts.gh.cli

# ─── Free text ────────────────────────────────────────────────────────────────
#
# Bodies arrive on standard input. A title, search term, or close comment
# arrives through the environment:
#
#     TITLE='Fix the retry loop' make issue-create < issue.md
#     SEARCH='is:open label:bug' make issue-list
#     COMMENT='Resolved in the latest deploy' make issue-close issue=7
#
# Free-text variables given as make arguments are refused. Use the environment or stdin.
NO_TTY_READ := [ -t 0 ] ||
FREE_TEXT_VARS := TITLE COMMENT SEARCH
$(foreach v,$(FREE_TEXT_VARS),$(if $(filter command line,$(origin $(v))),$(error \
$(v) was passed as a make argument, which make expands; use $(v)='...' make <target>)))

RETIRED_TEXT_ARGS := body title comment notes search detail \
body_file message message_file notes_file detail_file
$(foreach v,$(RETIRED_TEXT_ARGS),$(if $(filter command line,$(origin $(v))),$(error \
$(v)= is no longer an argument: body and other prose arrive on stdin, while a title, search term, or close comment comes from the environment)))

# ─── Paths ────────────────────────────────────────────────────────────────────
#
# Targets that take files read paths on stdin, one per line:
#
#     make stage <<'EOF'
#     My Notes.md
#     apps/loan-amortization/js/app.js
#     EOF
#
# Without stdin, a check covers its default scope. The helper runs each command
# without a shell, one argument per path.
STDIN_PATHS = $(PY_PATH_PREFIX) $(PYTHON) -m scripts.lib.stdin_paths

RETIRED_PATH_ARGS := files file paths path src
$(foreach v,$(RETIRED_PATH_ARGS),$(if $(filter command line,$(origin $(v))),$(error \
$(v)= is no longer an argument: pass paths on stdin, one per line (make <target> <<'EOF' then one path per line, then EOF))))

# Fail with a usage line when a required variable is empty.
# Usage: $(call need,varname,make switch name=my-feature)
define need
@test -n "$($(1))" || { printf 'Usage: %s\n' '$(2)' >&2; exit 1; }
endef

# ─── Command groups ───────────────────────────────────────────────────────────
#
# Each `make help` group lives in its own mk/NN-<group>.mk file, with its
# targets and the variables only that group uses. The number sets the group
# order in `make help`, and a new file is picked up without editing this one.
include $(sort $(wildcard mk/*.mk))
