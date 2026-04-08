from __future__ import annotations

import functools
import json
import re
from pathlib import Path

_CONTRACT_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "artifact_contract.json"


@functools.lru_cache(maxsize=1)
def _load_contract() -> dict[str, str]:
    """Load and cache the shared artifact contract from ``config/artifact_contract.json``."""
    contract = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
    return contract


def _artifact_id_re() -> re.Pattern[str]:
    """Return the compiled artifact id regex from the shared contract."""
    return re.compile(_load_contract()["artifactIdPattern"])


def _artifact_base_path() -> str:
    """Return the artifact base path from the shared contract."""
    return _load_contract()["artifactBasePath"]


def _thumbnail_file() -> str:
    """Return the thumbnail filename from the shared contract."""
    return _load_contract()["thumbnailFile"]


APP_RUNTIME_TOP_LEVELS = {"css", "js", "assets"}
APP_SHARED_RUNTIME_MARKERS = (
    Path("css/app.css"),
    Path("js/app.js"),
)
APP_METADATA_FILES = {
    "name.txt",
    "description.txt",
    "tags.txt",
    "tools.txt",
    "README.md",
}
SHARED_APP_RUNTIME_FILES = (
    Path("css/app-tokens.css"),
    Path("css/app-shell.css"),
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
SHARED_APP_INFRA_PATHS = SHARED_APP_RUNTIME_IMPACT_PATHS


def shared_app_runtime_paths(repo_root: Path) -> tuple[Path, ...]:
    """Return shared app runtime files rooted at ``repo_root``."""
    return tuple(
        repo_root / relative_path for relative_path in SHARED_APP_RUNTIME_FILES
    )


def artifact_uses_shared_app_runtime(artifact_dir: Path) -> bool:
    """Return whether one artifact opts into the shared app runtime."""
    return any(
        (artifact_dir / marker).exists() for marker in APP_SHARED_RUNTIME_MARKERS
    )


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
    thumbnail = _thumbnail_file()
    return [
        slug
        for slug in discover_app_slugs(apps_root)
        if not (apps_root / slug / thumbnail).exists()
    ]


def runtime_change_plan(changed_files: list[str]) -> dict[str, object]:
    """Classify runtime-impacting app changes from a changed-file list."""
    changed_slugs: set[str] = set()
    shared_runtime_changed = False

    for filename in changed_files:
        if filename in SHARED_APP_RUNTIME_IMPACT_PATHS:
            shared_runtime_changed = True
            continue

        parts = Path(filename).parts
        if len(parts) < 3 or parts[0] != "apps":
            continue

        slug = parts[1]
        if not _artifact_id_re().match(slug):
            continue
        top_level = parts[2]

        if top_level == "index.html" and len(parts) == 3:
            changed_slugs.add(slug)
            continue

        if top_level in APP_RUNTIME_TOP_LEVELS:
            changed_slugs.add(slug)
            continue

        if top_level == "docs":
            continue

        if top_level in APP_METADATA_FILES and len(parts) == 3:
            continue

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
