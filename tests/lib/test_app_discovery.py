from __future__ import annotations

from pathlib import Path

import pytest

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
    assert app_discovery.is_shared_app_browser_test_path(
        "tests/browser/test_frontend_apps_smoke.py"
    )
    assert not app_discovery.is_shared_app_browser_test_path("tests/browser/test_frontend_smoke.py")


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
        "app_scope": "changed",
        "browser_scope": "changed",
        "thumbnail_scope": "changed",
        "static_checks_scope": "all",
        "deploy_scope": "all",
        "changed_slugs": [
            "bond-price-vs-rate",
            "budget-tool",
            "loan-amortization",
            "loan-tool",
            "prompt-caching",
            "tokenizer-explorer",
        ],
        "runtime_changed": True,
        "browser_changed": True,
        "thumbnail_changed": True,
        "shared_runtime_changed": False,
        "shared_module_changed": True,
        "shared_browser_test_changed": False,
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
        "browser_scope": "none",
        "thumbnail_scope": "none",
        "static_checks_scope": "all",
        "deploy_scope": "all",
        "changed_slugs": [],
        "runtime_changed": False,
        "browser_changed": False,
        "thumbnail_changed": False,
        "shared_runtime_changed": False,
        "shared_module_changed": False,
        "shared_browser_test_changed": False,
    }


def test_runtime_change_plan_scopes_browser_test_only_changes_to_all_apps() -> None:
    """Test runtime change plan reruns all browser apps without thumbnail work."""
    assert app_discovery.runtime_change_plan(
        [
            "tests/browser/frontend_helpers.py",
            "tests/browser/test_frontend_apps_smoke.py",
        ]
    ) == {
        "app_scope": "none",
        "browser_scope": "all",
        "thumbnail_scope": "none",
        "static_checks_scope": "all",
        "deploy_scope": "all",
        "changed_slugs": [],
        "runtime_changed": False,
        "browser_changed": True,
        "thumbnail_changed": False,
        "shared_runtime_changed": False,
        "shared_module_changed": False,
        "shared_browser_test_changed": True,
    }


def test_full_impact_plan_fails_closed_to_every_app_axis() -> None:
    """Test unavailable comparisons select every app impact axis."""
    assert app_discovery.full_impact_plan() == {
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


def test_shared_module_consumers_follows_nested_local_modules(tmp_path: Path) -> None:
    """Shared module consumers include apps reached through nested local imports."""
    modules = tmp_path / "js" / "modules"
    modules.mkdir(parents=True)
    (modules / "chart-theme.js").write_text("export const color = 'blue';\n", encoding="utf-8")
    (modules / "unused.js").write_text("export const unused = true;\n", encoding="utf-8")
    for slug in ("alpha", "beta"):
        app_dir = tmp_path / "apps" / slug
        (app_dir / "js" / "nested").mkdir(parents=True)
        (app_dir / "index.html").write_text(
            '<script type="module" src="./js/app.js"></script>\n', encoding="utf-8"
        )
        (app_dir / "js" / "app.js").write_text('import "./nested/feature.js";\n', encoding="utf-8")
        (app_dir / "js" / "nested" / "feature.js").write_text(
            'import "../../../../js/modules/chart-theme.js";\n', encoding="utf-8"
        )

    consumers = app_discovery.shared_module_consumers(tmp_path)

    assert consumers["js/modules/chart-theme.js"] == {"alpha", "beta"}
    assert consumers["js/modules/unused.js"] == set()


def test_shared_module_consumers_only_seed_from_module_scripts(tmp_path: Path) -> None:
    """Classic script tags and srcless module tags never seed the ESM traversal."""
    modules = tmp_path / "js" / "modules"
    modules.mkdir(parents=True)
    (modules / "chart-theme.js").write_text("export {};\n", encoding="utf-8")
    app_dir = tmp_path / "apps" / "alpha"
    (app_dir / "js" / "vendor").mkdir(parents=True)
    (app_dir / "index.html").write_text(
        '<script defer src="./js/vendor/bundle.js"></script>\n'
        '<script data-type="module" src="./js/vendor/bundle.js"></script>\n'
        '<script type="module">console.log("inline");</script>\n'
        '<script type="module" data-src="./js/vendor/bundle.js"></script>\n'
        '<script type="module" src="https://cdn.example.com/remote.js"></script>\n'
        '<script type = "module" src = "../../outside-roots.js"></script>\n',
        encoding="utf-8",
    )
    (app_dir / "js" / "vendor" / "bundle.js").write_text(
        'import "../../../../js/modules/chart-theme.js";\n', encoding="utf-8"
    )
    (tmp_path / "outside-roots.js").write_text(
        'import "./js/modules/chart-theme.js";\n', encoding="utf-8"
    )

    assert app_discovery.shared_module_consumers(tmp_path) == {"js/modules/chart-theme.js": set()}


def test_runtime_change_plan_scopes_shared_modules_to_consumers(tmp_path: Path) -> None:
    """A narrowly used shared module scopes both runtime axes to its consumers."""
    modules = tmp_path / "js" / "modules"
    modules.mkdir(parents=True)
    (modules / "chart-theme.js").write_text("export {};\n", encoding="utf-8")
    for slug in ("alpha", "beta"):
        app_dir = tmp_path / "apps" / slug
        (app_dir / "js").mkdir(parents=True)
        (app_dir / "index.html").write_text(
            '<script type="module" src="./js/app.js"></script>\n', encoding="utf-8"
        )
        (app_dir / "js" / "app.js").write_text(
            'import "../../../js/modules/chart-theme.js";\n', encoding="utf-8"
        )

    plan = app_discovery.runtime_change_plan(
        ["apps/gamma/js/app.js", "js/modules/chart-theme.js"], repo_root=tmp_path
    )

    assert plan["browser_scope"] == "changed"
    assert plan["thumbnail_scope"] == "changed"
    assert plan["changed_slugs"] == ["alpha", "beta", "gamma"]
    assert plan["shared_runtime_changed"] is False
    assert plan["shared_module_changed"] is True


def test_runtime_change_plan_fails_open_for_global_or_unconsumed_modules(tmp_path: Path) -> None:
    """Global and unconsumed shared modules conservatively fan out to every app."""
    modules = tmp_path / "js" / "modules"
    modules.mkdir(parents=True)
    (modules / "unused.js").write_text("export {};\n", encoding="utf-8")

    global_plan = app_discovery.runtime_change_plan(["js/modules/app-shell.js"], repo_root=tmp_path)
    unused_plan = app_discovery.runtime_change_plan(["js/modules/unused.js"], repo_root=tmp_path)

    assert global_plan["browser_scope"] == "all"
    assert unused_plan["browser_scope"] == "all"
    assert unused_plan["thumbnail_scope"] == "all"


def test_import_helpers_ignore_external_and_outside_paths(tmp_path: Path) -> None:
    """Static import parsing keeps only local files within the repository root."""
    importer = tmp_path / "apps" / "alpha" / "js" / "app.js"
    importer.parent.mkdir(parents=True)
    importer.write_text("export {};\n", encoding="utf-8")

    assert app_discovery._repo_relative_path(tmp_path.parent / "outside.js", tmp_path) is None
    assert (
        app_discovery._local_import_path(importer, "https://example.com/app.js", tmp_path) is None
    )
    assert app_discovery._local_import_path(importer, "", tmp_path) is None
    assert app_discovery._local_import_path(importer, "../../../../outside.js", tmp_path) is None
    assert app_discovery._local_import_path(importer, "/js/root.js?cache=1#fragment", tmp_path) == (
        tmp_path / "js" / "root.js"
    )


def test_import_helpers_reject_symlinked_sources(tmp_path: Path) -> None:
    """App script and module parsers reject symlinks before reading their source text."""
    target = tmp_path / "target.js"
    target.write_text("export {};\n", encoding="utf-8")
    index = tmp_path / "index.html"
    index.symlink_to(target)
    module = tmp_path / "module.js"
    module.symlink_to(target)

    with pytest.raises(ValueError, match="symlinked app index"):
        app_discovery._script_sources(index, tmp_path)
    with pytest.raises(ValueError, match="symlinked app module"):
        app_discovery._module_imports(module, tmp_path)


def test_shared_module_consumers_rejects_symlinked_roots_and_handles_missing_modules(
    tmp_path: Path,
) -> None:
    """Consumer discovery rejects unsafe roots and tolerates an empty module directory."""
    target = tmp_path / "target"
    target.mkdir()
    apps_link = tmp_path / "apps"
    apps_link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinked app runtime"):
        app_discovery.shared_module_consumers(tmp_path)

    apps_link.unlink()
    (tmp_path / "apps").mkdir()
    assert app_discovery.shared_module_consumers(tmp_path) == {}

    linked_root = tmp_path.parent / f"{tmp_path.name}-linked-root"
    linked_root.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinked repository root"):
        app_discovery.shared_module_consumers(linked_root)


def test_runtime_change_plan_fails_open_when_consumer_discovery_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dependency graph errors conservatively expand a shared module change to all apps."""
    monkeypatch.setattr(
        app_discovery,
        "shared_module_consumers",
        lambda _root: (_ for _ in ()).throw(OSError("unreadable graph")),
    )

    plan = app_discovery.runtime_change_plan(["js/modules/chart-theme.js"])

    assert plan["browser_scope"] == "all"
    assert plan["shared_runtime_changed"] is True


def test_shared_module_consumers_skips_paths_without_repo_relative_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A defensive traversal ignores a queued path that cannot map to the repository."""
    modules = tmp_path / "js" / "modules"
    modules.mkdir(parents=True)
    (modules / "chart-theme.js").write_text("export {};\n", encoding="utf-8")
    app_dir = tmp_path / "apps" / "alpha"
    (app_dir / "js").mkdir(parents=True)
    (app_dir / "index.html").write_text("<html></html>\n", encoding="utf-8")
    app_file = app_dir / "js" / "app.js"
    app_file.write_text("export {};\n", encoding="utf-8")
    monkeypatch.setattr(app_discovery, "_script_sources", lambda *_args: [app_file])
    monkeypatch.setattr(app_discovery, "_repo_relative_path", lambda *_args: None)

    assert app_discovery.shared_module_consumers(tmp_path) == {"js/modules/chart-theme.js": set()}
