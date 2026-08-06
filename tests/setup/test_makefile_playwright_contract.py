from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE_TEXT = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

LOCAL_RUNTIME = "$(PLAYWRIGHT_LOCAL_RUNTIME)"
LOCAL_ENV = "$(PLAYWRIGHT_LOCAL_ENV)"
LOCAL_RUN = "$(PLAYWRIGHT_LOCAL_RUN)"
BROWSER_TESTS = "$(RUN_BROWSER_TESTS)"

# A recipe that names a browser suite or the thumbnail renderer launches a real
# browser and therefore has to inherit the private runtime when local_libs=1.
BROWSER_RECIPE_MARKERS = ("tests/browser/", "generate_thumbnails.py")


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

    Discovering these instead of listing them means a newly added browser target
    cannot silently skip the local-runtime wrapper.
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
    """Do not retain the obsolete Ubuntu platform override workaround.

    Playwright 1.61.x supports this host natively, and a stale override can leave
    the revision cache holding a browser built for another platform archive.
    """
    assert "PLAYWRIGHT_HOST_PLATFORM_OVERRIDE" not in MAKEFILE_TEXT
    assert "PLAYWRIGHT_SUPPORTED_UBUNTU" not in MAKEFILE_TEXT


def test_playwright_runtime_is_type_checked() -> None:
    """Keep the setup utility inside the strict Python type-check scope."""
    assert re.search(r"^PY_TYPE_PATHS\s*:=\s*scripts/\s*$", MAKEFILE_TEXT, re.MULTILINE)


def test_local_runtime_always_runs_under_the_repository_interpreter() -> None:
    """Pin the single entry point that makes sys.executable the Playwright environment.

    The probe re-launches Python through sys.executable, so it imports Playwright
    only because every invocation starts from the virtual-environment interpreter.
    Resolving .venv/bin/python inside the script cannot replace this contract: that
    path is a symlink to the system interpreter, so the module's own containment
    guard would reject it.
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
        "$(PLAYWRIGHT_LOCAL_ENV) $(PLAYWRIGHT_LOCAL_RUNTIME) run --,)" in MAKEFILE_TEXT
    )
    assert MAKEFILE_TEXT.count("run --,)") == 1


def test_every_browser_launching_target_inherits_the_wrapper() -> None:
    """Every discovered browser target opts in through the shared wrapper."""
    targets = browser_launching_targets()

    # Guard the discovery itself: the paths that bypass RUN_BROWSER_TESTS are the
    # ones most likely to be missed, so require them to be found.
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
    """visual-baselines calls pytest directly, so it needs the wrapper of its own."""
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
    """CI stays on Playwright's system-package install on disposable runners."""
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
    """Prepare the private libraries on both sides of a sudo-free browser install.

    The second preparation is what patches the freshly installed WebKit bundle
    launcher, so the ordering is part of the contract.
    """
    for target, engine in (
        ("setup-playwright-local", "chromium"),
        ("setup-playwright-webkit-local", "webkit"),
    ):
        recipe = target_recipe(target)
        prepare = f"{LOCAL_ENV} {LOCAL_RUNTIME} prepare --engine {engine}"
        install = f"playwright install {engine}"

        assert recipe.count(prepare) == 2
        assert install in recipe
        assert recipe.index(prepare) < recipe.index(install) < recipe.rindex(prepare)
        # Browsers land in Playwright's shared cache, so no repository-local
        # browser path is layered onto the install.
        assert "PLAYWRIGHT_BROWSERS_PATH" not in recipe


def test_webkit_local_setup_extends_rather_than_replaces_the_manifest() -> None:
    """Installing one engine must never strand the other's library closure.

    Each local target requests only its own engine; the runtime unions that
    request with the recorded engine set, so the resolved package closure is
    always the union both engines need.
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
    """Keep every lifecycle and real-engine gate entry point discoverable through Make."""
    for target, action in (
        ("playwright-local-status", "status"),
        ("playwright-local-gate", "probe"),
        ("playwright-local-clean", "clean"),
    ):
        assert f"{LOCAL_RUNTIME} {action}" in target_recipe(target)


def test_local_runtime_targets_are_documented_in_help() -> None:
    """Every new target carries the ## comment that drives make help."""
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
    """Never track the repository-local runtime cache."""
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert ".playwright/" in gitignore
