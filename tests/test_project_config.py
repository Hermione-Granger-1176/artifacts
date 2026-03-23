from __future__ import annotations

from pathlib import Path

import pytest

import scripts.project_config as project_config


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_load_artifacts_config_returns_empty_dict_when_section_is_missing(
    tmp_path: Path,
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, "[tool.other]\nvalue = true\n")

    assert project_config.load_artifacts_config(pyproject) == {}


def test_load_artifacts_config_rejects_non_table_section(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, 'tool = "invalid"\n')

    assert project_config.load_artifacts_config(pyproject) == {}


def test_load_artifacts_config_rejects_non_mapping_artifacts_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, '[tool.artifacts]\nsite_url = "https://example.com"\n')

    monkeypatch.setattr(
        project_config.tomllib,
        "loads",
        lambda _: {"tool": {"artifacts": "invalid"}},
    )

    with pytest.raises(ValueError, match=r"\[tool\.artifacts\] must be a table"):
        project_config.load_artifacts_config(pyproject)


def test_load_artifacts_setting_errors_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.toml"

    with pytest.raises(FileNotFoundError, match="pyproject.toml not found"):
        project_config.load_artifacts_setting(missing, "site_url")


def test_load_artifacts_setting_reads_string_value(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, '[tool.artifacts]\nsite_url = "https://example.com"\n')

    assert project_config.load_artifacts_setting(pyproject, "site_url") == (
        "https://example.com"
    )


def test_load_artifacts_setting_errors_for_missing_key(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, '[tool.artifacts]\nsite_path = "/artifacts/"\n')

    with pytest.raises(ValueError, match="Missing tool.artifacts.site_url"):
        project_config.load_artifacts_setting(pyproject, "site_url")


def test_load_artifacts_setting_rejects_non_string_values(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, "[tool.artifacts]\nsite_url = 1\n")

    with pytest.raises(ValueError, match="tool.artifacts.site_url must be a string"):
        project_config.load_artifacts_setting(pyproject, "site_url")
