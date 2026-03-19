from __future__ import annotations

from pathlib import Path

import pytest

import scripts.scaffold_artifact as scaffold_artifact


def test_title_from_slug_formats_words() -> None:
    assert scaffold_artifact._title_from_slug("budget-tracker") == "Budget Tracker"


def test_index_template_includes_title() -> None:
    template = scaffold_artifact._index_template("Budget Tracker")

    assert "<title>Budget Tracker</title>" in template
    assert "<h1>Budget Tracker</h1>" in template


def test_scaffold_artifact_creates_expected_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apps_dir = tmp_path / "apps"
    monkeypatch.setattr(scaffold_artifact, "APPS_DIR", apps_dir)

    artifact_dir = scaffold_artifact.scaffold_artifact("budget-tracker")

    assert artifact_dir == apps_dir / "budget-tracker"
    assert (artifact_dir / "index.html").exists()
    assert (artifact_dir / "name.txt").read_text(encoding="utf-8") == "Budget Tracker\n"
    assert (artifact_dir / "description.txt").read_text(encoding="utf-8") == "\n"
    assert (artifact_dir / "tags.txt").read_text(encoding="utf-8") == "\n"
    assert (artifact_dir / "tools.txt").read_text(encoding="utf-8") == "\n"


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

    with pytest.raises(FileExistsError, match="Artifact directory already exists"):
        scaffold_artifact.scaffold_artifact("budget-tracker")


def test_main_scaffolds_artifact_and_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    apps_dir = tmp_path / "apps"
    monkeypatch.setattr(scaffold_artifact, "APPS_DIR", apps_dir)

    result = scaffold_artifact.main(["budget-tracker"])

    captured = capsys.readouterr()
    assert result == 0
    assert "Created artifact scaffold" in captured.out


def test_main_requires_exactly_one_argument() -> None:
    with pytest.raises(ValueError, match="Usage: scaffold_artifact.py <artifact-name>"):
        scaffold_artifact.main([])
