from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE_TEXT = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")


def test_python_recipes_preserve_the_callers_python_path() -> None:
    """Python recipes extend PYTHONPATH instead of replacing it."""
    assert "PY_PATH_PREFIX = PYTHONPATH=.$${PYTHONPATH:+:$${PYTHONPATH}}" in MAKEFILE_TEXT
    assert "PYTHONPATH=. " not in MAKEFILE_TEXT


def test_markdown_formatting_has_one_non_conflicting_owner() -> None:
    """Prettier and table alignment must not fight over Markdown whitespace."""
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))

    for name in ("format", "format:check"):
        script = package["scripts"][name]
        assert "*.{json,md,yml,yaml}" not in script
        assert "docs/**/*.md" not in script
        assert ".github/**/*.{json,md,yml,yaml,mjs}" not in script

    assert "format-check: format-py-check format-prettier-check align-tables-check" in MAKEFILE_TEXT


def test_free_text_transport_avoids_make_argument_expansion() -> None:
    """Bodies use stdin and short prose uses the environment."""
    assert "NO_TTY_READ := [ -t 0 ] ||" in MAKEFILE_TEXT
    assert "FREE_TEXT_VARS := TITLE COMMENT SEARCH" in MAKEFILE_TEXT
    assert "RETIRED_TEXT_ARGS := body title comment notes search detail" in MAKEFILE_TEXT
    for expression in (
        "$(body)",
        "$(title)",
        "$(comment)",
        "$(search)",
        "$(detail)",
        "$(detail_file)",
        "$(message)",
        "$(message_file)",
    ):
        assert expression not in MAKEFILE_TEXT

    for target in ("pr-comment", "pr-reply", "pr-address", "issue-comment"):
        assert "--body-file -" in target_recipe(target)
    assert "--body-file -" in target_recipe("issue-create")
    assert "--detail-file -" in target_recipe("ci-alert-issue")
    assert "--body-file -" in target_recipe("pr-create")
    assert "$(GH) comment" in target_recipe("pr-comment")


def test_optional_prose_targets_do_not_read_a_terminal() -> None:
    """Optional bodies can be omitted interactively without hanging."""
    for target in ("pr-edit", "issue-edit", "ci-alert-issue"):
        assert "$(NO_TTY_READ)" in target_recipe(target)


def test_commit_requires_a_piped_message() -> None:
    """Commit messages fail fast instead of blocking on an interactive terminal."""
    recipe = target_recipe("commit")
    assert "if [ -t 0 ]; then" in recipe
    assert "Commit message must be provided on stdin." in recipe


def test_comment_delete_uses_a_structured_identifier_name() -> None:
    """A review comment id cannot be confused with free-form comment text."""
    recipe = target_recipe("pr-comment-delete")
    assert "comment_id=PRRC_" in recipe
    assert "$(comment)" not in recipe


# Make joins a trailing backslash to the next line, so a long .PHONY list can be
# wrapped without changing what it declares. Assertions about declarations match
# against this collapsed view so they track behavior rather than line breaks;
# recipe bodies keep using MAKEFILE_TEXT, where the line structure is the point.
MAKEFILE_LOGICAL_LINES = re.sub(r"\\\n[ \t]*", " ", MAKEFILE_TEXT)

# Playwright installs browsers into this user-level cache, which every other
# project on the machine reuses and which is therefore not ours to delete.
SHARED_BROWSER_CACHE = "ms-playwright"

# Targets that lint, format, or scan Python. Their scope comes from the tool's
# own config (CLAUDE.md rules 4 and 5); the Makefile only offers a per-invocation
# paths= override on top of it.
PYTHON_SCOPE_TARGETS = (
    "lint-py",
    "fmt-py",
    "format-py-check",
    "format-py-diff",
    "dead-code-py",
)


def target_recipe(name: str) -> str:
    """Return the recipe lines for one Makefile target."""
    match = re.search(
        rf"^{re.escape(name)}:.*\n(?P<recipe>(?:\t.*\n)+)",
        MAKEFILE_TEXT,
        re.MULTILINE,
    )
    assert match is not None, f"missing Makefile target: {name}"
    return match.group("recipe")


def test_python_scope_targets_keep_the_paths_override() -> None:
    """A per-invocation ``paths=`` still narrows every Python scope target.

    Checked in the recipe, not only in the help text. Advertising ``[paths=...]``
    while the command line has lost ``$(if $(paths),...)`` is the failure worth
    catching, and every command line has to carry it: fmt-py runs two tools, so
    an override on only the first would silently widen the second back to the
    whole tree.
    """
    for target in PYTHON_SCOPE_TARGETS:
        assert re.search(rf"^{re.escape(target)}:.*\[paths=\.\.\.\]", MAKEFILE_TEXT, re.MULTILINE)

        commands = [line for line in target_recipe(target).splitlines() if line.strip()]

        assert commands
        for command in commands:
            assert "$(if $(paths),$(paths)" in command


def test_vulture_scope_comes_from_its_own_config() -> None:
    """dead-code-py passes no default path, so [tool.vulture] owns the scope."""
    recipe = target_recipe("dead-code-py")

    assert "$(if $(paths),$(paths))" in recipe
    assert "pyproject.toml" not in recipe


def test_lock_node_update_bumps_selected_packages_only() -> None:
    """Selected lockfile bumps stay narrow instead of refreshing the whole lockfile."""
    recipe = target_recipe("lock-node-update")

    # Each name becomes its own quoted word, so a value carrying whitespace or a
    # shell metacharacter reaches npm as one package name instead of being split
    # or interpreted by /bin/sh.
    assert '$(NPM) update --package-lock-only $(foreach pkg,$(packages),"$(pkg)")' in recipe
    assert "--package-lock-only $(packages)" not in recipe


def test_lock_node_update_guards_its_required_argument() -> None:
    """The shared need macro prints the usage line when packages= is missing."""
    recipe = target_recipe("lock-node-update")

    assert '$(call need,packages,make lock-node-update packages="package ...")' in recipe


def test_lock_node_update_is_phony_and_documented() -> None:
    """The target joins its section's .PHONY list and carries a help description."""
    assert re.search(r"^\.PHONY:.*\block-node-update\b", MAKEFILE_LOGICAL_LINES, re.MULTILINE)
    assert re.search(r"^lock-node-update:.*## \S", MAKEFILE_TEXT, re.MULTILINE)


def test_clean_keeps_the_shared_playwright_browser_cache() -> None:
    """Make clean removes repository-local state only.

    The browsers live in a user-level cache every project reuses, so a path that
    reached it would cost every other checkout a multi-hundred-megabyte download.
    """
    recipe = target_recipe("clean")

    assert SHARED_BROWSER_CACHE not in recipe
    assert "$(HOME)" not in recipe
    assert "~/" not in recipe


def test_clean_documents_that_it_keeps_shared_browsers() -> None:
    """The intent is stated in the help text, not left implicit in the path list."""
    assert re.search(r"^clean:.*## .*keeps shared Playwright browsers", MAKEFILE_TEXT, re.MULTILINE)


def test_clean_cannot_be_aimed_outside_the_repository() -> None:
    """The only variable path in the rm -rf is confined to the repository.

    Every other entry is a fixed repository-relative literal, so VENV is the one
    way this recipe can be pointed elsewhere. It is set with ?= and make imports
    the environment, so an unrelated exported VENV would otherwise redirect an
    rm -rf into the user's home with no flag and no warning.
    """
    # Pinned as the whole expression rather than its parts. Asserting only that
    # CURDIR and abspath appear would still pass if filter became filter-out,
    # which inverts the guard into deleting exactly the paths it should refuse.
    # The words guard is part of the pin: make splits on whitespace, so without
    # it a VENV holding spaces expands into several separately deleted paths.
    assert (
        "CLEAN_VENV = $(if $(filter 1,$(words $(VENV))),$(filter $(CURDIR)/%,$(abspath $(VENV))))"
        in MAKEFILE_TEXT
    )

    recipe = target_recipe("clean")

    # The guarded value is what gets deleted, quoted so it stays one argument,
    # and the bare one never appears.
    assert 'rm -rf "$(CLEAN_VENV)"' in recipe
    assert "rm -rf $(VENV)" not in recipe
    # An empty result means VENV escaped the repository, so the recipe stops
    # rather than falling through to deleting the remaining shorter paths.
    assert 'test -n "$(CLEAN_VENV)"' in recipe
    assert "exit 1" in recipe


def test_clean_refusal_message_survives_a_quote_in_the_path() -> None:
    """The refusal reaches the operator instead of dying in the shell.

    VENV is the value most likely to be odd, and it is the one interpolated into
    this printf. Single-quoting it turns a path containing an apostrophe into an
    unterminated string, so the operator sees a shell syntax error rather than
    the reason their clean was refused.
    """
    recipe = target_recipe("clean")

    assert '"$(VENV)" "$(CURDIR)"' in recipe
    assert "'$(VENV)'" not in recipe


def test_ci_rerun_replays_a_run_and_can_narrow_to_failed_jobs() -> None:
    """Replaying a run is a first-class target, not a raw gh invocation."""
    recipe = target_recipe("ci-rerun")

    assert 'gh run rerun "$$run_id"' in recipe
    # Without this, a partially green run can only be replayed in full, which
    # re-uploads artifacts the surviving jobs already produced. Gated on the
    # literal 1 like local_libs, so failed=0 reads as off rather than as merely
    # non-empty and therefore on.
    assert "$(if $(filter 1,$(failed)),--failed)" in recipe
    assert "$(if $(failed),--failed)" not in recipe


def test_ci_watch_resolves_a_run_and_surfaces_failure_status() -> None:
    """The CI watcher works in noninteractive shells and returns run failures."""
    recipe = target_recipe("ci-watch")

    assert 'run_id="$(RUN_ID)"' in recipe
    assert 'gh run watch "$$run_id" --exit-status' in recipe
    assert "Usage: make ci-watch run=123456" in recipe
    assert "gh run watch\n" not in recipe


def test_ci_dispatch_starts_a_fresh_run_with_optional_inputs() -> None:
    """A fresh run is the escape hatch when replaying a run cannot work."""
    recipe = target_recipe("ci-dispatch")

    assert 'gh workflow run "$(workflow)"' in recipe
    assert "$(if $(ref),--ref " in recipe
    # Each key=value becomes its own quoted -f, so an input never word-splits.
    assert '$(foreach kv,$(inputs),-f "$(kv)")' in recipe


def test_ci_dispatch_guards_its_required_argument() -> None:
    """The shared need macro prints the usage line when workflow= is missing."""
    assert "$(call need,workflow," in target_recipe("ci-dispatch")


def test_ci_caches_lists_largest_entries_first() -> None:
    """Auditing cache waste starts from the biggest entries, so the sort is pinned."""
    recipe = target_recipe("ci-caches")

    assert "gh cache list" in recipe
    assert "--sort size_in_bytes" in recipe
    assert "--order desc" in recipe


def test_ci_cache_delete_guards_its_required_argument() -> None:
    """Deleting a cache is unrecoverable, so the target refuses an empty target."""
    recipe = target_recipe("ci-cache-delete")

    assert "$(call need,cache," in recipe
    # gh accepts an id or a key in the one positional slot, so a single variable
    # serves both; there is no --key flag to route a key through.
    assert 'gh cache delete "$(cache)"' in recipe
    # A key resolves against the current branch unless a ref disambiguates it,
    # and retired keys usually have one entry per ref that once built them.
    assert '$(if $(ref),--ref "$(ref)")' in recipe


def test_ci_run_targets_are_phony_and_documented() -> None:
    """The CI run helpers stay declared and discoverable through make help."""
    for target in ("ci-rerun", "ci-dispatch", "ci-caches", "ci-cache-delete"):
        assert re.search(rf"^\.PHONY:.*\b{target}\b", MAKEFILE_LOGICAL_LINES, re.MULTILINE)
        assert re.search(rf"^{target}:.*## \S", MAKEFILE_TEXT, re.MULTILINE)
