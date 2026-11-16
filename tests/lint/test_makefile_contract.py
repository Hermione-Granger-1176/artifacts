from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from scripts.gh import cli
from scripts.lint.make_targets import read_makefile_text

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE_TEXT = read_makefile_text(REPO_ROOT / "Makefile")


def test_python_recipes_preserve_the_callers_python_path() -> None:
    """Python recipes extend PYTHONPATH instead of replacing it."""
    assert "PY_PATH_PREFIX = PYTHONPATH=.$${PYTHONPATH:+:$${PYTHONPATH}}" in MAKEFILE_TEXT
    assert "PYTHONPATH=. " not in MAKEFILE_TEXT


def test_markdown_formatting_has_one_non_conflicting_owner() -> None:
    """Prettier's format scripts exclude Markdown, which align-tables owns."""
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


GH_TARGET_COMMANDS = {
    "pr-create": "pr-create",
    "pr-list": "pr-list",
    "pr-status": "pr-status",
    "pr-checks": "pr-checks",
    "pr-diff": "pr-diff",
    "pr-checkout": "pr-checkout",
    "pr-comments": "pr-comments",
    "pr-merge": "pr-merge",
    "pr-merge-admin": "pr-merge",
    "pr-reviewers": "pr-reviewers",
    "pr-label": "pr-label",
    "pr-close": "pr-close",
    "issue-list": "issue-list",
    "issue-view": "issue-view",
    "issue-create": "issue-create",
    "issue-comment": "issue-comment",
    "issue-edit": "issue-edit",
    "issue-label": "issue-label",
    "issue-unlabel": "issue-unlabel",
    "issue-assign": "issue-assign",
    "issue-unassign": "issue-unassign",
    "issue-close": "issue-close",
    "issue-reopen": "issue-reopen",
    "issue-develop": "issue-develop",
}


def test_pr_and_issue_targets_use_the_tested_gh_helpers() -> None:
    """Each GitHub target calls its scripts.gh helper subcommand."""
    for target, command in GH_TARGET_COMMANDS.items():
        assert f"$(GH) {command}" in target_recipe(target), target

    assert not re.search(r"^\t[^#\n]*\bgh (?:pr|issue)\b", MAKEFILE_TEXT, re.MULTILINE)
    assert "$(GH) current-pr" in MAKEFILE_TEXT


def test_gh_helper_commands_in_the_makefile_exist() -> None:
    """Every ``$(GH) <command>`` named in the Makefile is a registered helper subcommand."""
    used = set(re.findall(r"\$\(GH\) ([a-z][a-z-]*)", MAKEFILE_TEXT))

    assert used
    assert used <= set(cli.COMMAND_HANDLERS)


def test_thread_targets_accept_a_pr_number_for_numeric_ids() -> None:
    """Reply, resolve, and address pass pr_num to gh, which numeric thread ids require."""
    for target in ("pr-reply", "pr-resolve", "pr-address"):
        assert '$(if $(pr_num),--pr "$(pr_num)")' in target_recipe(target), target


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


# Makefile text with each backslash line continuation joined into one line.
# Declaration checks use this view. Recipe checks use MAKEFILE_TEXT, where the
# line structure matters.
MAKEFILE_LOGICAL_LINES = re.sub(r"\\\n[ \t]*", " ", MAKEFILE_TEXT)

# Playwright's user-level browser cache, shared by every project on the machine.
SHARED_BROWSER_CACHE = "ms-playwright"

# Targets that lint, format, or scan Python. Each tool's own config sets the
# scope. The Makefile only lets a caller narrow it with paths on stdin.
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


def test_python_scope_targets_take_paths_on_stdin() -> None:
    """Each Python scope target takes paths on stdin, and fmt-py passes them to both tools.

    Checks the recipe, not only the help text. Each target is one call to the
    stdin path runner. fmt-py chains its two tools with --then, so both see the
    same paths.
    """
    for target in PYTHON_SCOPE_TARGETS:
        assert re.search(rf"^{re.escape(target)}:.*\[paths on stdin\]", MAKEFILE_TEXT, re.MULTILINE)

        commands = [line for line in target_recipe(target).splitlines() if line.strip()]

        assert len(commands) == 1
        assert commands[0].startswith("\t@$(STDIN_PATHS) ")
    assert "ruff check --fix --then $(VENV_PYTHON) -m ruff format" in target_recipe("fmt-py")


def test_vulture_scope_comes_from_its_own_config() -> None:
    """dead-code-py passes no default path, so [tool.vulture] owns the scope."""
    recipe = target_recipe("dead-code-py")

    assert "@$(STDIN_PATHS) -- $(VENV_PYTHON) -m vulture" in recipe
    assert "pyproject.toml" not in recipe


@pytest.mark.parametrize("variable", ["files", "file", "paths", "path", "src"])
def test_no_recipe_reads_paths_from_a_make_variable(variable: str) -> None:
    """No recipe reads paths from a Make variable, since Make splits and expands them first."""
    assert f"$({variable})" not in MAKEFILE_TEXT
    assert f"$(value {variable})" not in MAKEFILE_TEXT


@pytest.mark.parametrize("variable", ["files", "file", "paths", "path", "src"])
def test_retired_path_arguments_are_refused_rather_than_ignored(variable: str) -> None:
    """A caller still passing paths as an argument gets the stdin form, not a silent no-op."""
    result = subprocess.run(
        ["make", "--no-print-directory", "-n", "stage", f"{variable}=a.txt"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert f"{variable}= is no longer an argument: pass paths on stdin" in result.stderr


@pytest.mark.parametrize(
    ("target", "invocation"),
    [
        ("stage", '--require --name "make stage" -- git --literal-pathspecs add --'),
        (
            "resolve-ours",
            '--require --name "make resolve-ours" -- git --literal-pathspecs checkout --ours -- '
            "--then git --literal-pathspecs add --",
        ),
        (
            "resolve-theirs",
            '--require --name "make resolve-theirs" -- git --literal-pathspecs checkout --theirs '
            "-- --then git --literal-pathspecs add --",
        ),
        ("diff", "-- git diff --"),
        ("diff-staged", "-- git diff --cached --"),
        ("align-tables", "-- $(VENV_PYTHON) scripts/lint/align_tables.py"),
        ("align-tables-check", "-- $(VENV_PYTHON) scripts/lint/align_tables.py --check"),
        ("lint-yaml", ". -- $(VENV)/bin/yamllint"),
        ("typecheck-py", "$(PY_TYPE_PATHS) -- $(VENV_PYTHON) -m mypy"),
        (
            "format-prettier-diff",
            '--require --name "make format-prettier-diff" -- $(VENV_PYTHON) -m '
            'scripts.lint.format_prettier_diff --runner "$(NPM) exec --no --"',
        ),
        ("optimize-social-image", "-- $(VENV_PYTHON) scripts/build/optimize_social_image.py"),
    ],
)
def test_path_targets_read_their_paths_from_stdin(target: str, invocation: str) -> None:
    """Each file-taking target hands its stdin paths to the tool without a shell."""
    assert target_recipe(target).strip() == f"@$(STDIN_PATHS) {invocation}"


def test_apply_patch_reads_the_patch_from_stdin() -> None:
    """The patch arrives on stdin; a terminal gets the usage line instead."""
    recipe = target_recipe("apply-patch")

    assert "test ! -t 0 ||" in recipe
    assert recipe.rstrip().endswith("git apply --3way --index")


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
    """Make clean removes repository-local state only and leaves the shared browser cache.

    The browser cache is user-level and shared, so clean must not touch it.
    """
    recipe = target_recipe("clean")

    assert SHARED_BROWSER_CACHE not in recipe
    assert "$(HOME)" not in recipe
    assert "~/" not in recipe


def test_clean_documents_that_it_keeps_shared_browsers() -> None:
    """The clean help text says it keeps shared Playwright browsers."""
    assert re.search(r"^clean:.*## .*keeps shared Playwright browsers", MAKEFILE_TEXT, re.MULTILINE)


def test_clean_cannot_be_aimed_outside_the_repository() -> None:
    """The only variable path in the rm -rf is confined to the repository.

    Every other entry is a fixed repository-relative literal. VENV is the one
    variable that could point elsewhere, since make imports it from the environment.
    """
    # The whole expression is pinned, not just its parts. Checking only for CURDIR
    # and abspath would also pass if filter were changed to filter-out. The words
    # guard is part of the pin: make splits on whitespace, so a VENV with spaces
    # would expand into several paths.
    assert (
        "CLEAN_VENV = $(if $(filter 1,$(words $(VENV))),$(filter $(CURDIR)/%,$(abspath $(VENV))))"
        in MAKEFILE_TEXT
    )

    recipe = target_recipe("clean")

    # The guarded value is what gets deleted, quoted so it stays one argument,
    # and the bare one never appears.
    assert 'rm -rf "$(CLEAN_VENV)"' in recipe
    assert "rm -rf $(VENV)" not in recipe
    # An empty result means VENV is outside the repository, and the recipe exits
    # instead of deleting the remaining paths.
    assert 'test -n "$(CLEAN_VENV)"' in recipe
    assert "exit 1" in recipe


def test_clean_refusal_message_survives_a_quote_in_the_path() -> None:
    """The clean refusal message quotes VENV, so an apostrophe in the path does not break the shell.

    VENV is the value most likely to be odd, and it is interpolated into this printf.
    """
    recipe = target_recipe("clean")

    assert '"$(VENV)" "$(CURDIR)"' in recipe
    assert "'$(VENV)'" not in recipe


def test_ci_rerun_replays_a_run_and_can_narrow_to_failed_jobs() -> None:
    """ci-rerun replays a run through gh run rerun, optionally only its failed jobs."""
    recipe = target_recipe("ci-rerun")

    assert 'gh run rerun "$$run_id"' in recipe
    # --failed is added only when failed is the literal 1, so failed=0 leaves it off.
    assert "$(if $(filter 1,$(failed)),--failed)" in recipe
    assert "$(if $(failed),--failed)" not in recipe


def test_ci_watch_resolves_a_run_and_surfaces_failure_status() -> None:
    """ci-watch resolves the run id and passes --exit-status to gh run watch."""
    recipe = target_recipe("ci-watch")

    assert 'run_id="$(RUN_ID)"' in recipe
    assert 'gh run watch "$$run_id" --exit-status' in recipe
    assert "Usage: make ci-watch run=123456" in recipe
    assert "gh run watch\n" not in recipe


def test_ci_dispatch_starts_a_fresh_run_with_optional_inputs() -> None:
    """ci-dispatch starts a new workflow run, with an optional ref and inputs."""
    recipe = target_recipe("ci-dispatch")

    assert 'gh workflow run "$(workflow)"' in recipe
    assert "$(if $(ref),--ref " in recipe
    # Each key=value becomes its own quoted -f, so an input never word-splits.
    assert '$(foreach kv,$(inputs),-f "$(kv)")' in recipe


def test_ci_dispatch_guards_its_required_argument() -> None:
    """The shared need macro prints the usage line when workflow= is missing."""
    assert "$(call need,workflow," in target_recipe("ci-dispatch")


def test_ci_caches_lists_largest_entries_first() -> None:
    """ci-caches lists the largest cache entries first."""
    recipe = target_recipe("ci-caches")

    assert "gh cache list" in recipe
    assert "--sort size_in_bytes" in recipe
    assert "--order desc" in recipe


def test_ci_cache_delete_guards_its_required_argument() -> None:
    """ci-cache-delete requires cache= and prints usage without it."""
    recipe = target_recipe("ci-cache-delete")

    assert "$(call need,cache," in recipe
    # gh takes an id or a key in one positional slot, so one variable serves both.
    assert 'gh cache delete "$(cache)"' in recipe
    # A key resolves against the current branch unless ref is given.
    assert '$(if $(ref),--ref "$(ref)")' in recipe


def test_ci_run_targets_are_phony_and_documented() -> None:
    """The CI run helpers stay declared and discoverable through make help."""
    for target in ("ci-rerun", "ci-dispatch", "ci-caches", "ci-cache-delete"):
        assert re.search(rf"^\.PHONY:.*\b{target}\b", MAKEFILE_LOGICAL_LINES, re.MULTILINE)
        assert re.search(rf"^{target}:.*## \S", MAKEFILE_TEXT, re.MULTILINE)


GROUP_FILES = sorted((REPO_ROOT / "mk").glob("*.mk"))
GROUP_TARGET_PATTERN = re.compile(r"^([a-z][a-z0-9-]*):(?!=)", re.MULTILINE)


def test_root_makefile_holds_shared_settings_only() -> None:
    """Targets live in mk/*.mk, so the root Makefile defines none of its own."""
    root_text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert GROUP_FILES
    assert GROUP_TARGET_PATTERN.findall(root_text) == []


def test_each_group_file_opens_with_one_help_group() -> None:
    """Every mk/*.mk file is one `make help` group, named by its header."""
    for path in GROUP_FILES:
        text = path.read_text(encoding="utf-8")
        headers = re.findall(r"^# ─── .+? @[a-z]+ .*$", text, re.MULTILINE)

        assert len(headers) == 1, path.name
        assert text.startswith(headers[0]), path.name


def test_group_file_targets_are_phony() -> None:
    """Each group file declares every target it defines as phony."""
    for path in GROUP_FILES:
        text = path.read_text(encoding="utf-8")
        phony = re.search(r"^\.PHONY: (.+)$", text, re.MULTILINE)

        assert phony, path.name
        assert set(GROUP_TARGET_PATTERN.findall(text)) <= set(phony.group(1).split()), path.name


@pytest.mark.parametrize(
    ("target", "variable", "option"),
    [
        ("pr-create", "TITLE", "--title"),
        ("pr-edit", "TITLE", "--title"),
        ("issue-list", "SEARCH", "--search"),
        ("issue-create", "TITLE", "--title"),
        ("issue-edit", "TITLE", "--title"),
        ("issue-close", "COMMENT", "--comment"),
        ("issue-reopen", "COMMENT", "--comment"),
    ],
)
def test_free_text_reaches_the_helper_as_one_option_equals_value_word(
    target: str, variable: str, option: str
) -> None:
    """Free text is one ``--option=value`` word, so a leading dash is not an option.

    For example, SEARCH='-label:bug' stays the value of --search.
    """
    recipe = target_recipe(target)

    assert f'{option}="$${variable}"' in recipe
    assert f'{option} "$${variable}"' not in recipe
