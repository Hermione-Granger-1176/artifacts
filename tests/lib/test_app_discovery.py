from __future__ import annotations

from pathlib import Path

import scripts.lib.app_discovery as app_discovery
import scripts.lib.artifact_contract as artifact_contract


def test_load_contract_returns_expected_fields() -> None:
    """Test load contract returns expected fields."""
    contract = artifact_contract.load_contract()

    assert "artifactIdPattern" in contract
    assert "artifactBasePath" in contract
    assert "thumbnailFile" in contract
    assert contract["artifactBasePath"] == "apps"
    assert contract["thumbnailFile"] == "thumbnail.webp"


def test_shared_app_runtime_paths_are_rooted(tmp_path: Path) -> None:
    """Test shared app runtime paths are rooted and discover non-gallery modules."""
    modules_dir = tmp_path / "js" / "modules"
    (modules_dir / "gallery").mkdir(parents=True)
    (modules_dir / "app-shell.js").write_text("export {};\n", encoding="utf-8")
    (modules_dir / "chart-theme.js").write_text("export {};\n", encoding="utf-8")
    (modules_dir / "gallery" / "render.js").write_text("export {};\n", encoding="utf-8")

    assert app_discovery.shared_app_runtime_paths(tmp_path) == (
        tmp_path / "css" / "style.css",
        tmp_path / "js" / "app-theme.js",
        modules_dir / "app-shell.js",
        modules_dir / "chart-theme.js",
    )


def test_artifact_uses_shared_app_runtime_detects_local_entrypoints(
    tmp_path: Path,
) -> None:
    """Test artifact uses shared app runtime detects local entrypoints."""
    artifact_dir = tmp_path / "apps" / "loan-tool"
    artifact_dir.mkdir(parents=True)

    assert app_discovery.artifact_uses_shared_app_runtime(artifact_dir) is False

    (artifact_dir / "css").mkdir()
    (artifact_dir / "css" / "app.css").write_text(".page {}\n", encoding="utf-8")
    assert app_discovery.artifact_uses_shared_app_runtime(artifact_dir) is False

    (artifact_dir / "js").mkdir(exist_ok=True)
    (artifact_dir / "js" / "app.js").write_text("export {};\n", encoding="utf-8")
    assert app_discovery.artifact_uses_shared_app_runtime(artifact_dir) is True


def test_is_shared_app_runtime_path_covers_shared_files_and_modules() -> None:
    """Test the shared runtime predicate covers shared files and non-gallery modules."""
    for path in app_discovery.SHARED_APP_RUNTIME_FILES:
        assert app_discovery.is_shared_app_runtime_path(path.as_posix())
    assert app_discovery.is_shared_app_runtime_path("js/modules/chart-theme.js")
    assert not app_discovery.is_shared_app_runtime_path("js/modules/gallery/render.js")
    assert not any(
        app_discovery.is_shared_app_runtime_path(path)
        for path in app_discovery.SHARED_APP_BROWSER_TEST_PATHS
    )


def test_discover_and_missing_thumbnail_helpers(tmp_path: Path) -> None:
    """Test discover and missing thumbnail helpers."""
    apps_root = tmp_path / "apps"

    assert app_discovery.discover_app_slugs(apps_root) == []

    (apps_root / "beta").mkdir(parents=True)
    (apps_root / "alpha").mkdir(parents=True)
    (apps_root / "alpha" / "index.html").write_text("<html></html>\n", encoding="utf-8")
    (apps_root / "beta" / "index.html").write_text("<html></html>\n", encoding="utf-8")
    (apps_root / "beta" / app_discovery.thumbnail_file()).write_bytes(b"thumb")
    (apps_root / "notes").mkdir()

    assert app_discovery.discover_app_slugs(apps_root) == ["alpha", "beta"]
    assert app_discovery.missing_thumbnail_slugs(apps_root) == ["alpha"]


def test_runtime_change_plan_handles_changed_and_shared_runtime_paths() -> None:
    """Test runtime change plan handles changed and shared runtime paths."""
    plan = app_discovery.runtime_change_plan(
        [
            "README.md",
            "apps/not-kebab slug/index.html",
            "apps/loan-tool/docs/verification.md",
            "apps/loan-tool/name.txt",
            "apps/loan-tool/index.html",
            "apps/loan-tool/js/app.js",
            "apps/budget-tool/assets/chart.json",
            "apps/budget-tool/css/app.css",
            "js/modules/chart-theme.js",
        ]
    )

    assert plan == {
        "app_scope": "all",
        "changed_slugs": ["budget-tool", "loan-tool"],
        "runtime_changed": True,
        "shared_runtime_changed": True,
    }


def test_runtime_change_plan_returns_none_for_non_runtime_changes() -> None:
    """Test runtime change plan returns none for non runtime changes."""
    assert app_discovery.runtime_change_plan(
        [
            "README.md",
            "apps/loan-tool/docs/verification.md",
            "apps/loan-tool/tags.txt",
            "js/modules/gallery/render.js",
        ]
    ) == {
        "app_scope": "none",
        "changed_slugs": [],
        "runtime_changed": False,
        "shared_runtime_changed": False,
    }


def test_runtime_change_plan_ignores_browser_test_only_changes() -> None:
    """Test runtime change plan ignores browser test only changes."""
    assert app_discovery.runtime_change_plan(
        [
            "tests/browser/frontend_helpers.py",
            "tests/browser/test_frontend_apps_smoke.py",
        ]
    ) == {
        "app_scope": "none",
        "changed_slugs": [],
        "runtime_changed": False,
        "shared_runtime_changed": False,
    }
