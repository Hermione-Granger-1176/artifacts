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


APP_RUNTIME_TOP_LEVELS = {"js", "assets"}
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
    Path("js/modules/app-shell.js"),
)
SHARED_APP_RUNTIME_PATHS = {*(path.as_posix() for path in SHARED_APP_RUNTIME_FILES)}
SHARED_APP_BROWSER_TEST_PATHS = {
    "tests/browser/frontend_helpers.py",
    "tests/browser/test_frontend_apps_accessibility.py",
    "tests/browser/test_frontend_apps_browser_flows.py",
    "tests/browser/test_frontend_apps_smoke.py",
}
SHARED_APP_RUNTIME_IMPACT_PATHS = SHARED_APP_RUNTIME_PATHS
SHARED_APP_BROWSER_IMPACT_PATHS = {
    *SHARED_APP_RUNTIME_PATHS,
    *SHARED_APP_BROWSER_TEST_PATHS,
}


def shared_app_runtime_paths(repo_root: Path) -> tuple[Path, ...]:
    """Return shared app runtime files rooted at ``repo_root``."""
    return tuple(repo_root / relative_path for relative_path in SHARED_APP_RUNTIME_FILES)


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


def runtime_change_plan(changed_files: list[str]) -> dict[str, object]:
    """Classify runtime-impacting app changes from a changed-file list."""
    changed_slugs: set[str] = set()
    shared_runtime_changed = False

    for filename in changed_files:
        if filename in SHARED_APP_RUNTIME_IMPACT_PATHS:
            shared_runtime_changed = True
            continue

        slug = _runtime_changed_slug(filename)
        if slug is not None:
            changed_slugs.add(slug)

    app_scope = "none"
    if shared_runtime_changed:
        app_scope = "all"
    elif changed_slugs:
        app_scope = "changed"

    return {
        "app_scope": app_scope,
        "changed_slugs": sorted(changed_slugs),
        "runtime_changed": shared_runtime_changed or bool(changed_slugs),
        "shared_runtime_changed": shared_runtime_changed,
    }
