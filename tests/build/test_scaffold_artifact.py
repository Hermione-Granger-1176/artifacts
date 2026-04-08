from __future__ import annotations

from pathlib import Path

import pytest

import scripts.build.scaffold_artifact as scaffold_artifact


def test_title_from_slug_formats_words() -> None:
    assert scaffold_artifact._title_from_slug("budget-tracker") == "Budget Tracker"


def test_index_template_includes_title() -> None:
    template = scaffold_artifact._index_template("Budget Tracker")

    assert "<title>Budget Tracker | Artifacts</title>" in template
    assert '<html lang="en" data-theme="light">' in template
    assert '<script src="../../js/app-theme.js"></script>' in template
    assert '<link rel="stylesheet" href="../../css/app-tokens.css">' in template
    assert '<link rel="stylesheet" href="../../css/app-shell.css">' in template
    assert '<link rel="stylesheet" href="./css/app.css">' in template
    assert '<script type="module" src="./js/app.js"></script>' in template
    assert 'data-app-shell="header"' in template
    assert 'data-app-shell="runtime-error"' in template
    assert 'data-app-shell="scroll-top"' in template
    assert '<h1 class="page-title">Budget Tracker</h1>' in template


def test_scaffold_artifact_creates_expected_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apps_dir = tmp_path / "apps"
    tests_js_apps_dir = tmp_path / "tests" / "js" / "apps"
    monkeypatch.setattr(scaffold_artifact, "APPS_DIR", apps_dir)
    monkeypatch.setattr(scaffold_artifact, "TESTS_JS_APPS_DIR", tests_js_apps_dir)

    artifact_dir = scaffold_artifact.scaffold_artifact("budget-tracker")

    assert artifact_dir == apps_dir / "budget-tracker"
    assert (artifact_dir / "index.html").exists()
    assert (artifact_dir / "css" / "app.css").exists()
    assert (artifact_dir / "js" / "app.js").exists()
    assert (artifact_dir / "README.md").exists()
    assert (artifact_dir / "docs" / "architecture.md").exists()
    assert (artifact_dir / "docs" / "verification.md").exists()
    assert (artifact_dir / "docs" / "decisions.md").exists()
    assert (tests_js_apps_dir / "budget-tracker").is_dir()
    assert (artifact_dir / "name.txt").read_text(encoding="utf-8") == "Budget Tracker\n"
    assert (artifact_dir / "description.txt").read_text(encoding="utf-8") == "\n"
    assert (artifact_dir / "tags.txt").read_text(encoding="utf-8") == "\n"
    assert (artifact_dir / "tools.txt").read_text(encoding="utf-8") == "\n"

    index_html = (artifact_dir / "index.html").read_text(encoding="utf-8")
    app_css = (artifact_dir / "css" / "app.css").read_text(encoding="utf-8")
    app_js = (artifact_dir / "js" / "app.js").read_text(encoding="utf-8")
    readme = (artifact_dir / "README.md").read_text(encoding="utf-8")

    assert "__APP_THUMBNAIL_URL__" in index_html
    assert '<script type="module" src="./js/app.js"></script>' in index_html
    assert ":root" not in app_css
    assert "renderAppShell();" in app_js
    assert "initAppShell" in app_js
    assert "initializeMatureApp" in app_js
    assert "# Budget Tracker" in readme


def test_scaffold_artifact_rejects_missing_name() -> None:
    with pytest.raises(ValueError, match="Artifact name is required"):
        scaffold_artifact.scaffold_artifact("")


def test_scaffold_artifact_rejects_non_kebab_case_name() -> None:
    with pytest.raises(ValueError, match="Artifact name must use kebab-case"):
        scaffold_artifact.scaffold_artifact("BudgetTracker")


def test_scaffold_artifact_rejects_existing_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apps_dir = tmp_path / "apps"
    artifact_dir = apps_dir / "budget-tracker"
    artifact_dir.mkdir(parents=True)
    monkeypatch.setattr(scaffold_artifact, "APPS_DIR", apps_dir)
    monkeypatch.setattr(
        scaffold_artifact, "TESTS_JS_APPS_DIR", tmp_path / "tests" / "js" / "apps"
    )

    with pytest.raises(FileExistsError, match="Artifact directory already exists"):
        scaffold_artifact.scaffold_artifact("budget-tracker")


def test_main_scaffolds_artifact_and_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    apps_dir = tmp_path / "apps"
    monkeypatch.setattr(scaffold_artifact, "APPS_DIR", apps_dir)
    monkeypatch.setattr(
        scaffold_artifact, "TESTS_JS_APPS_DIR", tmp_path / "tests" / "js" / "apps"
    )

    result = scaffold_artifact.main(["budget-tracker"])

    captured = capsys.readouterr()
    assert result == 0
    assert "Created artifact scaffold" in captured.out


def test_scaffold_artifact_creates_tests_directory_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apps_dir = tmp_path / "apps"
    tests_js_apps_dir = tmp_path / "tests" / "js" / "apps"
    monkeypatch.setattr(scaffold_artifact, "APPS_DIR", apps_dir)
    monkeypatch.setattr(scaffold_artifact, "TESTS_JS_APPS_DIR", tests_js_apps_dir)

    scaffold_artifact.scaffold_artifact("budget-tracker")

    assert tests_js_apps_dir.is_dir()
    assert (tests_js_apps_dir / "budget-tracker").is_dir()


def test_main_requires_exactly_one_argument() -> None:
    with pytest.raises(ValueError, match="Usage: make new name=<artifact-name>"):
        scaffold_artifact.main([])
