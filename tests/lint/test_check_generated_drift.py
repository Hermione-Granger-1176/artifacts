from __future__ import annotations

from pathlib import Path

import pytest

import scripts.build.generate_index as generate_index
import scripts.lint.check_generated_drift as check_generated_drift


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def configure_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path]:
    readme_file = tmp_path / "README.md"
    js_output_file = tmp_path / "js" / "data.js"
    js_config_output_file = tmp_path / "js" / "gallery-config.js"

    monkeypatch.setattr(generate_index, "README_FILE", readme_file)
    monkeypatch.setattr(generate_index, "JS_OUTPUT_FILE", js_output_file)
    monkeypatch.setattr(generate_index, "JS_CONFIG_OUTPUT_FILE", js_config_output_file)

    return readme_file, js_output_file, js_config_output_file


def test_check_generated_drift_returns_changed_files_and_restores_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    readme_file, js_output_file, js_config_output_file = configure_targets(
        tmp_path, monkeypatch
    )
    write_text(readme_file, "original readme\n")
    write_text(js_output_file, "original data\n")
    write_text(js_config_output_file, "original config\n")

    def fake_generate() -> None:
        write_text(readme_file, "updated readme\n")
        write_text(js_output_file, "original data\n")
        write_text(js_config_output_file, "updated config\n")

    monkeypatch.setattr(generate_index, "generate", fake_generate)

    drifted = check_generated_drift.check_generated_drift()

    assert drifted == [readme_file, js_config_output_file]
    assert readme_file.read_text(encoding="utf-8") == "original readme\n"
    assert js_output_file.read_text(encoding="utf-8") == "original data\n"
    assert js_config_output_file.read_text(encoding="utf-8") == "original config\n"


def test_check_generated_drift_removes_created_files_when_original_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    readme_file, js_output_file, js_config_output_file = configure_targets(
        tmp_path, monkeypatch
    )
    write_text(readme_file, "original readme\n")
    write_text(js_output_file, "original data\n")

    def fake_generate() -> None:
        write_text(js_config_output_file, "new config\n")

    monkeypatch.setattr(generate_index, "generate", fake_generate)

    drifted = check_generated_drift.check_generated_drift()

    assert drifted == [js_config_output_file]
    assert not js_config_output_file.exists()


def test_check_generated_drift_restores_files_when_generator_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    readme_file, js_output_file, js_config_output_file = configure_targets(
        tmp_path, monkeypatch
    )
    write_text(readme_file, "original readme\n")
    write_text(js_output_file, "original data\n")
    write_text(js_config_output_file, "original config\n")

    def fake_generate() -> None:
        write_text(readme_file, "updated readme\n")
        raise ValueError("generator broke")

    monkeypatch.setattr(generate_index, "generate", fake_generate)

    with pytest.raises(ValueError, match="generator broke"):
        check_generated_drift.check_generated_drift()

    assert readme_file.read_text(encoding="utf-8") == "original readme\n"
    assert js_output_file.read_text(encoding="utf-8") == "original data\n"
    assert js_config_output_file.read_text(encoding="utf-8") == "original config\n"


def test_main_reports_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check_generated_drift, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_generated_drift, "check_generated_drift", lambda: [])

    exit_code = check_generated_drift.main([])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "Generated files are up to date"


def test_main_reports_changed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check_generated_drift, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        check_generated_drift,
        "check_generated_drift",
        lambda: [tmp_path / "README.md", tmp_path / "js" / "data.js"],
    )

    exit_code = check_generated_drift.main([])

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "Generated files would change:" in captured
    assert "- README.md" in captured
    assert "- js/data.js" in captured


def test_main_reports_generator_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail() -> list[Path]:
        raise ValueError("broken")

    monkeypatch.setattr(check_generated_drift, "check_generated_drift", fail)

    exit_code = check_generated_drift.main([])

    assert exit_code == 1
    assert capsys.readouterr().out.strip() == "Generated drift check failed: broken"
