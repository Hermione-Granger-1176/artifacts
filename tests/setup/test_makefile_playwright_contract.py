from __future__ import annotations

import re
from pathlib import Path

from scripts.lint.make_targets import read_makefile_text

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE_TEXT = read_makefile_text(REPO_ROOT / "Makefile")

LOCAL_RUNTIME = "$(PLAYWRIGHT_LOCAL_RUNTIME)"
LOCAL_RUN = "$(PLAYWRIGHT_LOCAL_RUN)"
BROWSER_TESTS = "$(RUN_BROWSER_TESTS)"

# A recipe launches a browser when it runs a browser test file or the thumbnail
# generator. A recipe that only reads or writes files under tests/browser/
# (such as the visual baselines) does not.
BROWSER_RECIPE_MARKERS = ("tests/browser/test_", "generate_thumbnails.py")


def target_recipe(name: str) -> str:
    """Return the recipe lines for one Makefile target."""
    match = re.search(
        rf"^{re.escape(name)}:.*\n(?P<recipe>(?:\t.*\n)+)",
        MAKEFILE_TEXT,
        re.MULTILINE,
    )
    assert match is not None, f"missing Makefile target: {name}"
    return match.group("recipe")


def browser_launching_targets() -> dict[str, str]:
    """Return every target whose recipe launches a browser, discovered from the Makefile.

    Targets are found by scanning every recipe, so a new browser target is checked
    without being listed here.
    """
    recipes = {
        match.group("name"): match.group("recipe")
        for match in re.finditer(
            r"^(?P<name>[A-Za-z][A-Za-z0-9_-]*):.*\n(?P<recipe>(?:\t.*\n)+)",
            MAKEFILE_TEXT,
            re.MULTILINE,
        )
    }
    return {
        name: recipe
        for name, recipe in recipes.items()
        if any(marker in recipe for marker in BROWSER_RECIPE_MARKERS)
    }


def test_playwright_uses_native_host_detection() -> None:
    """The Makefile has no Playwright platform override.

    The pinned Playwright detects the host platform natively.
    """
    assert "PLAYWRIGHT_HOST_PLATFORM_OVERRIDE" not in MAKEFILE_TEXT
    assert "PLAYWRIGHT_SUPPORTED_UBUNTU" not in MAKEFILE_TEXT


def test_playwright_runtime_is_type_checked() -> None:
    """The setup utility is inside the Python type-check scope."""
    assert re.search(r"^PY_TYPE_PATHS\s*:=\s*scripts/\s*$", MAKEFILE_TEXT, re.MULTILINE)


def test_local_runtime_always_runs_under_the_repository_interpreter() -> None:
    """The local runtime is launched through the repository interpreter, $(VENV_PYTHON).

    The probe re-launches Python through sys.executable. The script does not resolve
    .venv/bin/python itself, because that path is a symlink that the module's
    containment guard rejects.
    """
    assert re.search(
        r"^PLAYWRIGHT_LOCAL_RUNTIME\s*:="
        r"\s*\$\(VENV_PYTHON\)\s+scripts/setup/playwright_local_runtime\.py\s*$",
        MAKEFILE_TEXT,
        re.MULTILINE,
    )


def test_browser_targets_share_one_opt_in_wrapper() -> None:
    """Require local_libs=1 to route browser work through a single wrapper variable."""
    assert (
        "PLAYWRIGHT_LOCAL_RUN = $(if $(filter 1,$(local_libs)),"
        "$(PLAYWRIGHT_LOCAL_RUNTIME) run --,)" in MAKEFILE_TEXT
    )
    assert MAKEFILE_TEXT.count("run --,)") == 1


def test_every_browser_launching_target_inherits_the_wrapper() -> None:
    """Every discovered browser target opts in through the shared wrapper."""
    targets = browser_launching_targets()

    # These targets bypass RUN_BROWSER_TESTS, so the discovery must find them.
    assert {"visual-baselines", "thumbnails", "thumbnails-shard"}.issubset(targets)
    assert any(name.startswith("test-browser-") for name in targets)

    unwrapped = sorted(
        name
        for name, recipe in targets.items()
        if LOCAL_RUN not in recipe and BROWSER_TESTS not in recipe
    )

    assert unwrapped == []


def test_browser_test_helper_runs_under_the_wrapper() -> None:
    """The retry helper wrapping every test-browser-* target inherits the runtime."""
    match = re.search(r"^RUN_BROWSER_TESTS = (?P<value>.+)$", MAKEFILE_TEXT, re.MULTILINE)

    assert match is not None
    assert match.group("value").startswith(LOCAL_RUN)


def test_visual_baselines_wraps_its_direct_pytest_call() -> None:
    """visual-baselines calls pytest directly, so its recipe wraps that call itself."""
    recipe = target_recipe("visual-baselines")

    assert BROWSER_TESTS not in recipe
    assert LOCAL_RUN in recipe


def test_local_setup_targets_never_install_system_packages() -> None:
    """Local browser installation stays sudo-free and package-manager-free."""
    for target in ("setup-playwright", "setup-playwright-webkit"):
        assert "--with-deps" not in target_recipe(target)

    for target in ("setup-playwright-local", "setup-playwright-webkit-local"):
        recipe = target_recipe(target)
        assert "--with-deps" not in recipe
        assert "sudo" not in recipe


def test_ci_setup_targets_keep_system_dependency_installation() -> None:
    """The CI setup targets install system packages with --with-deps."""
    assert "playwright install chromium --with-deps" in target_recipe("setup-playwright-ci")
    assert "playwright install webkit --with-deps" in target_recipe("setup-playwright-webkit-ci")


def test_selected_playwright_setup_validates_engines_and_dependencies() -> None:
    """Keep selective installs constrained to supported engines and dependency mode."""
    recipe = target_recipe("setup-playwright-engines")

    assert "PLAYWRIGHT_BROWSERS := chromium webkit" in MAKEFILE_TEXT
    assert "unsupported Playwright engine(s): $(PLAYWRIGHT_INVALID_ENGINES)" in recipe
    assert "engines must not contain duplicates" in recipe
    assert "with_deps must be one value" in recipe
    assert "with_deps must be 1 when provided" in recipe
    assert "$(if $(filter 1,$(with_deps)),--with-deps)" in recipe
    assert "$(filter $(PLAYWRIGHT_BROWSERS),$(PLAYWRIGHT_ENGINE_ARGS))" in recipe


def test_local_setup_prepares_libraries_around_a_shared_browser_install() -> None:
    """Prepare the private libraries before and after the browser install.

    The second preparation patches the installed WebKit bundle launcher.
    """
    for target, engine in (
        ("setup-playwright-local", "chromium"),
        ("setup-playwright-webkit-local", "webkit"),
    ):
        recipe = target_recipe(target)
        prepare = f"{LOCAL_RUNTIME} prepare --engine {engine}"
        install = f"playwright install {engine}"

        assert recipe.count(prepare) == 2
        assert install in recipe
        assert recipe.index(prepare) < recipe.index(install) < recipe.rindex(prepare)
        # Browsers install into Playwright's shared cache, and the recipe sets
        # no repository-local browser path.
        assert "PLAYWRIGHT_BROWSERS_PATH" not in recipe


def test_webkit_local_setup_extends_rather_than_replaces_the_manifest() -> None:
    """Installing one engine keeps the other engine's library closure.

    Each local target requests only its own engine. The runtime unions that
    request with the recorded engine set.
    """
    webkit_recipe = target_recipe("setup-playwright-webkit-local")

    assert "--engine webkit" in webkit_recipe
    assert "--engine chromium" not in webkit_recipe

    runtime_source = (REPO_ROOT / "scripts/setup/playwright_local_runtime.py").read_text(
        encoding="utf-8"
    )

    assert "def requested_engines(" in runtime_source
    assert "requested_engines(paths, engines)" in runtime_source


def test_local_runtime_lifecycle_targets_are_exposed() -> None:
    """Each lifecycle and gate entry point is reachable through Make."""
    for target, action in (
        ("playwright-local-status", "status"),
        ("playwright-local-gate", "probe"),
        ("playwright-local-clean", "clean"),
    ):
        assert f"{LOCAL_RUNTIME} {action}" in target_recipe(target)


def test_local_runtime_targets_are_documented_in_help() -> None:
    """Each target has a ## description, which make help reads."""
    for target in (
        "setup-playwright-local",
        "setup-playwright-webkit-local",
        "playwright-local-status",
        "playwright-local-gate",
        "playwright-local-clean",
    ):
        assert re.search(rf"^{re.escape(target)}:.*## \S", MAKEFILE_TEXT, re.MULTILINE)


def test_clean_removes_the_repository_local_playwright_cache() -> None:
    """Make clean drops the repository-local Playwright cache along with other caches."""
    assert " .playwright " in target_recipe("clean")


def test_playwright_cache_is_ignored() -> None:
    """The repository-local runtime cache is ignored by git."""
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert ".playwright/" in gitignore
