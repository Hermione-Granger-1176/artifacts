from __future__ import annotations

from pathlib import Path

from scripts.lib.artifact_contract import (
    artifact_base_path,
    thumbnail_file,
)
from scripts.lib.artifact_contract import (
    artifact_id_pattern as _artifact_id_pattern,
)

__all__ = ["artifact_base_path", "thumbnail_file"]


APP_RUNTIME_TOP_LEVELS = {"js", "assets", "css"}
APP_SHARED_RUNTIME_MARKERS = (Path("js/app.js"),)
APP_METADATA_FILES = {
    "name.txt",
    "description.txt",
    "tags.txt",
    "tools.txt",
    "README.md",
}
SHARED_APP_RUNTIME_FILES = (
    Path("css/style.css"),
    Path("js/app-theme.js"),
)
SHARED_APP_RUNTIME_PATHS = {*(path.as_posix() for path in SHARED_APP_RUNTIME_FILES)}
SHARED_APP_MODULES_DIR = Path("js/modules")
GALLERY_MODULES_DIR = Path("js/modules/gallery")
SHARED_APP_MODULES_PREFIX = f"{SHARED_APP_MODULES_DIR.as_posix()}/"
GALLERY_MODULES_PREFIX = f"{GALLERY_MODULES_DIR.as_posix()}/"
SHARED_APP_BROWSER_TEST_PATHS = {
    "tests/browser/conftest.py",
    "tests/browser/frontend_helpers.py",
    "tests/browser/test_frontend_apps_accessibility.py",
    "tests/browser/test_frontend_apps_browser_flows.py",
    "tests/browser/test_frontend_apps_smoke.py",
}


def is_shared_app_browser_test_path(filename: str) -> bool:
    """Return whether a path changes the shared mature-app browser suite."""
    return filename in SHARED_APP_BROWSER_TEST_PATHS


def is_shared_app_runtime_path(filename: str) -> bool:
    """Return whether one repo-relative path is part of the shared app runtime."""
    if filename in SHARED_APP_RUNTIME_PATHS:
        return True
    return filename.startswith(SHARED_APP_MODULES_PREFIX) and not filename.startswith(
        GALLERY_MODULES_PREFIX
    )


def shared_app_runtime_paths(repo_root: Path) -> tuple[Path, ...]:
    """Return shared app runtime files rooted at ``repo_root``."""
    gallery_root = repo_root / GALLERY_MODULES_DIR
    module_files = sorted(
        path
        for path in (repo_root / SHARED_APP_MODULES_DIR).rglob("*")
        if path.is_file() and not path.is_relative_to(gallery_root)
    )
    return (
        *(repo_root / relative_path for relative_path in SHARED_APP_RUNTIME_FILES),
        *module_files,
    )


def artifact_uses_shared_app_runtime(artifact_dir: Path) -> bool:
    """Return whether one artifact opts into the shared app runtime."""
    return any((artifact_dir / marker).exists() for marker in APP_SHARED_RUNTIME_MARKERS)


def discover_app_slugs(apps_root: Path = Path("apps")) -> list[str]:
    """Return app slugs for directories with an ``index.html`` entry point."""
    if not apps_root.exists():
        return []

    return sorted(
        path.name
        for path in apps_root.iterdir()
        if path.is_dir() and (path / "index.html").exists()
    )


def missing_thumbnail_slugs(apps_root: Path = Path("apps")) -> list[str]:
    """Return app slugs that are missing their thumbnail file."""
    thumbnail = thumbnail_file()
    return [
        slug
        for slug in discover_app_slugs(apps_root)
        if not (apps_root / slug / thumbnail).exists()
    ]


def _runtime_changed_slug(filename: str) -> str | None:
    """Return the changed app slug when one path affects runtime behavior."""
    parts = Path(filename).parts
    if len(parts) < 3 or parts[0] != "apps":
        return None

    slug = parts[1]
    if not _artifact_id_pattern().match(slug):
        return None

    top_level = parts[2]
    if top_level == "docs":
        return None
    if top_level in APP_METADATA_FILES and len(parts) == 3:
        return None
    if top_level == "index.html" and len(parts) == 3:
        return slug
    if top_level in APP_RUNTIME_TOP_LEVELS:
        return slug
    return None


def full_impact_plan() -> dict[str, object]:
    """Return the conservative impact plan used when comparison data is unavailable."""
    return {
        "app_scope": "all",
        "browser_scope": "all",
        "thumbnail_scope": "all",
        "static_checks_scope": "all",
        "deploy_scope": "all",
        "changed_slugs": [],
        "runtime_changed": True,
        "browser_changed": True,
        "thumbnail_changed": True,
        "shared_runtime_changed": True,
        "shared_browser_test_changed": False,
    }


def runtime_change_plan(changed_files: list[str]) -> dict[str, object]:
    """Classify changed files into independent browser and thumbnail impact axes."""
    changed_slugs: set[str] = set()
    shared_runtime_changed = False
    shared_browser_test_changed = False

    for filename in changed_files:
        if is_shared_app_runtime_path(filename):
            shared_runtime_changed = True
            continue

        if is_shared_app_browser_test_path(filename):
            shared_browser_test_changed = True
            continue

        slug = _runtime_changed_slug(filename)
        if slug is not None:
            changed_slugs.add(slug)

    thumbnail_scope = "none"
    if shared_runtime_changed:
        thumbnail_scope = "all"
    elif changed_slugs:
        thumbnail_scope = "changed"

    browser_scope = "none"
    if shared_runtime_changed or shared_browser_test_changed:
        browser_scope = "all"
    elif changed_slugs:
        browser_scope = "changed"

    runtime_changed = shared_runtime_changed or bool(changed_slugs)

    return {
        # app_scope remains for the thumbnail persistence interface. New callers
        # must use the independent browser_scope and thumbnail_scope fields.
        "app_scope": thumbnail_scope,
        "browser_scope": browser_scope,
        "thumbnail_scope": thumbnail_scope,
        "static_checks_scope": "all" if changed_files else "none",
        "deploy_scope": "all" if changed_files else "none",
        "changed_slugs": sorted(changed_slugs),
        "runtime_changed": runtime_changed,
        "browser_changed": browser_scope != "none",
        "thumbnail_changed": thumbnail_scope != "none",
        "shared_runtime_changed": shared_runtime_changed,
        "shared_browser_test_changed": shared_browser_test_changed,
    }
