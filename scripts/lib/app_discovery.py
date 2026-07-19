from __future__ import annotations

import re
from pathlib import Path

from scripts.lib.artifact_contract import (
    artifact_base_path,
    thumbnail_file,
)
from scripts.lib.artifact_contract import (
    artifact_id_pattern as _artifact_id_pattern,
)
from scripts.lib.path_validation import reject_symlinks

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
GLOBAL_APP_RUNTIME_PATHS = {
    "css/style.css",
    "js/app-theme.js",
    "js/modules/app-shell.js",
}
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
SCRIPT_TAG_PATTERN = re.compile(r"<script\b[^>]*>", re.IGNORECASE)
MODULE_TYPE_PATTERN = re.compile(r"(?<![\w-])type\s*=\s*[\"']module[\"']", re.IGNORECASE)
SCRIPT_SRC_PATTERN = re.compile(r"(?<![\w-])src\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
ESM_IMPORT_PATTERN = re.compile(
    r"(?<![\w$])(?:import|export)\s+(?:[^;]*?\s+from\s+)?[\"']([^\"']+)[\"']",
    re.DOTALL,
)


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


def is_global_app_runtime_path(filename: str) -> bool:
    """Return whether one shared path must always fan out to every app."""
    return filename in GLOBAL_APP_RUNTIME_PATHS


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


def _repo_relative_path(path: Path, repo_root: Path) -> str | None:
    """Return a repo-relative POSIX path when ``path`` is inside ``repo_root``."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None


def _local_import_path(importer: Path, specifier: str, repo_root: Path) -> Path | None:
    """Resolve one relative static import without following paths outside the repository."""
    clean_specifier = specifier.split("?", 1)[0].split("#", 1)[0]
    if not clean_specifier or clean_specifier.startswith(("http://", "https://", "//")):
        return None
    candidate = (
        (repo_root / clean_specifier.lstrip("/"))
        if clean_specifier.startswith("/")
        else (importer.parent / clean_specifier)
    )
    resolved = candidate.resolve()
    if _repo_relative_path(resolved, repo_root) is None:
        return None
    return resolved


def _script_sources(index_path: Path, repo_root: Path) -> list[Path]:
    """Return local module script files referenced by one app index page.

    Classic scripts (vendor bundles, app-theme) cannot statically import shared
    modules, so only ``type="module"`` tags seed the dependency traversal.
    """
    if index_path.is_symlink():
        raise ValueError(f"Refusing to read symlinked app index: {index_path}")
    content = index_path.read_text(encoding="utf-8")
    sources: list[Path] = []
    for tag in SCRIPT_TAG_PATTERN.findall(content):
        if not MODULE_TYPE_PATTERN.search(tag):
            continue
        src_match = SCRIPT_SRC_PATTERN.search(tag)
        if src_match is None:
            continue
        source = _local_import_path(index_path, src_match.group(1), repo_root)
        if source is not None:
            sources.append(source)
    return sources


def _module_imports(js_path: Path, repo_root: Path) -> list[Path]:
    """Return local static ES module imports from one JavaScript file."""
    if js_path.is_symlink():
        raise ValueError(f"Refusing to read symlinked app module: {js_path}")
    content = js_path.read_text(encoding="utf-8")
    return [
        source
        for specifier in ESM_IMPORT_PATTERN.findall(content)
        if (source := _local_import_path(js_path, specifier, repo_root)) is not None
    ]


def shared_module_consumers(repo_root: Path = Path()) -> dict[str, set[str]]:
    """Map shared runtime module paths to every app that statically imports them.

    The traversal begins with script tags in every app index page and follows
    static ESM imports through app-local and shared modules. Dynamic imports
    intentionally remain outside this conservative static graph.
    """
    if repo_root.is_symlink():
        raise ValueError(
            f"Refusing to discover consumers from symlinked repository root: {repo_root}"
        )
    root = repo_root.resolve()
    apps_root = root / artifact_base_path()
    modules_root = root / SHARED_APP_MODULES_DIR
    if apps_root.is_symlink() or modules_root.is_symlink():
        raise ValueError("Refusing to discover consumers from symlinked app runtime inputs")
    if apps_root.exists():
        reject_symlinks(apps_root)
    if modules_root.exists():
        reject_symlinks(modules_root)

    modules: dict[str, set[str]] = {}
    for path in shared_app_runtime_paths(root):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root).as_posix()
        if not relative_path.startswith(SHARED_APP_MODULES_PREFIX):
            continue
        modules[relative_path] = set()

    for slug in discover_app_slugs(apps_root):
        app_dir = apps_root / slug
        app_js_root = (app_dir / "js").resolve()
        pending = _script_sources(app_dir / "index.html", root)
        visited: set[Path] = set()
        while pending:
            js_path = pending.pop()
            if js_path in visited or not js_path.is_file():
                continue
            relative = _repo_relative_path(js_path, root)
            if relative is None:
                continue
            visited.add(js_path)
            if relative in modules:
                modules[relative].add(slug)

            in_app_js = js_path.is_relative_to(app_js_root)
            in_shared_modules = js_path.is_relative_to(modules_root)
            if in_app_js or in_shared_modules:
                pending.extend(_module_imports(js_path, root))

    return modules


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
        "shared_module_changed": True,
        "shared_browser_test_changed": False,
    }


def runtime_change_plan(changed_files: list[str], *, repo_root: Path = Path()) -> dict[str, object]:
    """Classify changed files into independent browser and thumbnail impact axes."""
    changed_slugs: set[str] = set()
    changed_shared_modules: set[str] = set()
    shared_runtime_changed = False
    shared_browser_test_changed = False

    for filename in changed_files:
        if is_global_app_runtime_path(filename):
            shared_runtime_changed = True
            continue

        if is_shared_app_runtime_path(filename):
            changed_shared_modules.add(filename)
            continue

        if is_shared_app_browser_test_path(filename):
            shared_browser_test_changed = True
            continue

        slug = _runtime_changed_slug(filename)
        if slug is not None:
            changed_slugs.add(slug)

    shared_module_consumers_by_path: dict[str, set[str]] = {}
    if changed_shared_modules and not shared_runtime_changed:
        try:
            shared_module_consumers_by_path = shared_module_consumers(repo_root)
        except (OSError, ValueError):
            # A partial dependency graph could skip a consumer. Expand instead.
            shared_runtime_changed = True
        else:
            for module_path in changed_shared_modules:
                consumers = shared_module_consumers_by_path.get(module_path, set())
                if not consumers:
                    # Unknown or unused modules are intentionally fail-open.
                    shared_runtime_changed = True
                    break
                changed_slugs.update(consumers)

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

    runtime_changed = shared_runtime_changed or bool(changed_slugs) or bool(changed_shared_modules)

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
        "shared_module_changed": bool(changed_shared_modules),
        "shared_browser_test_changed": shared_browser_test_changed,
    }
