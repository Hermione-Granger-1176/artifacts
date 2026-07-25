from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE_TEXT = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

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
    """A per-invocation ``paths=`` still narrows every Python scope target."""
    for target in PYTHON_SCOPE_TARGETS:
        assert re.search(rf"^{re.escape(target)}:.*\[paths=\.\.\.\]", MAKEFILE_TEXT, re.MULTILINE)


def test_vulture_scope_comes_from_its_own_config() -> None:
    """dead-code-py passes no default path, so [tool.vulture] owns the scope."""
    recipe = target_recipe("dead-code-py")

    assert "$(if $(paths),$(paths))" in recipe
    assert "pyproject.toml" not in recipe


def test_lock_node_update_bumps_selected_packages_only() -> None:
    """Transitive lockfile bumps stay narrow instead of refreshing the whole lockfile."""
    assert "$(NPM) update --package-lock-only $(packages)" in target_recipe("lock-node-update")


def test_lock_node_update_guards_its_required_argument() -> None:
    """The shared need macro prints the usage line when packages= is missing."""
    recipe = target_recipe("lock-node-update")

    assert '$(call need,packages,make lock-node-update packages="package ...")' in recipe


def test_lock_node_update_is_phony_and_documented() -> None:
    """The target joins its section's .PHONY list and carries a help description."""
    assert re.search(r"^\.PHONY:.*\block-node-update\b", MAKEFILE_TEXT, re.MULTILINE)
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
